"""Tests for app.services.knowledge_retriever.KnowledgeRetriever.

Ingests the synthetic fixture corpus (tests/fixtures/knowledge_source/ -
clearly labeled synthetic data, never real Lenny content) into the same
in-memory SQLite database the rest of the suite uses, then exercises
retrieval against it.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.knowledge.ingest import run_ingestion
from app.services.knowledge_retriever import KnowledgeRetriever

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "knowledge_source"


async def _ingested_session(db_sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncSession:
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    return db_sessionmaker()


async def test_relevant_query_finds_the_matching_chunk(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        retriever = KnowledgeRetriever(db)
        results = await retriever.search("What is the biggest onboarding mistake?")

    assert results
    assert any("onboarding" in r.text.lower() or "activation" in r.text.lower() for r in results)
    assert all(r.relevance > 0 for r in results)


async def test_irrelevant_query_returns_no_results(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        retriever = KnowledgeRetriever(db)
        results = await retriever.search("quantum chromodynamics particle physics")

    assert results == []


async def test_minimum_relevance_threshold_excludes_weak_matches(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        lenient = KnowledgeRetriever(db, min_relevance=0.0)
        strict = KnowledgeRetriever(db, min_relevance=1000.0)  # unreachably high on this tiny corpus

        lenient_results = await lenient.search("pricing")
        strict_results = await strict.search("pricing")

    assert lenient_results
    assert strict_results == []


async def test_top_k_bounds_the_result_count(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        retriever = KnowledgeRetriever(db, top_k=1, min_relevance=0.0)
        results = await retriever.search("onboarding activation pricing growth loops")

    assert len(results) <= 1


async def test_source_metadata_is_preserved_and_traceable(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        retriever = KnowledgeRetriever(db)
        results = await retriever.search("onboarding activation first value")

    assert results
    top = results[0]
    assert top.title == "SYNTHETIC TEST FIXTURE: Onboarding with Test Guest Alpha"
    assert top.guest == "Test Guest Alpha"
    assert top.source_type == "podcast"
    assert top.source_url == "https://example.com/fixtures/test-guest-alpha"
    assert top.published_at is not None
    assert top.chunk_id is not None
    assert top.document_id is not None


async def test_no_url_is_fabricated_when_source_has_none(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        retriever = KnowledgeRetriever(db, min_relevance=0.0)
        results = await retriever.search("nothing to link to here on purpose")

    matching = [r for r in results if r.title == "SYNTHETIC TEST FIXTURE: No URL Episode"]
    assert matching
    assert matching[0].source_url is None


async def test_empty_retrieval_on_a_query_with_only_stopwords(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        retriever = KnowledgeRetriever(db)
        results = await retriever.search("the a of and")

    assert results == []


async def test_multi_source_retrieval_across_documents(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    # Two terms per topic so each topic's chunk clears the minimum-matched-terms
    # gate (app.services.knowledge_retriever._bm25_scores) on its own.
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        retriever = KnowledgeRetriever(db, top_k=4, min_relevance=0.0)
        results = await retriever.search("onboarding activation tiered pricing")

    distinct_documents = {r.document_id for r in results}
    assert len(distinct_documents) >= 2


async def test_duplicate_chunks_from_the_same_document_are_capped(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """Source-diversity control: at most MAX_CHUNKS_PER_DOCUMENT chunks
    from any single document should appear in one result set.
    """
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        retriever = KnowledgeRetriever(db, top_k=10, min_relevance=0.0)
        results = await retriever.search("onboarding activation pricing growth")

    from collections import Counter

    counts = Counter(r.document_id for r in results)
    assert all(count <= 2 for count in counts.values())


async def test_follow_up_style_query_still_resolves_via_combined_terms(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """Simulates what GrowthAssistantAgent sends for a follow-up: the
    previous question's terms combined with the new, otherwise-ambiguous one.
    """
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    async with db_sessionmaker() as db:
        retriever = KnowledgeRetriever(db)
        results = await retriever.search("What makes onboarding effective? What about tiered pricing?")

    titles = {r.title for r in results}
    assert titles & {
        "SYNTHETIC TEST FIXTURE: Onboarding with Test Guest Alpha",
        "SYNTHETIC TEST FIXTURE: Pricing with Test Guest Beta",
    }
