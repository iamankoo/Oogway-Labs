"""Local model provider backed by a running Ollama instance.

This is the mandatory demo provider (see ``docs/architecture.md`` and the
root ``README.md`` for how to pull a model into the Ollama container).
Talks to Ollama's own REST API directly over HTTP - there is no official
Ollama Python SDK, and a thin ``httpx`` client is the appropriate amount
of integration for one endpoint (``POST /api/chat``).
"""

from __future__ import annotations

import time

import httpx

from app.agents.errors import EmptyResponseError, ModelNotFoundError, ModelTimeoutError, ProviderUnavailableError
from app.services.model_providers.base import ModelProvider, ProviderMessage, ProviderResponse

# Bounds response length so CPU-only local inference has a predictable
# latency ceiling - without this, Ollama has no output limit and a
# thorough answer can run long enough to blow past any reasonable
# request timeout. ~400 tokens is comfortably enough for the concise
# answers SYSTEM_PROMPT asks for.
MAX_RESPONSE_TOKENS = 400


class OllamaProvider(ModelProvider):
    provider_name = "ollama"

    def __init__(self, *, base_url: str, model: str, timeout_seconds: float) -> None:
        self.model_name = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def generate(self, *, system: str, messages: list[ProviderMessage]) -> ProviderResponse:
        payload = {
            "model": self.model_name,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
            "options": {"num_predict": MAX_RESPONSE_TOKENS},
        }

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
        except httpx.TimeoutException as exc:
            raise ModelTimeoutError() from exc
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(
                f"Local model unavailable. Check that Ollama is running at {self._base_url}."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError() from exc

        if response.status_code == 404 or "not found" in response.text.lower():
            raise ModelNotFoundError(
                f"The configured Ollama model '{self.model_name}' isn't installed. "
                f"Run: docker compose exec ollama ollama pull {self.model_name}"
            )
        if response.status_code >= 400:
            raise ProviderUnavailableError(f"Ollama returned an error (HTTP {response.status_code}).")

        data = response.json()
        content = (data.get("message") or {}).get("content", "").strip()
        if not content:
            raise EmptyResponseError()

        latency_ms = int((time.monotonic() - start) * 1000)
        return ProviderResponse(content=content, model=self.model_name, latency_ms=latency_ms)
