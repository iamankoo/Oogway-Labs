"""Selects a ``ModelProvider`` from configuration.

This is the only place that branches on ``Settings.llm_provider``. A new
provider is added by writing a class and a branch here - nothing else in
the agent or API layer changes.
"""

from __future__ import annotations

from app.config import Settings
from app.services.model_providers.anthropic_provider import AnthropicProvider
from app.services.model_providers.base import ModelProvider
from app.services.model_providers.ollama_provider import OllamaProvider


def get_model_provider(settings: Settings) -> ModelProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.model_timeout_seconds,
        )
    if settings.llm_provider == "cloud":
        return AnthropicProvider(
            api_key=settings.cloud_api_key,
            model=settings.cloud_model,
            timeout_seconds=settings.model_timeout_seconds,
        )
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider!r}")
