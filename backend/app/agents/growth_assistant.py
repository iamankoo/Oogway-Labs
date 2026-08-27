"""The Lenny Growth Assistant agent.

This wraps ``pi_agent.agent.Agent`` - the required agent framework (see
``docs/architecture.md`` "Agent framework choice") - configured with
**zero coding tools**: this is a conversational product/growth advisor,
not a coding agent, so the tool registry is intentionally empty. With no
tools to call, pi-agent's ReAct loop takes exactly one turn per user
message (there is nothing for the model to call, so
``response.tool_calls`` is always empty and the loop returns
immediately) - a deliberate, documented choice, not a limitation. Phase
4/5 tool integrations (retrieval, artifacts) add real ``Tool`` entries to
the registry without changing this class's shape.

pi-agent owns the actual agent-level behavior this class delegates to:
the model turn itself, transient-error retry with backoff, and
conversation-history trimming (``AgentConfig.max_history_messages``).
This class's own job is narrower: translate between this application's
``Message`` ORM rows and pi-agent's neutral transcript, enforce an
overall wall-clock timeout (pi-agent's client calls are synchronous), and
normalize whatever exceptions surface into this application's own
``AgentError`` taxonomy.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from dataclasses import dataclass

import anthropic
import openai
from pi_agent.agent import Agent as PiAgent
from pi_agent.config import AgentConfig
from pi_agent.llm import LLMProvider
from pi_agent.sandbox import Sandbox
from pi_agent.tools.registry import ToolRegistry

from app.agents.errors import (
    EmptyResponseError,
    ModelNotFoundError,
    ModelTimeoutError,
    ProviderUnavailableError,
)
from app.agents.prompts import SYSTEM_PROMPT
from app.db.models import Message, MessageRole


@dataclass(frozen=True)
class AgentResult:
    content: str
    provider: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


def _map_provider_exception(exc: Exception) -> Exception:
    """Translate an openai/anthropic SDK exception into an AgentError.

    Both SDKs (pi-agent's Ollama path goes through ``openai``, its cloud
    path through ``anthropic``) expose parallel exception hierarchies, so
    one mapping covers either provider.
    """
    if isinstance(exc, (openai.APITimeoutError, anthropic.APITimeoutError)):
        return ModelTimeoutError()
    if isinstance(exc, (openai.NotFoundError, anthropic.NotFoundError)):
        return ModelNotFoundError()
    if isinstance(exc, (openai.AuthenticationError, anthropic.AuthenticationError)):
        return ProviderUnavailableError("The configured credentials were rejected.")
    if isinstance(exc, (openai.APIConnectionError, anthropic.APIConnectionError)):
        return ProviderUnavailableError()
    if isinstance(exc, (openai.APIStatusError, anthropic.APIStatusError)):
        return ProviderUnavailableError(f"The model provider returned an error (HTTP {exc.status_code}).")
    return exc


class GrowthAssistantAgent:
    def __init__(self, provider: LLMProvider, *, max_context_messages: int, timeout_seconds: float) -> None:
        self._provider = provider
        self._max_context_messages = max_context_messages
        self._timeout_seconds = timeout_seconds

    def _build_pi_agent(self, history: list[Message]) -> tuple[PiAgent, str]:
        relevant = [m for m in history if m.role in (MessageRole.user, MessageRole.assistant)]
        if not relevant or relevant[-1].role != MessageRole.user:
            raise ValueError("respond() requires the last message in history to be a pending user turn")

        prior, latest = relevant[:-1], relevant[-1]
        neutral_history = [{"role": m.role.value, "content": m.content} for m in prior]

        agent = PiAgent(
            provider=self._provider,
            # No coding tools - see module docstring. An empty registry means
            # the model is never even told it can call a tool, so it always
            # answers in a single turn.
            registry=ToolRegistry([]),
            # Never resolved (no tools registered to resolve a path), but the
            # framework's Agent requires one.
            sandbox=Sandbox(tempfile.gettempdir()),
            config=AgentConfig(
                system_prompt=SYSTEM_PROMPT,
                max_iterations=1,
                auto_approve=True,
                stream=False,
                reflect=False,
                max_retries=3,
                max_history_messages=self._max_context_messages,
            ),
            messages=neutral_history,
        )
        return agent, latest.content

    async def respond(self, history: list[Message]) -> AgentResult:
        agent, latest_content = self._build_pi_agent(history)

        start = time.monotonic()
        try:
            # pi-agent's provider clients are synchronous - run the (blocking)
            # agent loop in a thread so it doesn't stall the event loop, and
            # enforce our own wall-clock timeout around it.
            content = await asyncio.wait_for(
                asyncio.to_thread(agent.run, latest_content), timeout=self._timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            raise ModelTimeoutError() from exc
        except Exception as exc:  # noqa: BLE001 - normalized immediately below
            raise _map_provider_exception(exc) from exc

        if not content or not content.strip():
            raise EmptyResponseError()

        latency_ms = int((time.monotonic() - start) * 1000)
        return AgentResult(
            content=content,
            provider=self._provider.name,
            model=self._provider.model,
            latency_ms=latency_ms,
            input_tokens=agent.total_usage.input_tokens,
            output_tokens=agent.total_usage.output_tokens,
        )
