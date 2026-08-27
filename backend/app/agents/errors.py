"""Agent/generation error taxonomy.

These are distinct from ``app.core.errors.AppError``: an ``AgentError``
never becomes an HTTP error response on its own. A generation failure is
a *partial* failure - the user's message was already persisted - so the
API layer catches these and reports them as a ``generation_error`` field
inside an otherwise-successful response, rather than failing the whole
request. See ``app.api.sessions.create_message`` and
``docs/architecture.md`` ("Assistant generation failure semantics").
"""

from __future__ import annotations


class AgentError(Exception):
    """Base class for a failure to produce an assistant response."""

    code: str = "generation_error"
    message: str = "Something went wrong generating a response. Please try again."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class ProviderUnavailableError(AgentError):
    code = "provider_unavailable"
    message = "The model provider is unavailable. Please try again shortly."


class ModelNotFoundError(AgentError):
    code = "model_not_found"
    message = "The configured model isn't available."


class MissingCredentialsError(AgentError):
    code = "missing_credentials"
    message = "The cloud provider isn't configured."


class ModelTimeoutError(AgentError):
    code = "model_timeout"
    message = "The model took too long to respond. Please try again."


class EmptyResponseError(AgentError):
    code = "empty_response"
    message = "The model returned an empty response. Please try again."
