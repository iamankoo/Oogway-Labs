"""ORM models for the Lenny knowledge base (Phase 4).

Kept separate from ``app.db.models`` (conversation persistence) because
these tables are a different bounded concern - ingested source material
and its chunks - populated by the offline ``app.knowledge.ingest`` CLI,
not by request handlers. Both files share the same ``Base``, so Alembic
autogenerate and ``Base.metadata.create_all`` (used by the test fixture)
see all tables regardless of which module defines them.

Schema, at a glance::

    knowledge_documents (1) ----< knowledge_chunks (many)
    messages (1) ----< message_sources (many) >---- knowledge_chunks (0..1)

``MessageSource`` intentionally denormalizes the citation fields it needs
to display (title, guest, published_at, source_url, excerpt) rather than
joining live through ``chunk_id`` at read time: a citation shown to a
user for a message generated last week must keep showing exactly what
was retrieved *then*, even if the corpus is later re-ingested and that
chunk's text or id changes or the chunk is deleted outright (hence
``ON DELETE SET NULL`` on ``chunk_id``/``document_id`` rather than
cascading delete). See ``docs/architecture.md`` "Source traceability".
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base
from app.db.types import GUID


class KnowledgeSourceType(str, enum.Enum):
    podcast = "podcast"
    newsletter = "newsletter"


class KnowledgeDocument(Base):
    """One ingested source document (a podcast transcript or newsletter post).

    ``(source_type, slug)`` is the natural key ingestion upserts against -
    ``slug`` is the source repository's own filename stem (e.g.
    ``"elena-verna-40"``), which is stable across re-ingestion runs. This
    is what makes ingestion idempotent: re-running it against an
    unchanged file finds the existing row by this key and, seeing an
    unchanged ``content_hash``, does nothing.
    """

    __tablename__ = "knowledge_documents"
    __table_args__ = (UniqueConstraint("source_type", "slug", name="uq_knowledge_documents_source_type_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[KnowledgeSourceType] = mapped_column(
        Enum(KnowledgeSourceType, native_enum=False, length=20), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # Nullable: newsletters have no guest; some podcast entries in the
    # source repo's own index are missing fields too - never fabricated.
    guest: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[date | None] = mapped_column(Date(), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    # SHA-256 of the raw source file bytes - the refresh mechanism's only
    # signal for "has this file actually changed since last ingestion."
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="KnowledgeChunk.chunk_index"
    )


class KnowledgeChunk(Base):
    """One retrievable slice of a document's text - see ``app.knowledge.chunking``."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (Index("ix_knowledge_chunks_document_id_chunk_index", "document_id", "chunk_index"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer(), nullable=False)
    text: Mapped[str] = mapped_column(Text(), nullable=False)
    # Comma-joined distinct speaker names appearing in this chunk. Populated
    # for podcast transcripts only (turn-based); null for newsletters
    # (essay prose has no speakers) - never fabricated when absent.
    speakers: Mapped[str | None] = mapped_column(String(500), nullable=True)
    char_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")


class MessageSource(Base):
    """A frozen citation: exactly what retrieval returned for one assistant message.

    Written once, at generation time, directly from
    ``KnowledgeRetriever.search()`` results - never from anything the
    model said. This is what "citation integrity" means in practice: the
    model can reference retrieved material conceptually, but the source
    list a user sees always traces back to a real row here, which in turn
    traces back to a real retrieved chunk.
    """

    __tablename__ = "message_sources"
    __table_args__ = (Index("ix_message_sources_message_id_rank", "message_id", "rank"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable + ON DELETE SET NULL: a re-ingestion that removes/replaces a
    # chunk must not delete history of what was actually cited at the time.
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("knowledge_documents.id", ondelete="SET NULL"), nullable=True
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("knowledge_chunks.id", ondelete="SET NULL"), nullable=True
    )
    rank: Mapped[int] = mapped_column(Integer(), nullable=False)
    relevance: Mapped[float] = mapped_column(Float(), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    guest: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[date | None] = mapped_column(Date(), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    excerpt: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    message: Mapped["Message"] = relationship(back_populates="sources")  # noqa: F821
