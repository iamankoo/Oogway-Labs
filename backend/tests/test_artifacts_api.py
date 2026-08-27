"""Tests for artifact generation/retrieval (Phase 5).

Uses the same stub-provider pattern as test_generation_api.py - no real
model or network access - and the synthetic knowledge fixture from
Phase 4 to verify grounded artifact generation end to end.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from pi_agent.llm import AssistantResponse, NeutralMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.errors import ModelTimeoutError
from app.knowledge.ingest import run_ingestion

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "knowledge_source"


class _StubProvider:
    name = "ollama"
    model = "test-model"
    supports_streaming = False

    def __init__(self, *, text: str | None = None, error: Exception | None = None) -> None:
        self._text = text or "# A Test Essay\n\nSome generated content."
        self._error = error

    def complete(self, system: str, messages: list[NeutralMessage], tools: list[dict[str, Any]]) -> AssistantResponse:
        if self._error:
            raise self._error
        return AssistantResponse(text=self._text)


async def test_generate_markdown_artifact_and_list_it(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.artifacts.get_model_provider", lambda _settings, **_kwargs: _StubProvider())

    session = (await client.post("/api/sessions")).json()
    response = await client.post(
        f"/api/sessions/{session['id']}/artifacts", json={"kind": "markdown", "topic": "onboarding"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["generation_error"] is None
    artifact = body["artifact"]
    assert artifact["kind"] == "markdown"
    assert artifact["title"] == "A Test Essay"
    assert "generated content" in artifact["content"]

    listed = (await client.get(f"/api/sessions/{session['id']}/artifacts")).json()
    assert len(listed) == 1
    assert listed[0]["id"] == artifact["id"]


async def test_ship30_essay_grounds_with_real_fixture_sources(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)

    captured: dict[str, Any] = {}

    class _CapturingProvider(_StubProvider):
        def complete(self, system, messages, tools):  # noqa: ANN001
            captured["messages"] = messages
            return AssistantResponse(text="# Onboarding Essay\n\nSome ~1250 word essay body.")

    monkeypatch.setattr("app.api.artifacts.get_model_provider", lambda _settings, **_kwargs: _CapturingProvider())

    session = (await client.post("/api/sessions")).json()
    response = await client.post(
        f"/api/sessions/{session['id']}/artifacts",
        json={"kind": "ship30", "topic": "What is the biggest onboarding mistake?"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["artifact"]["kind"] == "ship30"
    user_content = captured["messages"][0]["content"]
    assert "<retrieved_lenny_material>" in user_content
    assert "Test Guest Alpha" in user_content


async def test_unsupported_topic_still_generates_but_without_fabricated_grounding(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await run_ingestion(str(FIXTURES_ROOT), session_factory=db_sessionmaker)
    captured: dict[str, Any] = {}

    class _CapturingProvider(_StubProvider):
        def complete(self, system, messages, tools):  # noqa: ANN001
            captured["messages"] = messages
            return AssistantResponse(text="# General Advice\n\nSome general reasoning.")

    monkeypatch.setattr("app.api.artifacts.get_model_provider", lambda _settings, **_kwargs: _CapturingProvider())

    session = (await client.post("/api/sessions")).json()
    response = await client.post(
        f"/api/sessions/{session['id']}/artifacts",
        json={"kind": "ship30", "topic": "What is the airspeed velocity of an unladen swallow?"},
    )

    assert response.status_code == 201
    assert "No relevant material was found" in captured["messages"][0]["content"]


async def test_artifact_generation_failure_reports_safe_error(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.artifacts.get_model_provider", lambda _settings, **_kwargs: _StubProvider(error=ModelTimeoutError())
    )

    session = (await client.post("/api/sessions")).json()
    response = await client.post(f"/api/sessions/{session['id']}/artifacts", json={"kind": "html"})

    assert response.status_code == 201
    body = response.json()
    assert body["artifact"] is None
    assert body["generation_error"]["code"] == "model_timeout"

    listed = (await client.get(f"/api/sessions/{session['id']}/artifacts")).json()
    assert listed == []


async def test_html_artifact_strips_code_fence_and_extracts_title(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fenced = "```html\n<!DOCTYPE html><html><head><title>My Page</title></head><body>Hi</body></html>\n```"
    monkeypatch.setattr("app.api.artifacts.get_model_provider", lambda _settings, **_kwargs: _StubProvider(text=fenced))

    session = (await client.post("/api/sessions")).json()
    response = await client.post(f"/api/sessions/{session['id']}/artifacts", json={"kind": "html"})

    artifact = response.json()["artifact"]
    assert artifact["title"] == "My Page"
    assert not artifact["content"].startswith("```")
    assert artifact["content"].startswith("<!DOCTYPE html>")


async def test_artifacts_are_session_isolated(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.artifacts.get_model_provider", lambda _settings, **_kwargs: _StubProvider())

    session_a = (await client.post("/api/sessions")).json()
    session_b = (await client.post("/api/sessions")).json()
    await client.post(f"/api/sessions/{session_a['id']}/artifacts", json={"kind": "markdown"})

    listed_a = (await client.get(f"/api/sessions/{session_a['id']}/artifacts")).json()
    listed_b = (await client.get(f"/api/sessions/{session_b['id']}/artifacts")).json()
    assert len(listed_a) == 1
    assert listed_b == []
