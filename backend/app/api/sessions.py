"""Session and message endpoints.

All endpoints operate on behalf of the single local demo user
(``app.db.models.DEMO_USER_ID``) - see that module's docstring for the
single-user rationale. There is no authentication in Phase 2/3.

Phase 3 adds real assistant generation to ``POST .../messages``: the
user's message is always persisted first, then the agent is invoked: on
success the assistant's reply is persisted too, on failure the response
carries a ``generation_error`` instead - the user's message is never
lost because of a model failure. See ``docs/architecture.md``
("Assistant generation failure semantics") for the full contract.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.errors import AgentError
from app.agents.growth_assistant import GrowthAssistantAgent
from app.api.schemas import (
    GenerationError,
    MessageCreate,
    MessageCreateResponse,
    MessageOut,
    RetryResponse,
    SessionOut,
)
from app.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import DEMO_USER_ID, Message, MessageRole
from app.db.session import get_db
from app.logging_config import get_logger
from app.services import conversations
from app.services.conversations import NothingToRetryError, get_message_pending_retry
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.model_providers.factory import get_model_provider

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = get_logger(__name__)


class NothingToRetryAppError(AppError):
    code = "nothing_to_retry"
    status_code = status.HTTP_409_CONFLICT
    message = "There's nothing to retry - this conversation already has a reply to its last message."


async def _generate_assistant_reply(
    db: AsyncSession, *, session_id: uuid.UUID, history: list[Message], settings: Settings
) -> tuple[Message | None, GenerationError | None]:
    """Invoke the agent and persist its reply, or return a safe error.

    Never raises - a generation failure is reported, not propagated, so
    the caller can still return the user's already-persisted message.
    """
    try:
        provider = get_model_provider(settings)
        retriever = KnowledgeRetriever(
            db, top_k=settings.knowledge_top_k, min_relevance=settings.knowledge_min_relevance
        )
        agent = GrowthAssistantAgent(
            provider,
            retriever,
            max_context_messages=settings.max_context_messages,
            timeout_seconds=settings.model_timeout_seconds,
        )
        result = await agent.respond(history)
    except AgentError as exc:
        logger.warning(
            "assistant_generation_failed",
            session_id=str(session_id),
            provider=settings.llm_provider,
            code=exc.code,
        )
        return None, GenerationError(code=exc.code, message=exc.message)

    assistant_message, _ = await conversations.create_message(
        db,
        user_id=DEMO_USER_ID,
        session_id=session_id,
        role=MessageRole.assistant,
        content=result.content,
        metadata={
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "status": "ok",
        },
        sources=result.sources,
    )
    logger.info(
        "assistant_generation_succeeded",
        session_id=str(session_id),
        provider=result.provider,
        model=result.model,
        latency_ms=result.latency_ms,
        retrieved_count=len(result.sources),
        source_ids=[str(s.chunk_id) for s in result.sources],
        relevance_scores=[s.relevance for s in result.sources],
    )
    return assistant_message, None


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
    return [MessageOut.from_message(message) for message in messages]


@router.post("/{session_id}/messages", response_model=MessageCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    session_id: uuid.UUID, payload: MessageCreate, db: AsyncSession = Depends(get_db)
) -> MessageCreateResponse:
    user_message, session = await conversations.create_message(
        db,
        user_id=DEMO_USER_ID,
        session_id=session_id,
        role=MessageRole(payload.role),
        content=payload.content,
    )

    history = await conversations.list_messages(db, user_id=DEMO_USER_ID, session_id=session_id)
    settings = get_settings()
    assistant_message, generation_error = await _generate_assistant_reply(
        db, session_id=session_id, history=history, settings=settings
    )
    if assistant_message is not None:
        session = await conversations.get_session(db, user_id=DEMO_USER_ID, session_id=session_id)

    return MessageCreateResponse(
        message=MessageOut.from_message(user_message),
        assistant_message=MessageOut.from_message(assistant_message) if assistant_message else None,
        session=SessionOut.model_validate(session),
        generation_error=generation_error,
    )


@router.post("/{session_id}/messages/retry", response_model=RetryResponse)
async def retry_message(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> RetryResponse:
    """Regenerate a reply for the session's pending user message.

    Never creates a new user message - see
    ``conversations.get_message_pending_retry`` for the exact semantics
    that keep this from ever duplicating a turn.
    """
    try:
        await get_message_pending_retry(db, user_id=DEMO_USER_ID, session_id=session_id)
    except NothingToRetryError as exc:
        raise NothingToRetryAppError() from exc

    history = await conversations.list_messages(db, user_id=DEMO_USER_ID, session_id=session_id)
    settings = get_settings()
    assistant_message, generation_error = await _generate_assistant_reply(
        db, session_id=session_id, history=history, settings=settings
    )
    session = await conversations.get_session(db, user_id=DEMO_USER_ID, session_id=session_id)

    return RetryResponse(
        assistant_message=MessageOut.from_message(assistant_message) if assistant_message else None,
        session=SessionOut.model_validate(session),
        generation_error=generation_error,
    )
