from __future__ import annotations

import httpx
import pytest

from app.agents.errors import (
    EmptyResponseError,
    MissingCredentialsError,
    ModelNotFoundError,
    ModelTimeoutError,
    ProviderUnavailableError,
)
from app.config import Settings
from app.services.model_providers.anthropic_provider import AnthropicProvider
from app.services.model_providers.factory import get_model_provider
from app.services.model_providers.ollama_provider import OllamaProvider


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict, text: str = "") -> None:
        self.status_code = status_code
        self._json_body = json_body
        self.text = text or str(json_body)

    def json(self) -> dict:
        return self._json_body


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient, returning a scripted response or raising."""

    def __init__(self, response: _FakeResponse | None = None, raise_exc: Exception | None = None, **_kwargs) -> None:
        self._response = response
        self._raise_exc = raise_exc

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def post(self, *_args: object, **_kwargs: object) -> _FakeResponse:
        if self._raise_exc:
            raise self._raise_exc
        assert self._response is not None
        return self._response


def _patch_httpx_client(monkeypatch: pytest.MonkeyPatch, client: _FakeAsyncClient) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)


async def test_ollama_provider_returns_content_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _FakeResponse(200, {"message": {"content": "Here's an onboarding framework..."}})
    _patch_httpx_client(monkeypatch, _FakeAsyncClient(response=response))

    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2:3b", timeout_seconds=5)
    result = await provider.generate(system="be helpful", messages=[{"role": "user", "content": "hi"}])

    assert result.content == "Here's an onboarding framework..."
    assert result.model == "llama3.2:3b"
    assert result.latency_ms >= 0


async def test_ollama_provider_raises_model_not_found_on_404(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _FakeResponse(404, {"error": "model 'ghost:1b' not found, try pulling it first"})
    _patch_httpx_client(monkeypatch, _FakeAsyncClient(response=response))

    provider = OllamaProvider(base_url="http://localhost:11434", model="ghost:1b", timeout_seconds=5)
    with pytest.raises(ModelNotFoundError):
        await provider.generate(system="s", messages=[])


async def test_ollama_provider_raises_provider_unavailable_on_connect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx_client(
        monkeypatch, _FakeAsyncClient(raise_exc=httpx.ConnectError("refused", request=httpx.Request("POST", "http://x")))
    )

    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2:3b", timeout_seconds=5)
    with pytest.raises(ProviderUnavailableError):
        await provider.generate(system="s", messages=[])


async def test_ollama_provider_raises_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx_client(
        monkeypatch,
        _FakeAsyncClient(raise_exc=httpx.ReadTimeout("timed out", request=httpx.Request("POST", "http://x"))),
    )

    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2:3b", timeout_seconds=5)
    with pytest.raises(ModelTimeoutError):
        await provider.generate(system="s", messages=[])


async def test_ollama_provider_raises_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _FakeResponse(200, {"message": {"content": "   "}})
    _patch_httpx_client(monkeypatch, _FakeAsyncClient(response=response))

    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2:3b", timeout_seconds=5)
    with pytest.raises(EmptyResponseError):
        await provider.generate(system="s", messages=[])


def test_anthropic_provider_raises_missing_credentials_when_no_key() -> None:
    with pytest.raises(MissingCredentialsError):
        AnthropicProvider(api_key=None, model="claude-opus-5", timeout_seconds=5)


def test_anthropic_provider_constructs_with_key() -> None:
    provider = AnthropicProvider(api_key="sk-ant-fake", model="claude-opus-5", timeout_seconds=5)
    assert provider.provider_name == "cloud"
    assert provider.model_name == "claude-opus-5"


def test_factory_selects_ollama_by_default() -> None:
    settings = Settings(llm_provider="ollama", ollama_model="llama3.2:3b")
    provider = get_model_provider(settings)
    assert isinstance(provider, OllamaProvider)
    assert provider.model_name == "llama3.2:3b"


def test_factory_selects_cloud_when_configured() -> None:
    settings = Settings(llm_provider="cloud", cloud_api_key="sk-ant-fake", cloud_model="claude-opus-5")
    provider = get_model_provider(settings)
    assert isinstance(provider, AnthropicProvider)


def test_factory_cloud_without_key_raises_missing_credentials() -> None:
    settings = Settings(llm_provider="cloud", cloud_api_key=None)
    with pytest.raises(MissingCredentialsError):
        get_model_provider(settings)
