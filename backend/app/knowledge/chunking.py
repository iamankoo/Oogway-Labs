"""Turn-aware / paragraph-aware chunking.

Neither strategy splits every N characters blindly. A podcast transcript
is a sequence of speaker turns (``app.knowledge.parsing.Turn``); a turn's
text is never split across two chunks - chunks accumulate whole turns
until a target size is reached, so a chunk always reads as a coherent,
unambiguously-attributed run of consecutive dialogue. A newsletter is
essay prose with no speakers; chunks accumulate whole paragraphs the same
way.

``TARGET_CHUNK_CHARS`` (1200, ~200 words) balances two things: large
enough that a chunk carries a complete thought rather than an isolated
sentence fragment with no context, small enough that the default top-k
retrieval (see ``app.services.knowledge_retriever``) keeps the grounding
context sent to the model - especially the CPU-bound local Ollama path -
to a small, predictable size. It is a soft target, not a hard cap: a
single turn/paragraph longer than the target is never split mid-unit to
enforce it, since preserving speaker attribution and complete thoughts
matters more here than hitting an exact size.

Consecutive chunks from the same document overlap by exactly one unit
(the last turn/paragraph of a chunk is repeated as the first unit of the
next), so a fact sitting near a chunk boundary still appears whole in at
least one retrievable chunk.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.knowledge.parsing import Turn

TARGET_CHUNK_CHARS = 1200
# A trailing chunk shorter than this (typically just the carried-over
# overlap unit, when the document ends right after a chunk boundary) is
# merged into its predecessor instead of being shipped as a near-duplicate sliver.
MIN_CHUNK_CHARS = 200


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    speakers: str | None  # comma-joined distinct speakers, in order of first appearance; podcasts only


def _pack(units: list[tuple[str, str | None]]) -> list[ChunkDraft]:
    """Greedily pack ``(text, speaker_or_none)`` units into chunks with one-unit overlap."""
    if not units:
        return []

    chunks: list[ChunkDraft] = []
    current: list[tuple[str, str | None]] = []
    current_len = 0

    def flush() -> None:
        if not current:
            return
        text = "\n\n".join(u[0] for u in current)
        speakers = ", ".join(dict.fromkeys(u[1] for u in current if u[1]))
        chunks.append(ChunkDraft(text=text, speakers=speakers or None))

    for unit_text, speaker in units:
        unit_len = len(unit_text)
        if current and current_len + unit_len > TARGET_CHUNK_CHARS:
            flush()
            overlap_unit = current[-1]
            current = [overlap_unit]
            current_len = len(overlap_unit[0])
        current.append((unit_text, speaker))
        current_len += unit_len
    flush()

    if len(chunks) >= 2 and len(chunks[-1].text) < MIN_CHUNK_CHARS:
        tail = chunks.pop()
        head = chunks.pop()
        merged_speakers: list[str] = []
        for draft in (head, tail):
            for name in (draft.speakers or "").split(", "):
                if name and name not in merged_speakers:
                    merged_speakers.append(name)
        chunks.append(ChunkDraft(text=head.text + "\n\n" + tail.text, speakers=", ".join(merged_speakers) or None))

    return chunks


def chunk_turns(turns: list[Turn]) -> list[ChunkDraft]:
    units = [(f"**{turn.speaker}**: {turn.text}", turn.speaker) for turn in turns]
    return _pack(units)


def chunk_paragraphs(paragraphs: list[str]) -> list[ChunkDraft]:
    units: list[tuple[str, str | None]] = [(paragraph, None) for paragraph in paragraphs]
    return _pack(units)
