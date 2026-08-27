"""knowledge base (Phase 4)

Adds the Lenny knowledge base tables: knowledge_documents (ingested
podcast transcripts / newsletter posts), knowledge_chunks (retrievable
slices of a document, produced by app.knowledge.chunking), and
message_sources (frozen per-message citations, written by
app.services.conversations.create_message from real
KnowledgeRetriever results - never from model output).

Revision ID: e75557089cdb
Revises: 9360e5d2f679
Create Date: 2026-08-27 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e75557089cdb"
down_revision: Union[str, None] = "9360e5d2f679"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_type",
            sa.String(length=20),
            sa.CheckConstraint("source_type IN ('podcast', 'newsletter')", name="ck_knowledge_documents_source_type"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("guest", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_type", "slug", name="uq_knowledge_documents_source_type_slug"),
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("speakers", sa.String(length=500), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_document_id_chunk_index", "knowledge_chunks", ["document_id", "chunk_index"])

    op.create_table(
        "message_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("relevance", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("guest", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_message_sources_message_id", "message_sources", ["message_id"])
    op.create_index("ix_message_sources_message_id_rank", "message_sources", ["message_id", "rank"])


def downgrade() -> None:
    op.drop_table("message_sources")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
