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
    # assistant response. The ORM's MessageRole still supports all three
    # for when Phase 3 starts writing assistant messages server-side.
    role: Literal["user"] = "user"
    content: str = Field(min_length=1, max_length=8000)


class MessageCreateResponse(BaseModel):
    message: MessageOut
    session: SessionOut
