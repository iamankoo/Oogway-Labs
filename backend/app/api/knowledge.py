"""Knowledge base diagnostics (Phase 4).

An internal/operational endpoint, not part of the chat product surface -
it exists so an evaluator or operator can verify ingestion actually ran
(document/chunk counts, last ingestion time) without needing direct
database access. See ``docs/architecture.md`` "Knowledge health".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.knowledge_models import KnowledgeChunk, KnowledgeDocument, KnowledgeSourceType
from app.db.session import get_db

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class KnowledgeStatusOut(BaseModel):
    document_count: int
    chunk_count: int
    podcast_document_count: int
    newsletter_document_count: int
    last_ingested_at: str | None


@router.get("/status", response_model=KnowledgeStatusOut)
async def knowledge_status(db: AsyncSession = Depends(get_db)) -> KnowledgeStatusOut:
    document_count = (await db.execute(select(func.count()).select_from(KnowledgeDocument))).scalar_one()
    chunk_count = (await db.execute(select(func.count()).select_from(KnowledgeChunk))).scalar_one()
    podcast_count = (
        await db.execute(
            select(func.count())
            .select_from(KnowledgeDocument)
            .where(KnowledgeDocument.source_type == KnowledgeSourceType.podcast)
        )
    ).scalar_one()
    newsletter_count = (
        await db.execute(
            select(func.count())
            .select_from(KnowledgeDocument)
            .where(KnowledgeDocument.source_type == KnowledgeSourceType.newsletter)
        )
    ).scalar_one()
    last_ingested_at = (await db.execute(select(func.max(KnowledgeDocument.updated_at)))).scalar_one_or_none()

    return KnowledgeStatusOut(
        document_count=document_count,
        chunk_count=chunk_count,
        podcast_document_count=podcast_count,
        newsletter_document_count=newsletter_count,
        last_ingested_at=last_ingested_at.isoformat() if last_ingested_at else None,
    )
