"""Cloud model provider backed by the Anthropic Claude API.

Uses the official ``anthropic`` Python SDK's Messages API - the
standard, production-appropriate way to call Claude (see
``docs/architecture.md`` for why this was chosen over the Claude Agent
SDK / Claude Code harness, which targets autonomous coding/computer-use
agents rather than a conversational product-advice assistant).
"""

from __future__ import annotations

import time

import anthropic

from app.agents.errors import (
    EmptyResponseError,
    MissingCredentialsError,
    ModelNotFoundError,
    ModelTimeoutError,
    ProviderUnavailableError,
)
from app.services.model_providers.base import ModelProvider, ProviderMessage, ProviderResponse

MAX_RESPONSE_TOKENS = 2048


class AnthropicProvider(ModelProvider):
    provider_name = "cloud"

    def __init__(self, *, api_key: str | None, model: str, timeout_seconds: float) -> None:
        if not api_key:
            raise MissingCredentialsError(
                "Cloud provider is not configured. Set CLOUD_API_KEY in your environment."
            )
        self.model_name = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_seconds)

    async def generate(self, *, system: str, messages: list[ProviderMessage]) -> ProviderResponse:
        start = time.monotonic()
        try:
            response = await self._client.messages.create(
                model=self.model_name,
                max_tokens=MAX_RESPONSE_TOKENS,
                system=system,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],
                output_config={"effort": "medium"},
            )
        except anthropic.AuthenticationError as exc:
            raise MissingCredentialsError("Cloud provider rejected the configured API key.") from exc
        except anthropic.APITimeoutError as exc:
            raise ModelTimeoutError() from exc
        except anthropic.NotFoundError as exc:
            raise ModelNotFoundError(f"The configured cloud model '{self.model_name}' was not found.") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderUnavailableError("Couldn't reach the cloud provider.") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderUnavailableError("The cloud provider is rate-limiting requests. Please try again shortly.") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderUnavailableError(f"Cloud provider error (HTTP {exc.status_code}).") from exc

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise EmptyResponseError()

        latency_ms = int((time.monotonic() - start) * 1000)
        return ProviderResponse(content=text, model=response.model, latency_ms=latency_ms)
