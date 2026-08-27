"""Selects a ``pi_agent.llm.LLMProvider`` from configuration.

This is the only place that branches on ``Settings.llm_provider``. A new
provider is added by writing a small ``build_provider``-style branch here
- nothing else in the agent or API layer changes.

Both branches build a real provider from ``pi-coding-agent`` (the
required agent framework's own provider abstraction - see
``docs/architecture.md`` "Agent framework choice"):

- ``ollama``: ``pi_agent.llm.OpenAIProvider`` pointed at Ollama's
  OpenAI-compatible endpoint (``/v1``). Ollama has no Anthropic-compatible
  endpoint, so this is the framework's own documented mechanism for
  reaching a local model - not a workaround invented here.
- ``cloud``: ``pi_agent.llm.AnthropicProvider``, talking to the real
  Anthropic Messages API.
"""

from __future__ import annotations

from pi_agent.llm import AnthropicProvider, LLMProvider, OpenAIProvider

from app.agents.errors import MissingCredentialsError
from app.config import Settings

# Bounds response length so CPU-only local inference has a predictable
# latency ceiling - see docs/architecture.md "Timeouts and retry" for the
# measurement this is based on.
OLLAMA_MAX_RESPONSE_TOKENS = 400
CLOUD_MAX_RESPONSE_TOKENS = 2048


def get_model_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OpenAIProvider(
            model=settings.ollama_model,
            # Ollama's OpenAI-compatible endpoint doesn't check the key, but
            # the OpenAI SDK requires a non-empty string to construct a client.
            api_key="ollama",
            base_url=f"{settings.ollama_base_url.rstrip('/')}/v1",
            max_tokens=OLLAMA_MAX_RESPONSE_TOKENS,
        )
    if settings.llm_provider == "cloud":
        if not settings.cloud_api_key:
            raise MissingCredentialsError(
                "Cloud provider is not configured. Set CLOUD_API_KEY in your environment."
            )
        return AnthropicProvider(
            model=settings.cloud_model,
            api_key=settings.cloud_api_key,
            max_tokens=CLOUD_MAX_RESPONSE_TOKENS,
        )
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider!r}")
