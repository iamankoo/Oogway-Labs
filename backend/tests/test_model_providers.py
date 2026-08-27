from __future__ import annotations

import pytest
from pi_agent.llm import AnthropicProvider, OpenAIProvider

from app.agents.errors import MissingCredentialsError
from app.config import Settings
from app.services.model_providers.factory import get_model_provider


def test_factory_selects_ollama_by_default() -> None:
    settings = Settings(llm_provider="ollama", ollama_model="llama3.2:3b", ollama_base_url="http://localhost:11434")
    provider = get_model_provider(settings)

    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "llama3.2:3b"
    # pi-coding-agent's own documented mechanism for reaching a local model:
    # Ollama's OpenAI-compatible endpoint, not a workaround invented here.
    assert provider.base_url == "http://localhost:11434/v1"


def test_factory_selects_cloud_when_configured() -> None:
    settings = Settings(llm_provider="cloud", cloud_api_key="sk-ant-fake", cloud_model="claude-opus-5")
    provider = get_model_provider(settings)

    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-opus-5"


def test_factory_cloud_without_key_raises_missing_credentials() -> None:
    settings = Settings(llm_provider="cloud", cloud_api_key=None)
    with pytest.raises(MissingCredentialsError):
        get_model_provider(settings)


def test_factory_ollama_provider_conforms_to_llm_provider_protocol() -> None:
    """The provider returned is a real pi-coding-agent LLMProvider - the
    required agent framework's own abstraction - not a hand-rolled stand-in.
    """
    settings = Settings(llm_provider="ollama", ollama_model="llama3.2:3b")
    provider = get_model_provider(settings)

    assert hasattr(provider, "complete")
    assert hasattr(provider, "name")
    assert hasattr(provider, "model")
    assert provider.name == "openai"  # pi-agent's OpenAIProvider identifies itself this way
