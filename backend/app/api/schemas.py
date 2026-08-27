"""Pydantic request/response models for the conversation API.

Kept separate from the ORM models in ``app.db.models`` so the API's
public shape (what fields exist, what's required) can evolve
independently of storage - and so internal database details are never
accidentally serialized to a client.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


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
