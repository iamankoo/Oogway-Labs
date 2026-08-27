from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from app.agents.errors import ModelTimeoutError
from app.agents.growth_assistant import GrowthAssistantAgent
from app.db.models import Message, MessageRole
from app.services.model_providers.base import ModelProvider, ProviderMessage, ProviderResponse


def _message(role: MessageRole, content: str) -> Message:
    return Message(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc),
    )


class _RecordingProvider(ModelProvider):
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self) -> None:
        self.received_messages: list[ProviderMessage] | None = None

    async def generate(self, *, system: str, messages: list[ProviderMessage]) -> ProviderResponse:
        self.received_messages = messages
        return ProviderResponse(content="a reasonable answer", model=self.model_name, latency_ms=42)


class _HangingProvider(ModelProvider):
    provider_name = "fake"
    model_name = "fake-model"

    async def generate(self, *, system: str, messages: list[ProviderMessage]) -> ProviderResponse:
        await asyncio.sleep(10)
        raise AssertionError("should have timed out before completing")


async def test_agent_returns_provider_result() -> None:
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, max_context_messages=20, timeout_seconds=5)

    result = await agent.respond([_message(MessageRole.user, "What is PMF?")])

    assert result.content == "a reasonable answer"
    assert result.provider == "fake"
    assert result.model == "fake-model"
    assert result.latency_ms == 42


async def test_agent_excludes_system_messages_from_context() -> None:
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, max_context_messages=20, timeout_seconds=5)

    await agent.respond(
        [
            _message(MessageRole.system, "session started"),
            _message(MessageRole.user, "hello"),
        ]
    )

    assert provider.received_messages == [{"role": "user", "content": "hello"}]


async def test_agent_caps_context_to_max_messages() -> None:
    provider = _RecordingProvider()
    agent = GrowthAssistantAgent(provider, max_context_messages=2, timeout_seconds=5)

    history = [_message(MessageRole.user, f"message {i}") for i in range(5)]
    await agent.respond(history)

    assert provider.received_messages is not None
    assert len(provider.received_messages) == 2
    assert provider.received_messages[-1]["content"] == "message 4"


async def test_agent_raises_timeout_when_provider_hangs() -> None:
    agent = GrowthAssistantAgent(_HangingProvider(), max_context_messages=20, timeout_seconds=0.05)

    with pytest.raises(ModelTimeoutError):
        await agent.respond([_message(MessageRole.user, "hi")])
