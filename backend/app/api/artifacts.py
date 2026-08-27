"""Artifact generation and retrieval endpoints (Phase 5).

Mirrors the assistant-generation contract from ``app.api.sessions``: the
generator either produces real content or the request reports a safe
``generation_error`` - it never returns a fabricated/placeholder
artifact, and a failure never crashes the request.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.errors import AgentError
from app.api.schemas import ArtifactCreate, ArtifactCreateResponse, ArtifactOut, GenerationError
from app.config import Settings, get_settings
from app.db.models import DEMO_USER_ID
from app.db.session import get_db
from app.logging_config import get_logger
from app.services import conversations
from app.services.artifact_generation import generate_html_doc, generate_markdown_doc, generate_ship30_essay
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.model_providers.factory import get_model_provider

router = APIRouter(prefix="/api/sessions", tags=["artifacts"])
logger = get_logger(__name__)

_GENERATORS = {
    "ship30": generate_ship30_essay,
    "markdown": generate_markdown_doc,
    "html": generate_html_doc,
}


@router.post(
    "/{session_id}/artifacts", response_model=ArtifactCreateResponse, status_code=status.HTTP_201_CREATED
)
async def create_artifact(
    session_id: uuid.UUID, payload: ArtifactCreate, db: AsyncSession = Depends(get_db)
) -> ArtifactCreateResponse:
    settings: Settings = get_settings()
    history = await conversations.list_messages(db, user_id=DEMO_USER_ID, session_id=session_id)

    try:
        provider = get_model_provider(settings, content_mode=True)
        retriever = KnowledgeRetriever(
            db, top_k=settings.knowledge_top_k, min_relevance=settings.knowledge_min_relevance
        )
        generate = _GENERATORS[payload.kind]
        result = await generate(
            provider=provider,
            retriever=retriever,
            history=history,
            topic=payload.topic,
            timeout_seconds=settings.artifact_timeout_seconds,
        )
    except AgentError as exc:
        logger.warning(
            "artifact_generation_failed", session_id=str(session_id), kind=payload.kind, code=exc.code
        )
        return ArtifactCreateResponse(generation_error=GenerationError(code=exc.code, message=exc.message))

    artifact = await conversations.create_artifact(
        db,
        user_id=DEMO_USER_ID,
        session_id=session_id,
        title=result.title,
        kind=payload.kind,
        content=result.content,
    )
    logger.info("artifact_generation_succeeded", session_id=str(session_id), kind=payload.kind, artifact_id=str(artifact.id))
    return ArtifactCreateResponse(artifact=ArtifactOut.model_validate(artifact))


@router.get("/{session_id}/artifacts", response_model=list[ArtifactOut])
async def list_session_artifacts(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[ArtifactOut]:
    artifacts = await conversations.list_artifacts(db, user_id=DEMO_USER_ID, session_id=session_id)
    return [ArtifactOut.model_validate(a) for a in artifacts]
