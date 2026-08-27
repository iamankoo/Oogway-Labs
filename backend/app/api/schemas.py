"""Pydantic request/response models for the conversation API.

Kept separate from the ORM models in ``app.db.models`` so the API's
public shape (what fields exist, what's required) can evolve
independently of storage - and so internal database details are never
accidentally serialized to a client.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceOut(BaseModel):
    """One citation for an assistant message - always traced back to an
    actual retrieved chunk (``app.db.knowledge_models.MessageSource``),
    never parsed from the model's own text. A field is omitted (``None``),
    never invented, when the source repository didn't actually provide it.
    """

    source_id: uuid.UUID
    source_type: Literal["podcast", "newsletter"]
    title: str
    guest: str | None
    published_at: date | None
    source_url: str | None
    excerpt: str
    relevance: float

    @classmethod
    def from_message_source(cls, source: "MessageSource") -> "SourceOut":  # noqa: F821
        """Build from the ORM row explicitly - its primary key is ``id``,
        not ``source_id``, so a plain ``model_validate(source)`` would not
        map correctly; this keeps that mapping in one obvious place.
        """
        return cls(
            source_id=source.id,
            source_type=source.source_type,
            title=source.title,
            guest=source.guest,
            published_at=source.published_at,
            source_url=source.source_url,
            excerpt=source.excerpt,
            relevance=source.relevance,
        )


class MessageOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime
    # Populated only for a grounded assistant message; [] for every other
    # message (user/system messages, and assistant messages where
    # retrieval found no supporting material).
    sources: list[SourceOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[misc]
    @property
    def grounded(self) -> bool:
        """True only when retrieval actually found supporting material.

        Drives the frontend's "grounded in Lenny's Podcast" indicator -
        never shown for an ungrounded response, never a fake badge.
        """
        return len(self.sources) > 0

    @classmethod
    def from_message(cls, message: "Message") -> "MessageOut":  # noqa: F821
        """Build from the ORM row, mapping ``message.sources`` explicitly
        (see ``SourceOut.from_message_source`` for why a plain
        ``model_validate`` isn't used for the nested list).
        """
        return cls(
            id=message.id,
            session_id=message.session_id,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
            sources=[SourceOut.from_message_source(s) for s in message.sources],
        )


class MessageCreate(BaseModel):
    # Only "user" is accepted here - assistant/system messages are never
    # client-supplied, so the API can't be used to fabricate a fake
    # assistant response. The agent layer is the only thing that ever
    # creates an assistant message, server-side, after a real generation.
    role: Literal["user"] = "user"
    content: str = Field(min_length=1, max_length=8000)


class GenerationError(BaseModel):
    """A safe, user-facing description of why assistant generation failed.

    Never carries provider exception details, stack traces, or secrets -
    see ``app.agents.errors`` for the taxonomy this is built from.
    """

    code: str
    message: str


class MessageCreateResponse(BaseModel):
    message: MessageOut
    # Present only when generation succeeded. Never a fabricated message -
    # absent (not a placeholder) whenever generation_error is set.
    assistant_message: MessageOut | None = None
    session: SessionOut
    generation_error: GenerationError | None = None


class RetryResponse(BaseModel):
    """Response for regenerating a reply to an existing user message.

    No ``message`` field - retry never creates or re-returns a user
    message, only a new assistant attempt (or another error).
    """

    assistant_message: MessageOut | None = None
    session: SessionOut
    generation_error: GenerationError | None = None


class ProviderStatusOut(BaseModel):
    """Reflects the backend's actual active configuration - never fake state."""

    provider: Literal["ollama", "cloud"]
    model: str


class ArtifactCreate(BaseModel):
    """Requests generation of one artifact from the session's conversation.

    ``kind`` selects the generator (Phase 5): ``ship30`` (a ~1,250-word
    grounded essay), ``markdown`` (a structured Markdown summary/doc), or
    ``html`` (a self-contained HTML/CSS document). ``topic`` optionally
    focuses the generator; when omitted, the session's own conversation
    is the topic.
    """

    kind: Literal["ship30", "markdown", "html"]
    topic: str | None = Field(default=None, max_length=500)


class ArtifactOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    title: str
    kind: Literal["ship30", "markdown", "html"]
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArtifactCreateResponse(BaseModel):
    """Same never-fabricate contract as ``MessageCreateResponse``: on
    failure ``artifact`` is absent (not a placeholder) and
    ``generation_error`` carries a safe, user-facing reason.
    """

    artifact: ArtifactOut | None = None
    generation_error: GenerationError | None = None
