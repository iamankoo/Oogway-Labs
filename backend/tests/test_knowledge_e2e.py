"""End-to-end grounding test: question -> retrieval -> agent -> answer -> sources -> API response.

Uses the synthetic fixture corpus (never real Lenny content) ingested
into the same in-memory SQLite database the test client uses, and a
stub model provider (no real model call needed to verify the pipeline
wiring and API response shape) - matching this project's existing test
strategy of never requiring real model credentials or network access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from pi_agent.llm import AssistantResponse, NeutralMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.knowledge.ingest import run_ingestion

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "knowledge_source"


class _StubProvider:
    name = "ollama"
    model = "test-model"
    supports_streaming = False

    def complete(
        self, system: str, messages: list[NeutralMessage], tools: list[dict[str, Any]]
    ) -> AssistantResponse:
        return AssistantResponse(text="Focus on time-to-first-value.")


@pytest.fixture
async def grounded_db(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """Ingest the synthetic fixture corpus into the test's SQLite database."""
    exit_code = await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    assert exit_code == 0


async def test_supported_question_returns_a_grounded_answer_with_sources(
    client: AsyncClient, grounded_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.sessions.get_model_provider", lambda _settings: _StubProvider())

    session = (await client.post("/api/sessions")).json()
    response = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "What is the biggest onboarding mistake?"},
    )

    assert response.status_code == 201
    body = response.json()
    assistant_message = body["assistant_message"]
    assert assistant_message is not None
    assert assistant_message["grounded"] is True
    assert len(assistant_message["sources"]) >= 1

    source = assistant_message["sources"][0]
    assert source["title"] == "SYNTHETIC TEST FIXTURE: Onboarding with Test Guest Alpha"
    assert source["guest"] == "Test Guest Alpha"
    assert source["source_type"] == "podcast"
    assert source["source_url"] == "https://example.com/fixtures/test-guest-alpha"
    assert source["relevance"] > 0
    # The excerpt is real retrieved chunk text, not something invented.
    assert "onboarding" in source["excerpt"].lower() or "activation" in source["excerpt"].lower()


async def test_unsupported_question_returns_no_fabricated_sources(
    client: AsyncClient, grounded_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.sessions.get_model_provider", lambda _settings: _StubProvider())

    session = (await client.post("/api/sessions")).json()
    response = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "What is the airspeed velocity of an unladen swallow?"},
    )

    assert response.status_code == 201
    body = response.json()
    assistant_message = body["assistant_message"]
    assert assistant_message is not None
    assert assistant_message["grounded"] is False
    assert assistant_message["sources"] == []


async def test_sources_persist_across_a_refresh(
    client: AsyncClient, grounded_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.sessions.get_model_provider", lambda _settings: _StubProvider())

    session = (await client.post("/api/sessions")).json()
    await client.post(
        f"/api/sessions/{session['id']}/messages", json={"content": "What is the biggest onboarding mistake?"}
    )

    # Simulates a browser refresh: re-fetching messages from scratch.
    messages = (await client.get(f"/api/sessions/{session['id']}/messages")).json()
    assistant_message = next(m for m in messages if m["role"] == "assistant")
    assert assistant_message["grounded"] is True
    assert len(assistant_message["sources"]) >= 1
