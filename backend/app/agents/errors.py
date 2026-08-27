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


class RetrievalError(AgentError):
    """The knowledge base could not be searched (e.g. a database failure).

    Distinct from an *empty* retrieval result (no relevant material
    found, which is a normal outcome the agent handles by proceeding
    without grounding - see ``docs/architecture.md`` "Empty retrieval").
    This is a real failure and must surface as one, not silently become
    an ungrounded answer with no indication anything went wrong.
    """

    code = "retrieval_failed"
    message = "Couldn't search the Lenny knowledge base. Please try again."
