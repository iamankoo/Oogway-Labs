"""add message extra_metadata

Adds a nullable JSON column for assistant-message generation metadata
(provider, model, latency, status) introduced in Phase 3. User and system
messages leave it null.

Revision ID: 9360e5d2f679
Revises: 37c02c433bb2
Create Date: 2026-08-27 11:40:21.584020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9360e5d2f679'
down_revision: Union[str, None] = '37c02c433bb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("extra_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "extra_metadata")
