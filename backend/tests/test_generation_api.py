from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from pi_agent.llm import AssistantResponse, NeutralMessage

from app.agents.errors import ModelTimeoutError, ProviderUnavailableError


class _StubProvider:
    """Conforms to pi_agent.llm.LLMProvider without any network access."""

    name = "ollama"
    model = "llama3.2:3b"
    supports_streaming = False

    def __init__(self, *, content: str | None = None, error: Exception | None = None) -> None:
        self._content = content
        self._error = error
        self.calls: list[list[NeutralMessage]] = []

    def complete(
        self, system: str, messages: list[NeutralMessage], tools: list[dict[str, Any]]
    ) -> AssistantResponse:
        # Copy: pi_agent.Agent appends the assistant reply to this same list
        # object right after complete() returns.
        self.calls.append(list(messages))
        if self._error:
            raise self._error
        assert self._content is not None
        return AssistantResponse(text=self._content)


@pytest.fixture
def stub_provider(monkeypatch: pytest.MonkeyPatch):
    provider = _StubProvider(content="Focus on activation first.")

    def _factory(_settings: object) -> _StubProvider:
        return provider

    monkeypatch.setattr("app.api.sessions.get_model_provider", _factory)
    return provider


async def test_sending_a_message_persists_and_returns_assistant_reply(
    client: AsyncClient, stub_provider: _StubProvider
) -> None:
    session = (await client.post("/api/sessions")).json()

    response = await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "How do I grow?"})

    assert response.status_code == 201
    body = response.json()
    assert body["message"]["content"] == "How do I grow?"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["content"] == "Focus on activation first."
    assert body["generation_error"] is None

    messages = (await client.get(f"/api/sessions/{session['id']}/messages")).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]


async def test_assistant_response_never_leaks_internal_fields(
    client: AsyncClient, stub_provider: _StubProvider
) -> None:
    session = (await client.post("/api/sessions")).json()
    response = await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "hi"})
    body = response.json()

    allowed_keys = {"id", "session_id", "role", "content", "created_at", "sources", "grounded"}
    assert set(body["assistant_message"].keys()) == allowed_keys
    assert set(body["message"].keys()) == allowed_keys
    # This test's stub provider never grounds anything - no fabricated sources.
    assert body["assistant_message"]["sources"] == []
    assert body["assistant_message"]["grounded"] is False


async def test_session_context_is_sent_to_the_provider(client: AsyncClient, stub_provider: _StubProvider) -> None:
    session = (await client.post("/api/sessions")).json()
    await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "What is a good onboarding flow?"})
    await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "How does that change for B2B?"})

    # The second call's context includes the first turn's user + assistant messages.
    second_call_context = stub_provider.calls[-1]
    contents = [m["content"] for m in second_call_context]
    assert "What is a good onboarding flow?" in contents
    assert "Focus on activation first." in contents
    assert contents[-1] == "How does that change for B2B?"


async def test_session_context_never_crosses_sessions(client: AsyncClient, stub_provider: _StubProvider) -> None:
    session_a = (await client.post("/api/sessions")).json()
    session_b = (await client.post("/api/sessions")).json()

    await client.post(f"/api/sessions/{session_a['id']}/messages", json={"content": "message only in A"})
    await client.post(f"/api/sessions/{session_b['id']}/messages", json={"content": "message only in B"})

    last_call_context = stub_provider.calls[-1]
    contents = [m["content"] for m in last_call_context]
    assert "message only in A" not in contents
    assert "message only in B" in contents


async def test_generation_failure_keeps_user_message_and_reports_safe_error(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _StubProvider(error=ProviderUnavailableError("Local model unavailable."))
    monkeypatch.setattr("app.api.sessions.get_model_provider", lambda _settings: provider)

    session = (await client.post("/api/sessions")).json()
    response = await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "hello"})

    assert response.status_code == 201
    body = response.json()
    assert body["message"]["content"] == "hello"
    assert body["assistant_message"] is None
    assert body["generation_error"]["code"] == "provider_unavailable"

    messages = (await client.get(f"/api/sessions/{session['id']}/messages")).json()
    assert [m["role"] for m in messages] == ["user"]


async def test_retry_regenerates_without_duplicating_user_message(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    failing_provider = _StubProvider(error=ModelTimeoutError())
    monkeypatch.setattr("app.api.sessions.get_model_provider", lambda _settings: failing_provider)

    session = (await client.post("/api/sessions")).json()
    await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "hello"})

    recovering_provider = _StubProvider(content="Sorry about that - here's an answer.")
    monkeypatch.setattr("app.api.sessions.get_model_provider", lambda _settings: recovering_provider)

    retry_response = await client.post(f"/api/sessions/{session['id']}/messages/retry")
    assert retry_response.status_code == 200
    body = retry_response.json()
    assert body["assistant_message"]["content"] == "Sorry about that - here's an answer."
    assert "message" not in body

    messages = (await client.get(f"/api/sessions/{session['id']}/messages")).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert sum(1 for m in messages if m["role"] == "user") == 1


async def test_retry_without_a_pending_message_is_rejected(client: AsyncClient, stub_provider: _StubProvider) -> None:
    session = (await client.post("/api/sessions")).json()
    await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "hello"})

    # The first send already succeeded (stub_provider always succeeds), so
    # there is no reply-less user message left to retry.
    response = await client.post(f"/api/sessions/{session['id']}/messages/retry")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "nothing_to_retry"


async def test_provider_status_reflects_active_configuration(client: AsyncClient) -> None:
    response = await client.get("/api/provider")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"
    assert body["model"]
