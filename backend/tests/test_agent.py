from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
)
from app.agents.growth_assistant import GrowthAssistantAgent
from app.db.models import Message, MessageRole


def _message(role: MessageRole, content: str) -> Message:
    return Message(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc),
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
        # object right after complete() returns, so a bare reference would
        # observe the mutation instead of what was actually sent.
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


async def test_agent_puts_the_required_framework_in_the_execution_path() -> None:
    """GrowthAssistantAgent must actually drive a pi_agent.agent.Agent, not
    merely wrap a provider itself - this is the crux of the compliance fix.
    """
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, max_context_messages=20, timeout_seconds=5)

    pi_agent, latest = agent._build_pi_agent([_message(MessageRole.user, "What is PMF?")])

    from pi_agent.agent import Agent as PiAgent

    assert isinstance(pi_agent, PiAgent)
    assert pi_agent.provider is provider
    assert latest == "What is PMF?"


async def test_agent_returns_provider_result() -> None:
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, max_context_messages=20, timeout_seconds=5)

    result = await agent.respond([_message(MessageRole.user, "What is PMF?")])

    assert result.content == "a reasonable answer"
    assert result.provider == "fake"
    assert result.model == "fake-model"
    assert result.input_tokens == 11
    assert result.output_tokens == 7


async def test_agent_excludes_system_messages_from_context() -> None:
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, max_context_messages=20, timeout_seconds=5)

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
    agent = GrowthAssistantAgent(provider, max_context_messages=20, timeout_seconds=5)

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
    agent = GrowthAssistantAgent(provider, max_context_messages=2, timeout_seconds=5)

    history = [_message(MessageRole.user, f"message {i}") for i in range(5)]
    result = await agent.respond(history)

    assert result.content == "a reasonable answer"


async def test_agent_raises_timeout_when_provider_hangs() -> None:
    agent = GrowthAssistantAgent(_HangingProvider(), max_context_messages=20, timeout_seconds=0.05)

    with pytest.raises(ModelTimeoutError):
        await agent.respond([_message(MessageRole.user, "hi")])


async def test_agent_raises_empty_response_error() -> None:
    provider = _RecordingProvider(text="   ")
    agent = GrowthAssistantAgent(provider, max_context_messages=20, timeout_seconds=5)

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
    agent = GrowthAssistantAgent(_RaisingProvider(exc), max_context_messages=20, timeout_seconds=5)

    with pytest.raises(expected):
        await agent.respond([_message(MessageRole.user, "hi")])
