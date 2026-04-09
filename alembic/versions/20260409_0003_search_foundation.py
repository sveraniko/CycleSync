"""search projection and query logging foundation

Revision ID: 20260409_0003
Revises: 20260409_0002
Create Date: 2026-04-09 02:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260409_0003"
down_revision: Union[str, Sequence[str], None] = "20260409_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_projection_state",
        sa.Column("projection_name", sa.String(length=128), nullable=False),
        sa.Column("checkpoint", sa.String(length=128), nullable=False),
        sa.Column("checkpointed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("indexed_documents_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_rebuild_kind", sa.String(length=32), nullable=False, server_default=sa.text("'incremental'")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_search_read_search_projection_state"),
        sa.UniqueConstraint("projection_name", name="uq_search_projection_state_name"),
        schema="search_read",
    )

    op.create_table(
        "search_query_logs",
        sa.Column("raw_query", sa.String(length=512), nullable=False),
        sa.Column("normalized_query", sa.String(length=512), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'text'")),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("was_found", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_search_read_search_query_logs"),
        schema="search_read",
    )
    op.create_index(
        "ix_search_query_logs_created_at",
        "search_query_logs",
        ["created_at"],
        unique=False,
        schema="search_read",
    )
    op.create_index(
        "ix_search_query_logs_was_found_created_at",
        "search_query_logs",
        ["was_found", "created_at"],
        unique=False,
        schema="search_read",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_search_query_logs_was_found_created_at",
        table_name="search_query_logs",
        schema="search_read",
    )
    op.drop_index("ix_search_query_logs_created_at", table_name="search_query_logs", schema="search_read")
    op.drop_table("search_query_logs", schema="search_read")
    op.drop_table("search_projection_state", schema="search_read")
