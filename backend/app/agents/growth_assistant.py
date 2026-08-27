"""The Lenny Growth Assistant agent.

Owns the assistant's persona and turns a session's persisted message
history into a single provider call. This is the "agent" the API layer
talks to - it never talks to Ollama or Anthropic directly, and it never
touches the database (that stays in ``app.services.conversations``).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.agents.errors import ModelTimeoutError
from app.agents.prompts import SYSTEM_PROMPT
from app.db.models import Message, MessageRole
from app.services.model_providers.base import ModelProvider, ProviderMessage


@dataclass(frozen=True)
class AgentResult:
    content: str
    provider: str
    model: str
    latency_ms: int


class GrowthAssistantAgent:
    def __init__(self, provider: ModelProvider, *, max_context_messages: int, timeout_seconds: float) -> None:
        self._provider = provider
        self._max_context_messages = max_context_messages
        self._timeout_seconds = timeout_seconds

    def _build_context(self, history: list[Message]) -> list[ProviderMessage]:
        relevant = [m for m in history if m.role in (MessageRole.user, MessageRole.assistant)]
        recent = relevant[-self._max_context_messages :]
        return [{"role": m.role.value, "content": m.content} for m in recent]  # type: ignore[typeddict-item]

    async def respond(self, history: list[Message]) -> AgentResult:
        context = self._build_context(history)
        try:
            response = await asyncio.wait_for(
                self._provider.generate(system=SYSTEM_PROMPT, messages=context),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise ModelTimeoutError() from exc

        return AgentResult(
            content=response.content,
            provider=self._provider.provider_name,
            model=response.model,
            latency_ms=response.latency_ms,
        )
