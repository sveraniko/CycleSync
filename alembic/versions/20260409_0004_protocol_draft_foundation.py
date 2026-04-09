"""protocol draft foundation

Revision ID: 20260409_0004
Revises: 20260409_0003
Create Date: 2026-04-09 03:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260409_0004"
down_revision: Union[str, Sequence[str], None] = "20260409_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "protocol_drafts",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_protocols_protocol_drafts"),
        schema="protocols",
    )
    op.create_index(
        "ix_protocol_drafts_user_status",
        "protocol_drafts",
        ["user_id", "status"],
        unique=False,
        schema="protocols",
    )
    op.create_index(
        "uq_protocol_drafts_user_active",
        "protocol_drafts",
        ["user_id"],
        unique=True,
        schema="protocols",
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "protocol_draft_items",
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selected_brand", sa.String(length=255), nullable=True),
        sa.Column("selected_product_name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["protocols.protocol_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["compound_catalog.compound_products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_protocols_protocol_draft_items"),
        sa.UniqueConstraint("draft_id", "product_id", name="uq_protocol_draft_item_product"),
        schema="protocols",
    )
    op.create_index(
        "ix_protocol_draft_items_draft_id",
        "protocol_draft_items",
        ["draft_id"],
        unique=False,
        schema="protocols",
    )


def downgrade() -> None:
    op.drop_index("ix_protocol_draft_items_draft_id", table_name="protocol_draft_items", schema="protocols")
    op.drop_table("protocol_draft_items", schema="protocols")

    op.drop_index("uq_protocol_drafts_user_active", table_name="protocol_drafts", schema="protocols")
    op.drop_index("ix_protocol_drafts_user_status", table_name="protocol_drafts", schema="protocols")
    op.drop_table("protocol_drafts", schema="protocols")
