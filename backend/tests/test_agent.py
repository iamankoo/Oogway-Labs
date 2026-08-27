from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

import httpx
import openai
import pytest
from pi_agent.llm import AssistantResponse, NeutralMessage, Usage

from app.agents.errors import (
    EmptyResponseError,
    ModelNotFoundError,
    ModelTimeoutError,
    ProviderUnavailableError,
    RetrievalError,
)
from app.agents.growth_assistant import GrowthAssistantAgent
from app.db.models import Message, MessageRole
from app.services.knowledge_retriever import RetrievedChunk


def _message(role: MessageRole, content: str) -> Message:
    return Message(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc),
    )


def _chunk(*, title: str = "A Test Episode", guest: str | None = "A Test Guest", text: str = "some excerpt") -> RetrievedChunk:
    """A synthetic RetrievedChunk for tests only - never real Lenny content."""
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        source_type="podcast",
        title=title,
        guest=guest,
        published_at=date(2026, 1, 1),
        source_url="https://example.com/episode",
        text=text,
        relevance=0.42,
    )


class _RecordingProvider:
    """A fake conforming to pi_agent.llm.LLMProvider - no network access."""

    name = "fake"
    model = "fake-model"
    supports_streaming = False

    def __init__(self, *, text: str = "a reasonable answer") -> None:
        self._text = text
        self.received_system: str | None = None
        self.received_messages: list[NeutralMessage] | None = None

    def complete(
        self, system: str, messages: list[NeutralMessage], tools: list[dict[str, Any]]
    ) -> AssistantResponse:
        self.received_system = system
        # Copy: pi_agent.Agent appends the assistant reply to this same list
        # object right after complete() returns.
        self.received_messages = list(messages)
        return AssistantResponse(text=self._text, usage=Usage(input_tokens=11, output_tokens=7))


class _HangingProvider:
    name = "fake"
    model = "fake-model"
    supports_streaming = False

    def complete(
        self, system: str, messages: list[NeutralMessage], tools: list[dict[str, Any]]
    ) -> AssistantResponse:
        import time

        time.sleep(2)
        raise AssertionError("should have timed out before completing")


class _RaisingProvider:
    name = "fake"
    model = "fake-model"
    supports_streaming = False

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def complete(
        self, system: str, messages: list[NeutralMessage], tools: list[dict[str, Any]]
    ) -> AssistantResponse:
        raise self._exc


class _FakeRetriever:
    """A fake conforming to KnowledgeRetriever's interface - no database access."""

    def __init__(self, results: list[RetrievedChunk] | None = None, *, error: Exception | None = None) -> None:
        self._results = results if results is not None else []
        self._error = error
        self.received_queries: list[str] = []

    async def search(self, query: str) -> list[RetrievedChunk]:
        self.received_queries.append(query)
        if self._error:
            raise self._error
        return self._results


async def test_agent_puts_the_required_framework_in_the_execution_path() -> None:
    """GrowthAssistantAgent must actually drive a pi_agent.agent.Agent, not
    merely wrap a provider itself - this is the crux of the Phase 3 fix.
    """
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, _FakeRetriever(), max_context_messages=20, timeout_seconds=5)

    pi_agent, latest = agent._build_pi_agent([_message(MessageRole.user, "What is PMF?")], system_prompt="sys")

    from pi_agent.agent import Agent as PiAgent

    assert isinstance(pi_agent, PiAgent)
    assert pi_agent.provider is provider
    assert latest == "What is PMF?"


async def test_agent_returns_provider_result() -> None:
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, _FakeRetriever(), max_context_messages=20, timeout_seconds=5)

    result = await agent.respond([_message(MessageRole.user, "What is PMF?")])

    assert result.content == "a reasonable answer"
    assert result.provider == "fake"
    assert result.model == "fake-model"
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert result.sources == []


async def test_agent_excludes_system_messages_from_context() -> None:
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, _FakeRetriever(), max_context_messages=20, timeout_seconds=5)

    await agent.respond(
        [
            _message(MessageRole.system, "session started"),
            _message(MessageRole.user, "hello"),
        ]
    )

    # "hello" is the pending turn passed to agent.run(); the system message
    # never enters the neutral transcript at all.
    assert provider.received_messages == [{"role": "user", "content": "hello"}]


async def test_agent_seeds_pi_agent_history_from_prior_turns() -> None:
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, _FakeRetriever(), max_context_messages=20, timeout_seconds=5)

    await agent.respond(
        [
            _message(MessageRole.user, "first question"),
            _message(MessageRole.assistant, "first answer"),
            _message(MessageRole.user, "second question"),
        ]
    )

    assert provider.received_messages == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
        {"role": "user", "content": "second question"},
    ]


async def test_agent_caps_context_to_max_messages() -> None:
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, _FakeRetriever(), max_context_messages=2, timeout_seconds=5)

    history = [_message(MessageRole.user, f"message {i}") for i in range(5)]
    result = await agent.respond(history)

    assert result.content == "a reasonable answer"


