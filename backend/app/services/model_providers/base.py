"""The provider interface every model backend implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, TypedDict


class ProviderMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    model: str
    latency_ms: int


class ModelProvider(ABC):
    """A backend capable of generating a chat completion.

    Implementations must never leak provider-specific exceptions past
    ``generate`` - they should raise a subclass of
    ``app.agents.errors.AgentError`` instead, so the agent layer and API
    can handle every provider identically.
    """

    #: Short identifier surfaced to the frontend's provider indicator, e.g. "ollama" or "cloud".
    provider_name: str
    #: The concrete model name in use, e.g. "llama3.2:3b" or "claude-opus-5".
    model_name: str

    @abstractmethod
    async def generate(self, *, system: str, messages: list[ProviderMessage]) -> ProviderResponse:
        """Generate a single assistant turn given a system prompt and history."""
        raise NotImplementedError
