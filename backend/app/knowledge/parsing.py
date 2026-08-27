"""Parses one Lenny's Data source document (podcast transcript or newsletter post).

Metadata - title, guest, publication date, source URL, word count -
comes from the source repository's own ``index.json``, not from each
file's YAML frontmatter: only ``index.json`` carries a source URL for
podcast entries at all (a podcast transcript's own frontmatter has
``title``/``date``/``type``/``guest``/``channel``/``description`` and
sometimes ``word_count``, but no URL field - verified by inspecting the
actual source repository, not assumed). Frontmatter is still parsed, to
cleanly separate it from the transcript/essay body.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from app.db.knowledge_models import KnowledgeSourceType

_TURN_RE = re.compile(r"^\*\*(?P<speaker>[^*]+)\*\*\s*\((?P<timestamp>[\d:]+)\):\s*$")


class MalformedSourceError(Exception):
    """Raised when a source file doesn't match the expected shape."""


@dataclass(frozen=True)
class Turn:
    speaker: str
    timestamp: str
    text: str


@dataclass(frozen=True)
class SourceIndexEntry:
    """One entry from the source repository's ``index.json``."""

    source_type: KnowledgeSourceType
    filename: str
    title: str
    guest: str | None
    published_at: date | None
    source_url: str | None
    word_count: int | None


@dataclass(frozen=True)
class ParsedDocument:
    """A fully parsed source document, ready for chunking."""

    index_entry: SourceIndexEntry
    slug: str
    content_hash: str
    turns: list[Turn] | None  # populated for podcasts, else None
    paragraphs: list[str] | None  # populated for newsletters, else None


def load_source_index(index_path: Path) -> list[SourceIndexEntry]:
    """Read and validate the source repository's ``index.json``.

    Raises ``MalformedSourceError`` (not a raw ``json.JSONDecodeError`` or
    ``KeyError``) so the CLI can report a clear, actionable failure
    instead of a stack trace pointing into this module.
    """
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MalformedSourceError(f"Could not read/parse index.json at {index_path}: {exc}") from exc

    entries: list[SourceIndexEntry] = []
    for kind, key in ((KnowledgeSourceType.podcast, "podcasts"), (KnowledgeSourceType.newsletter, "newsletters")):
        for item in raw.get(key, []):
            try:
                published_at = datetime.strptime(item["date"], "%Y-%m-%d").date() if item.get("date") else None
                entries.append(
                    SourceIndexEntry(
                        source_type=kind,
                        filename=item["filename"],
                        title=item["title"],
                        guest=item.get("guest") or None,
                        published_at=published_at,
                        source_url=item.get("post_url") or item.get("youtube_url") or None,
                        word_count=item.get("word_count"),
                    )
                )
            except (KeyError, ValueError) as exc:
                raise MalformedSourceError(f"index.json entry under {key!r} is missing a required field: {exc}") from exc
    return entries


def _split_frontmatter(raw_text: str) -> tuple[dict, str]:
    if not raw_text.startswith("---"):
        raise MalformedSourceError("File does not start with a '---' YAML frontmatter block.")
    parts = raw_text.split("---", 2)
    if len(parts) != 3:
        raise MalformedSourceError("File has an unterminated YAML frontmatter block.")
    frontmatter = yaml.safe_load(parts[1]) or {}
    if not isinstance(frontmatter, dict):
        raise MalformedSourceError("YAML frontmatter did not parse to a mapping.")
    return frontmatter, parts[2]


def _parse_turns(body: str) -> list[Turn]:
    """Split a transcript body into speaker turns.

    A state machine, not a blank-line split: a turn's body can itself
    contain a blank-line-separated multi-line answer, and (rarer) a
    speaker marker can immediately follow another with no text between
    them (an interruption with nothing transcribed) - both are handled
    correctly here, where a naive "split on blank lines" would not.
    """
    turns: list[Turn] = []
    speaker: str | None = None
    timestamp: str | None = None
    lines: list[str] = []

    def _flush() -> None:
        if speaker is None:
            return
        text = " ".join(line for line in lines if line).strip()
        if text:
            turns.append(Turn(speaker=speaker, timestamp=timestamp or "", text=text))

    for raw_line in body.splitlines():
        match = _TURN_RE.match(raw_line.strip())
        if match:
            _flush()
            speaker = match.group("speaker").strip()
            timestamp = match.group("timestamp")
            lines = []
        elif speaker is not None and raw_line.strip():
            lines.append(raw_line.strip())
    _flush()
    return turns


def _parse_paragraphs(body: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]


def parse_document(*, raw_bytes: bytes, index_entry: SourceIndexEntry) -> ParsedDocument:
    """Parse one source file's raw bytes against its ``index.json`` entry."""
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MalformedSourceError(f"{index_entry.filename!r} is not valid UTF-8 text.") from exc

    _frontmatter, body = _split_frontmatter(text)
    slug = index_entry.filename.rsplit("/", 1)[-1].removesuffix(".md")
    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    if index_entry.source_type is KnowledgeSourceType.podcast:
        turns = _parse_turns(body)
        if not turns:
            raise MalformedSourceError(f"No speaker turns found in {index_entry.filename!r}.")
        return ParsedDocument(
            index_entry=index_entry, slug=slug, content_hash=content_hash, turns=turns, paragraphs=None
        )

    paragraphs = _parse_paragraphs(body)
    if not paragraphs:
        raise MalformedSourceError(f"No content paragraphs found in {index_entry.filename!r}.")
    return ParsedDocument(
        index_entry=index_entry, slug=slug, content_hash=content_hash, turns=None, paragraphs=paragraphs
    )
