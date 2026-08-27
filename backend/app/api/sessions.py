"""Session and message endpoints.

All endpoints operate on behalf of the single local demo user
(``app.db.models.DEMO_USER_ID``) - see that module's docstring for the
single-user rationale. There is no authentication in Phase 2.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MessageCreate, MessageCreateResponse, MessageOut, SessionOut
from app.db.models import DEMO_USER_ID, MessageRole
from app.db.session import get_db
from app.services import conversations

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(db: AsyncSession = Depends(get_db)) -> SessionOut:
    session = await conversations.create_session(db, user_id=DEMO_USER_ID)
    return SessionOut.model_validate(session)


@router.get("", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)) -> list[SessionOut]:
    sessions = await conversations.list_sessions(db, user_id=DEMO_USER_ID)
    return [SessionOut.model_validate(session) for session in sessions]


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> SessionOut:
    session = await conversations.get_session(db, user_id=DEMO_USER_ID, session_id=session_id)
    return SessionOut.model_validate(session)


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[MessageOut]:
    messages = await conversations.list_messages(db, user_id=DEMO_USER_ID, session_id=session_id)
    return [MessageOut.model_validate(message) for message in messages]


@router.post("/{session_id}/messages", response_model=MessageCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    session_id: uuid.UUID, payload: MessageCreate, db: AsyncSession = Depends(get_db)
) -> MessageCreateResponse:
    message, session = await conversations.create_message(
        db,
        user_id=DEMO_USER_ID,
        session_id=session_id,
        role=MessageRole(payload.role),
        content=payload.content,
    )
    return MessageCreateResponse(
        message=MessageOut.model_validate(message),
        session=SessionOut.model_validate(session),
    )
