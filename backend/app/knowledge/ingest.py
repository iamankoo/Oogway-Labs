"""Idempotent CLI ingestion of a Lenny's Data source directory into PostgreSQL.

Usage
-----
::

    python -m app.knowledge.ingest --source data/knowledge_source

Run once after fetching the source data locally (see the root
``README.md`` "Knowledge base setup" for exactly how), and re-run any
time the source directory changes. This never runs automatically on
application startup (``docker compose up`` never blocks on it) - it is a
separate, explicit, evaluator-run step.

What "ingest" does, per file
-----------------------------
1. Look up the file's entry in the source directory's own ``index.json``
   (title, guest, publication date, source URL, word count - see
   ``app.knowledge.parsing`` for why this file is authoritative over each
   document's own frontmatter).
2. Hash the raw file bytes (SHA-256). If a document with the same
   ``(source_type, slug)`` already exists with an identical hash, it is
   skipped entirely - running ingestion twice never creates duplicate
   rows or reprocesses unchanged files.
3. Otherwise (new document, or an existing one whose hash changed):
   parse, chunk, and upsert - replacing that document's chunks and
   updating its metadata inside one transaction per document, so a
   failure on one file can never corrupt another's data.
4. A missing, oversized, or malformed file is logged as a failure and
   skipped; ingestion continues with the rest of the corpus rather than
   aborting the whole run.

Security
--------
``--source`` must resolve to an existing local directory. Every file
this command opens is resolved from ``index.json``'s own ``filename``
field and asserted to still resolve inside that source directory (no
``..`` escape), must end in ``.md``, and is size-capped
(``MAX_SOURCE_FILE_BYTES``) before being read into memory - see
``docs/architecture.md`` "Ingestion security".
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.knowledge_models import KnowledgeChunk, KnowledgeDocument
from app.knowledge.chunking import chunk_paragraphs, chunk_turns
from app.knowledge.parsing import MalformedSourceError, ParsedDocument, SourceIndexEntry, load_source_index, parse_document
from app.logging_config import configure_logging, get_logger

MAX_SOURCE_FILE_BYTES = 5 * 1024 * 1024  # 5MB - real transcripts run ~100-150KB; generous headroom, not unbounded

logger = get_logger(__name__)


class IngestionFileError(Exception):
    """A single-file failure that should not abort the whole ingestion run."""


def _resolve_and_validate(source_root: Path, entry: SourceIndexEntry) -> Path:
    """Resolve ``entry.filename`` under ``source_root``, rejecting anything that escapes it."""
    if not entry.filename.endswith(".md"):
        raise IngestionFileError(f"{entry.filename!r}: index.json entry does not point at a .md file.")

    candidate = (source_root / entry.filename).resolve()
    if source_root not in candidate.parents:
        raise IngestionFileError(f"{entry.filename!r}: resolves outside the source directory - refusing to read it.")
    if not candidate.is_file():
        raise IngestionFileError(f"{entry.filename!r}: file not found at {candidate}.")

    size = candidate.stat().st_size
    if size > MAX_SOURCE_FILE_BYTES:
        raise IngestionFileError(f"{entry.filename!r}: {size} bytes exceeds the {MAX_SOURCE_FILE_BYTES} byte cap.")
    return candidate


def _read_and_parse(source_root: Path, entry: SourceIndexEntry) -> ParsedDocument:
    path = _resolve_and_validate(source_root, entry)
    raw_bytes = path.read_bytes()
    try:
        return parse_document(raw_bytes=raw_bytes, index_entry=entry)
    except MalformedSourceError as exc:
        raise IngestionFileError(str(exc)) from exc


def _draft_chunks(parsed: ParsedDocument):
    if parsed.turns is not None:
        return chunk_turns(parsed.turns)
    return chunk_paragraphs(parsed.paragraphs or [])


async def _upsert_document(db, parsed: ParsedDocument) -> str:
    """Insert or update one document + its chunks. Returns "new"/"updated"/"unchanged"."""
    entry = parsed.index_entry
    existing = (
        await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.source_type == entry.source_type, KnowledgeDocument.slug == parsed.slug
            )
        )
    ).scalar_one_or_none()

    if existing is not None and existing.content_hash == parsed.content_hash:
        return "unchanged"

    drafts = _draft_chunks(parsed)
    if not drafts:
        raise IngestionFileError(f"{entry.filename!r}: produced zero chunks.")

    if existing is not None:
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == existing.id))
        document = existing
        document.title = entry.title
        document.guest = entry.guest
        document.published_at = entry.published_at
        document.source_url = entry.source_url
        document.word_count = entry.word_count
        document.content_hash = parsed.content_hash
        outcome = "updated"
    else:
        document = KnowledgeDocument(
            source_type=entry.source_type,
            slug=parsed.slug,
            title=entry.title,
            guest=entry.guest,
            published_at=entry.published_at,
            source_url=entry.source_url,
            word_count=entry.word_count,
            content_hash=parsed.content_hash,
        )
        db.add(document)
        outcome = "new"

    await db.flush()  # assigns document.id for new rows

    for index, draft in enumerate(drafts):
        db.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=index,
                text=draft.text,
                speakers=draft.speakers,
                char_count=len(draft.text),
            )
        )

    await db.commit()
    return outcome


async def run_ingestion(source_dir: str, *, session_factory: async_sessionmaker | None = None) -> int:
    """Ingest every file listed in ``source_dir/index.json``. Returns a process exit code.

    ``session_factory`` is injectable so tests can point ingestion at an
    isolated in-memory SQLite database instead of a real PostgreSQL
    instance (matching this project's existing test strategy - see
    ``backend/tests/conftest.py``); the CLI entrypoint always builds a
    real one from ``Settings.database_url``.
    """
    source_root = Path(source_dir).resolve()
    index_path = source_root / "index.json"
    if not index_path.is_file():
        logger.error("knowledge_ingest_missing_index", source_dir=str(source_root))
        print(
            f"No index.json found at {index_path}.\n"
            "See README.md 'Knowledge base setup' for how to fetch the source data.",
            file=sys.stderr,
        )
        return 1

    try:
        entries = load_source_index(index_path)
    except MalformedSourceError as exc:
        logger.error("knowledge_ingest_bad_index", error=str(exc))
        print(f"index.json is malformed: {exc}", file=sys.stderr)
        return 1

    counts = {"new": 0, "updated": 0, "unchanged": 0, "failed": 0}

    owns_engine = session_factory is None
    engine = None
    if owns_engine:
        settings = get_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        for entry in entries:
            try:
                parsed = _read_and_parse(source_root, entry)
                outcome = await _upsert_document(db, parsed)
                counts[outcome] += 1
                logger.info("knowledge_ingest_document", filename=entry.filename, outcome=outcome)
            except IngestionFileError as exc:
                await db.rollback()
                counts["failed"] += 1
                logger.warning("knowledge_ingest_document_failed", filename=entry.filename, error=str(exc))

        total_documents = (await db.execute(select(KnowledgeDocument))).scalars().all()
        total_chunks = (await db.execute(select(KnowledgeChunk))).scalars().all()

    if owns_engine and engine is not None:
        await engine.dispose()

    logger.info(
        "knowledge_ingest_complete",
        new=counts["new"],
        updated=counts["updated"],
        unchanged=counts["unchanged"],
        failed=counts["failed"],
        total_documents=len(total_documents),
        total_chunks=len(total_chunks),
    )
    print(
        f"Ingestion complete: {counts['new']} new, {counts['updated']} updated, "
        f"{counts['unchanged']} unchanged, {counts['failed']} failed. "
        f"Knowledge base now has {len(total_documents)} documents / {len(total_chunks)} chunks."
    )
    return 1 if counts["failed"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--source",
        required=True,
        help="Path to a directory containing index.json, podcasts/, and newsletters/ (a Lenny's Data checkout).",
    )
    args = parser.parse_args()

    configure_logging(get_settings())
    exit_code = asyncio.run(run_ingestion(args.source))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
