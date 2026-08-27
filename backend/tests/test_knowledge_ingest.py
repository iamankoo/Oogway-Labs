"""Tests for app.knowledge (parsing, chunking, ingestion).

Runs entirely against the synthetic fixtures under
``tests/fixtures/knowledge_source/`` and ``tests/fixtures/malformed_knowledge_source/``
- clearly labeled synthetic data, never real Lenny content - and the same
in-memory SQLite database the rest of this test suite uses, never a real
network call or PostgreSQL instance.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.knowledge_models import KnowledgeChunk, KnowledgeDocument, KnowledgeSourceType
from app.knowledge.chunking import chunk_paragraphs, chunk_turns
from app.knowledge.ingest import IngestionFileError, _read_and_parse, run_ingestion
from app.knowledge.parsing import MalformedSourceError, SourceIndexEntry, load_source_index, parse_document

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "knowledge_source"
MALFORMED_ROOT = Path(__file__).parent / "fixtures" / "malformed_knowledge_source"


# --- parsing -----------------------------------------------------------------


def test_load_source_index_reads_podcasts_and_newsletters() -> None:
    entries = load_source_index(FIXTURES_ROOT / "index.json")
    assert len(entries) == 4
    podcast_entries = [e for e in entries if e.source_type is KnowledgeSourceType.podcast]
    newsletter_entries = [e for e in entries if e.source_type is KnowledgeSourceType.newsletter]
    assert len(podcast_entries) == 3
    assert len(newsletter_entries) == 1


def test_metadata_comes_from_index_not_frontmatter() -> None:
    """post_url only exists in index.json for podcasts - never guessed from the file."""
    entries = load_source_index(FIXTURES_ROOT / "index.json")
    alpha = next(e for e in entries if e.filename == "podcasts/test-guest-alpha.md")
    assert alpha.source_url == "https://example.com/fixtures/test-guest-alpha"
    assert alpha.guest == "Test Guest Alpha"

    gamma = next(e for e in entries if e.filename == "podcasts/test-guest-gamma.md")
    assert gamma.source_url is None  # never fabricated when absent from index.json


def test_parse_document_extracts_turns_for_podcast() -> None:
    entry = next(e for e in load_source_index(FIXTURES_ROOT / "index.json") if "alpha" in e.filename)
    raw = (FIXTURES_ROOT / entry.filename).read_bytes()
    parsed = parse_document(raw_bytes=raw, index_entry=entry)

    assert parsed.turns is not None
    assert parsed.paragraphs is None
    speakers = {t.speaker for t in parsed.turns}
    assert speakers == {"Test Host", "Test Guest Alpha"}
    assert all(t.text for t in parsed.turns)


def test_parse_document_extracts_paragraphs_for_newsletter() -> None:
    entry = next(e for e in load_source_index(FIXTURES_ROOT / "index.json") if "newsletter" in e.filename)
    raw = (FIXTURES_ROOT / entry.filename).read_bytes()
    parsed = parse_document(raw_bytes=raw, index_entry=entry)

    assert parsed.paragraphs is not None
    assert parsed.turns is None
    assert len(parsed.paragraphs) == 2


def test_content_hash_is_deterministic_and_sensitive_to_content() -> None:
    entry = next(e for e in load_source_index(FIXTURES_ROOT / "index.json") if "alpha" in e.filename)
    raw = (FIXTURES_ROOT / entry.filename).read_bytes()
    first = parse_document(raw_bytes=raw, index_entry=entry)
    second = parse_document(raw_bytes=raw, index_entry=entry)
    assert first.content_hash == second.content_hash

    changed = parse_document(raw_bytes=raw + b"\nextra", index_entry=entry)
    assert changed.content_hash != first.content_hash


def test_malformed_missing_frontmatter_raises() -> None:
    entries = load_source_index(MALFORMED_ROOT / "index.json")
    entry = next(e for e in entries if "no-frontmatter" in e.filename)
    raw = (MALFORMED_ROOT / entry.filename).read_bytes()
    with pytest.raises(MalformedSourceError):
        parse_document(raw_bytes=raw, index_entry=entry)


def test_malformed_empty_transcript_raises() -> None:
    entries = load_source_index(MALFORMED_ROOT / "index.json")
    entry = next(e for e in entries if "empty-transcript" in e.filename)
    raw = (MALFORMED_ROOT / entry.filename).read_bytes()
    with pytest.raises(MalformedSourceError):
        parse_document(raw_bytes=raw, index_entry=entry)


# --- chunking ------------------------------------------------------------


def test_chunk_turns_never_splits_a_single_turn() -> None:
    entry = next(e for e in load_source_index(FIXTURES_ROOT / "index.json") if "alpha" in e.filename)
    raw = (FIXTURES_ROOT / entry.filename).read_bytes()
    parsed = parse_document(raw_bytes=raw, index_entry=entry)

    chunks = chunk_turns(parsed.turns)
    assert len(chunks) >= 1
    for turn in parsed.turns:
        assert any(turn.text in chunk.text for chunk in chunks), f"turn text missing from all chunks: {turn.text!r}"


def test_chunk_turns_preserves_speaker_metadata() -> None:
    entry = next(e for e in load_source_index(FIXTURES_ROOT / "index.json") if "alpha" in e.filename)
    raw = (FIXTURES_ROOT / entry.filename).read_bytes()
    parsed = parse_document(raw_bytes=raw, index_entry=entry)

    chunks = chunk_turns(parsed.turns)
    assert all(chunk.speakers for chunk in chunks)
    assert any("Test Guest Alpha" in (chunk.speakers or "") for chunk in chunks)


def test_chunk_paragraphs_covers_all_source_text() -> None:
    entry = next(e for e in load_source_index(FIXTURES_ROOT / "index.json") if "newsletter" in e.filename)
    raw = (FIXTURES_ROOT / entry.filename).read_bytes()
    parsed = parse_document(raw_bytes=raw, index_entry=entry)

    chunks = chunk_paragraphs(parsed.paragraphs)
    assert len(chunks) >= 1
    for paragraph in parsed.paragraphs:
        assert any(paragraph in chunk.text for chunk in chunks)


# --- ingestion security ---------------------------------------------------


def test_path_traversal_in_index_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "podcasts").mkdir()
    hostile_entry = SourceIndexEntry(
        source_type=KnowledgeSourceType.podcast,
        filename="../outside.md",
        title="hostile",
        guest=None,
        published_at=None,
        source_url=None,
        word_count=None,
    )
    with pytest.raises(IngestionFileError, match="resolves outside the source directory"):
        _read_and_parse(tmp_path, hostile_entry)


def test_missing_file_is_reported_not_crashed(tmp_path: Path) -> None:
    (tmp_path / "podcasts").mkdir()
    entry = SourceIndexEntry(
        source_type=KnowledgeSourceType.podcast,
        filename="podcasts/does-not-exist.md",
        title="missing",
        guest=None,
        published_at=None,
        source_url=None,
        word_count=None,
    )
    with pytest.raises(IngestionFileError, match="not found"):
        _read_and_parse(tmp_path, entry)


def test_non_markdown_filename_is_rejected(tmp_path: Path) -> None:
    entry = SourceIndexEntry(
        source_type=KnowledgeSourceType.podcast,
        filename="podcasts/script.sh",
        title="not markdown",
        guest=None,
        published_at=None,
        source_url=None,
        word_count=None,
    )
    with pytest.raises(IngestionFileError, match=r"\.md"):
        _read_and_parse(tmp_path, entry)


# --- full ingestion runs (idempotency, refresh, malformed handling) -------


async def test_full_ingestion_of_the_fixture_corpus(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    exit_code = await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    assert exit_code == 0

    async with db_sessionmaker() as db:
        documents = (await db.execute(select(KnowledgeDocument))).scalars().all()
        chunks = (await db.execute(select(KnowledgeChunk))).scalars().all()

    assert len(documents) == 4
    assert len(chunks) >= 4
    slugs = {d.slug for d in documents}
    assert slugs == {"test-guest-alpha", "test-guest-beta", "test-guest-gamma", "test-newsletter-one"}


async def test_repeat_ingestion_is_idempotent(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """CRITICAL RULE: running ingestion twice must never create duplicate rows."""
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        first_run_document_ids = {d.id for d in (await db.execute(select(KnowledgeDocument))).scalars().all()}
        first_run_chunk_count = len((await db.execute(select(KnowledgeChunk))).scalars().all())

    exit_code = await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    assert exit_code == 0

    async with db_sessionmaker() as db:
        second_run_documents = (await db.execute(select(KnowledgeDocument))).scalars().all()
        second_run_chunk_count = len((await db.execute(select(KnowledgeChunk))).scalars().all())

    assert {d.id for d in second_run_documents} == first_run_document_ids
    assert len(second_run_documents) == 4
    assert second_run_chunk_count == first_run_chunk_count


async def test_changed_source_file_is_reprocessed_in_place(
    tmp_path: Path, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Refresh strategy: a changed file updates the SAME document row
    (same id, same natural key) with new chunks - it is never deleted
    and recreated as a different document.
    """
    import shutil

    source_copy = tmp_path / "source"
    shutil.copytree(FIXTURES_ROOT, source_copy)

    await run_ingestion(str(source_copy), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        before = (
            await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.slug == "test-guest-alpha"))
        ).scalar_one()
        document_id = before.id
        original_hash = before.content_hash

    # Modify the file's transcript body (a real content change).
    alpha_path = source_copy / "podcasts" / "test-guest-alpha.md"
    alpha_path.write_text(alpha_path.read_text(encoding="utf-8") + "\n**Test Host** (00:01:00):\nOne more thing.\n", encoding="utf-8")

    exit_code = await run_ingestion(str(source_copy), session_factory=db_sessionmaker)
    assert exit_code == 0

    async with db_sessionmaker() as db:
        after = (
            await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.slug == "test-guest-alpha"))
        ).scalar_one()
        chunk_texts = [
            c.text
            for c in (
                await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id))
            ).scalars().all()
        ]

    assert after.id == document_id  # same document row, not a duplicate
    assert after.content_hash != original_hash
    assert any("One more thing" in text for text in chunk_texts)


async def test_malformed_files_are_skipped_without_aborting_the_run(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    exit_code = await run_ingestion(str(MALFORMED_ROOT), session_factory=db_sessionmaker)
    assert exit_code == 1  # non-zero: failures happened

    async with db_sessionmaker() as db:
        documents = (await db.execute(select(KnowledgeDocument))).scalars().all()
    # All three fixture entries are malformed/missing - none should be ingested,
    # but the run must complete rather than raise.
    assert documents == []