async def test_agent_raises_timeout_when_provider_hangs() -> None:
    agent = GrowthAssistantAgent(_HangingProvider(), _FakeRetriever(), max_context_messages=20, timeout_seconds=0.05)

    with pytest.raises(ModelTimeoutError):
        await agent.respond([_message(MessageRole.user, "hi")])


async def test_agent_raises_empty_response_error() -> None:
    provider = _RecordingProvider(text="   ")
    agent = GrowthAssistantAgent(provider, _FakeRetriever(), max_context_messages=20, timeout_seconds=5)

    with pytest.raises(EmptyResponseError):
        await agent.respond([_message(MessageRole.user, "hi")])


_FAKE_REQUEST = httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
_FAKE_RESPONSE = httpx.Response(404, request=_FAKE_REQUEST)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (openai.NotFoundError("not found", response=_FAKE_RESPONSE, body=None), ModelNotFoundError),
        (openai.APIConnectionError(request=_FAKE_REQUEST), ProviderUnavailableError),
    ],
)
async def test_agent_maps_openai_exceptions_to_agent_errors(exc: Exception, expected: type) -> None:
    agent = GrowthAssistantAgent(_RaisingProvider(exc), _FakeRetriever(), max_context_messages=20, timeout_seconds=5)

    with pytest.raises(expected):
        await agent.respond([_message(MessageRole.user, "hi")])


# --- Phase 4: retrieval + grounding integration -----------------------------


async def test_agent_grounds_the_system_prompt_with_retrieved_chunks() -> None:
    provider = _RecordingProvider()
    chunk = _chunk(title="Growth Loops 101", guest="Jane Doe", text="the key insight is retention first")
    agent = GrowthAssistantAgent(provider, _FakeRetriever([chunk]), max_context_messages=20, timeout_seconds=5)

    await agent.respond([_message(MessageRole.user, "How do growth loops work?")])

    assert provider.received_system is not None
    assert "Growth Loops 101" in provider.received_system
    assert "Jane Doe" in provider.received_system
    assert "the key insight is retention first" in provider.received_system
    assert "<retrieved_lenny_material>" in provider.received_system


async def test_agent_tells_the_model_when_no_material_was_found() -> None:
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, _FakeRetriever([]), max_context_messages=20, timeout_seconds=5)

    await agent.respond([_message(MessageRole.user, "What is quantum computing?")])

    assert provider.received_system is not None
    assert "No relevant material was found" in provider.received_system
    # No fabricated episode/guest content should appear when nothing was retrieved.
    assert "Growth Loops 101" not in provider.received_system


async def test_agent_result_sources_are_exactly_what_retrieval_returned() -> None:
    """Citation integrity: AgentResult.sources must be the retriever's own
    objects, never something derived from the model's text output.
    """
    provider = _RecordingProvider(text="Retention matters most [1].")
    chunk = _chunk()
    agent = GrowthAssistantAgent(provider, _FakeRetriever([chunk]), max_context_messages=20, timeout_seconds=5)

    result = await agent.respond([_message(MessageRole.user, "How do I grow?")])

    assert result.sources == [chunk]


async def test_agent_query_uses_only_current_message_on_first_turn() -> None:
    retriever = _FakeRetriever([])
    agent = GrowthAssistantAgent(_RecordingProvider(), retriever, max_context_messages=20, timeout_seconds=5)

    await agent.respond([_message(MessageRole.user, "What makes onboarding effective?")])

    assert retriever.received_queries == ["What makes onboarding effective?"]


async def test_agent_query_incorporates_prior_user_turn_for_follow_up() -> None:
    """Follow-up retrieval strategy: the immediately preceding user message
    is folded into the query so a short follow-up like "How about B2B?"
    still carries the topic ("onboarding") that resolves it.
    """
    retriever = _FakeRetriever([])
    agent = GrowthAssistantAgent(_RecordingProvider(), retriever, max_context_messages=20, timeout_seconds=5)

    await agent.respond(
        [
            _message(MessageRole.user, "What makes onboarding effective?"),
            _message(MessageRole.assistant, "Clear activation moments."),
            _message(MessageRole.user, "How about for B2B?"),
        ]
    )

    assert retriever.received_queries == ["What makes onboarding effective? How about for B2B?"]


async def test_agent_raises_retrieval_error_on_search_failure() -> None:
    """A real retrieval failure (e.g. a database error) must surface as an
    error, not silently become an ungrounded-but-apparently-fine answer.
    """
    retriever = _FakeRetriever(error=RuntimeError("database exploded"))
    agent = GrowthAssistantAgent(_RecordingProvider(), retriever, max_context_messages=20, timeout_seconds=5)

    with pytest.raises(RetrievalError):
        await agent.respond([_message(MessageRole.user, "hi")])
