"""Data-access layer for sessions and messages.

Every function here takes an explicit ``user_id`` and scopes its query
accordingly - session isolation is enforced here, in the data-access
layer, rather than trusted to callers. A session that does not belong to
the given user is treated exactly like a session that does not exist
(``SessionNotFoundError``), so callers cannot distinguish "not yours"
from "not found" and leak information about other users' data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import SessionNotFoundError
from app.db.models import ChatSession, Message, MessageRole

TITLE_MAX_LENGTH = 60
DEFAULT_TITLE = "New conversation"


def _derive_title_from_content(content: str) -> str:
    """Deterministically derive a session title from the first user message.

    No LLM/summarization involved - just a clean truncation, matching the
    Phase 2 requirement to avoid fabricated AI-generated summaries.
    """
    collapsed = " ".join(content.split())
    if len(collapsed) <= TITLE_MAX_LENGTH:
        return collapsed or DEFAULT_TITLE
    return collapsed[:TITLE_MAX_LENGTH].rstrip() + "…"


async def create_session(db: AsyncSession, *, user_id: uuid.UUID) -> ChatSession:
    session = ChatSession(user_id=user_id, title=DEFAULT_TITLE)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(db: AsyncSession, *, user_id: uuid.UUID) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_session(db: AsyncSession, *, user_id: uuid.UUID, session_id: uuid.UUID) -> ChatSession:
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise SessionNotFoundError()
    return session


async def list_messages(db: AsyncSession, *, user_id: uuid.UUID, session_id: uuid.UUID) -> list[Message]:
    # Confirms the session belongs to this user before touching messages -
    # this is the check that keeps session A's messages from leaking to
    # a caller who only knows session B's id.
    await get_session(db, user_id=user_id, session_id=session_id)
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return list(result.scalars().all())


class NothingToRetryError(Exception):
    """Raised when a session has no pending (reply-less) user message."""


async def get_message_pending_retry(db: AsyncSession, *, user_id: uuid.UUID, session_id: uuid.UUID) -> Message:
    """Return the user message that should be regenerated for.

    Retry semantics: only the session's most recent message may be
    retried, and only if it's a user message that has no assistant reply
    after it yet (i.e. the previous generation attempt failed or never
    ran). This is what prevents a retry from ever duplicating a user
    message - it never creates one, it only re-runs generation for the
    one that's already there.
    """
    history = await list_messages(db, user_id=user_id, session_id=session_id)
    if not history or history[-1].role != MessageRole.user:
        raise NothingToRetryError()
    return history[-1]


async def create_message(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    role: MessageRole,
    content: str,
    metadata: dict | None = None,
) -> tuple[Message, ChatSession]:
    session = await get_session(db, user_id=user_id, session_id=session_id)

    message = Message(session_id=session_id, role=role, content=content, extra_metadata=metadata)
    db.add(message)

    if role == MessageRole.user and session.title == DEFAULT_TITLE:
        session.title = _derive_title_from_content(content)
    # Touch updated_at explicitly so the sidebar's "most recently active
    # first" ordering reflects new messages, not just title/metadata edits.
    session.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(message)
    await db.refresh(session)
    return message, session
