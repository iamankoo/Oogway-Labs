"""KnowledgeRetriever: the agent's only path to the Lenny knowledge base.

Ranking is a pure-Python BM25 score over chunk rows loaded from
PostgreSQL, not a Postgres-native full-text/vector index. This is a
deliberate choice - see ``docs/architecture.md`` "Retrieval strategy" for
the full reasoning - made for two reasons: (1) the corpus this phase
targets (Lenny's Data's free starter pack: 50 podcast transcripts + 10
newsletter posts) chunks down to a few thousand chunks, small enough to
score entirely in Python with no measurable latency cost, avoiding both
a paid embedding API and a new local embedding-model dependency; (2) the
identical ranking code then runs unmodified against both PostgreSQL
(production/Docker) and the project's existing in-memory SQLite test
fixture, since Postgres-only functions like ``to_tsvector``/``ts_rank_cd``
would not run there at all. A cheap SQL ``ILIKE`` prefilter (see
``_candidate_chunks``) keeps a query from hydrating every chunk in the
corpus, and a per-document cap keeps results source-diverse rather than
one document dominating the top-k.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.knowledge_models import KnowledgeChunk, KnowledgeDocument

DEFAULT_TOP_K = 4
# BM25's raw score scale depends on corpus size (IDF is a function of how
# many documents/chunks exist in total), so it is NOT a meaningful
# absolute threshold across corpora of different sizes - this is why the
# real precision mechanism against off-topic queries is
# `_bm25_scores`'s minimum-matched-terms gate (see there), calibrated
# empirically against the real ingested corpus - see
# docs/architecture.md "Retrieval parameters". This constant is only a
# low backstop against a near-zero-signal match that still happened to
# clear the term-coverage gate.
DEFAULT_MIN_RELEVANCE = 0.5
MAX_CHUNKS_PER_DOCUMENT = 2

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an the of to in on for and or is are was were be been being this that these those "
    "it its i me my mine myself you your yours yourself we us our ours ourselves they them "
    "their theirs themselves he him his himself she her hers herself as at by with from "
    "about into over than then so if not no do does did can could should would will just "
    "also very what how when where which who whom whose tell say says said know knows "
    "think thinks want wants need needs look looks see sees get gets got make makes made "
    "way ways best good great thing things".split()
)

# Okapi BM25's standard constants.
_BM25_K1 = 1.5
_BM25_B = 0.75


def _tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS]


@dataclass(frozen=True)
class RetrievedChunk:
    """One retrieval result - everything the agent and API need to build
    both the grounding prompt and a user-facing citation, with nothing
    added or guessed beyond what the source repository actually provided.
    """

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    source_type: str
    title: str
    guest: str | None
    published_at: date | None
    source_url: str | None
    text: str
    relevance: float


class KnowledgeRetriever:
    def __init__(
        self, db: AsyncSession, *, top_k: int = DEFAULT_TOP_K, min_relevance: float = DEFAULT_MIN_RELEVANCE
    ) -> None:
        self._db = db
        self._top_k = top_k
        self._min_relevance = min_relevance

    async def _candidate_chunks(self, query_tokens: list[str]) -> list[tuple[KnowledgeChunk, KnowledgeDocument]]:
        """SQL-level prefilter: chunks containing at least one query token.

        Bounds how much of the corpus a query ever hydrates into Python -
        see the module docstring for why this isn't a real index.
        """
        conditions = [KnowledgeChunk.text.ilike(f"%{token}%") for token in query_tokens[:8]]
        result = await self._db.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(or_(*conditions))
        )
        return list(result.all())

    @staticmethod
    def _bm25_scores(
        query_tokens: list[str], candidates: list[tuple[KnowledgeChunk, KnowledgeDocument]]
    ) -> list[tuple[float, KnowledgeChunk, KnowledgeDocument]]:
        if not candidates:
            return []

        candidate_tokens = [_tokenize(chunk.text) for chunk, _doc in candidates]
        doc_freq: Counter[str] = Counter()
        for tokens in candidate_tokens:
            doc_freq.update(set(tokens))

        n = len(candidates)
        avg_len = sum(len(tokens) for tokens in candidate_tokens) / n or 1.0
        distinct_query_terms = set(query_tokens)
        # A single rare word coincidentally appearing once in one chunk gets
        # a huge IDF weight in plain BM25 and can outscore a chunk that
        # genuinely matches most of the query - verified empirically against
        # the real ingested corpus (an out-of-domain query like "what's the
        # best way to cook a lasagna" scored *above* several genuinely
        # on-topic product questions before this guard was added). Requiring
        # at least two distinct query terms to actually appear (or all of
        # them, for a one/two-word query) filters that out while barely
        # affecting real multi-word product/growth questions.
        min_matched_terms = min(2, len(distinct_query_terms))

        scored: list[tuple[float, KnowledgeChunk, KnowledgeDocument]] = []
        for (chunk, doc), tokens in zip(candidates, candidate_tokens):
            term_freq = Counter(tokens)
            matched_terms = sum(1 for term in distinct_query_terms if term_freq.get(term, 0) > 0)
            if matched_terms < min_matched_terms:
                continue

            doc_len = len(tokens) or 1
            score = 0.0
            for term in query_tokens:
                tf = term_freq.get(term, 0)
                if tf == 0:
                    continue
                df = doc_freq.get(term, 0)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                denom = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * doc_len / avg_len)
                score += idf * (tf * (_BM25_K1 + 1)) / denom
            if score > 0:
                scored.append((score, chunk, doc))
        return scored

    async def search(self, query: str) -> list[RetrievedChunk]:
        """Return up to ``top_k`` relevant chunks, or ``[]`` if none clear the threshold.

        An empty result is a normal, expected outcome (see
        ``docs/architecture.md`` "Empty retrieval") - it means the
        available Lenny material doesn't support this query, not that
        something failed.
        """
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        candidates = await self._candidate_chunks(query_tokens)
        scored = self._bm25_scores(query_tokens, candidates)
        scored.sort(key=lambda item: item[0], reverse=True)

        results: list[RetrievedChunk] = []
        per_document_count: dict[uuid.UUID, int] = {}
        for score, chunk, doc in scored:
            if score < self._min_relevance:
                break
            if per_document_count.get(doc.id, 0) >= MAX_CHUNKS_PER_DOCUMENT:
                continue
            per_document_count[doc.id] = per_document_count.get(doc.id, 0) + 1
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    source_type=doc.source_type.value,
                    title=doc.title,
                    guest=doc.guest,
                    published_at=doc.published_at,
                    source_url=doc.source_url,
                    text=chunk.text,
                    relevance=round(score, 4),
                )
            )
            if len(results) >= self._top_k:
                break
        return results
