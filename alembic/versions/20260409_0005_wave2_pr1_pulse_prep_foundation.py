"""wave2 pr1 pulse preparation foundation

Revision ID: 20260409_0005
Revises: 20260409_0004
Create Date: 2026-04-09 05:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260409_0005"
down_revision: Union[str, Sequence[str], None] = "20260409_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "compound_products",
        sa.Column("max_injection_volume_ml", sa.Numeric(precision=10, scale=3), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_products",
        sa.Column("is_automatable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_products",
        sa.Column("pharmacology_notes", sa.Text(), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_products",
        sa.Column("composition_basis_notes", sa.Text(), nullable=True),
        schema="compound_catalog",
    )

    op.add_column(
        "compound_ingredients",
        sa.Column("half_life_days", sa.Numeric(precision=8, scale=3), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_ingredients",
        sa.Column("dose_guidance_min_mg_week", sa.Numeric(precision=12, scale=4), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_ingredients",
        sa.Column("dose_guidance_max_mg_week", sa.Numeric(precision=12, scale=4), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_ingredients",
        sa.Column("dose_guidance_typical_mg_week", sa.Numeric(precision=12, scale=4), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_ingredients",
        sa.Column("is_pulse_driver", sa.Boolean(), nullable=True),
        schema="compound_catalog",
    )

    op.create_table(
        "protocol_draft_settings",
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekly_target_total_mg", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("duration_weeks", sa.SmallInteger(), nullable=True),
        sa.Column("preset_code", sa.String(length=32), nullable=True),
        sa.Column("max_injection_volume_ml", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("max_injections_per_week", sa.SmallInteger(), nullable=True),
        sa.Column("planned_start_date", sa.Date(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["protocols.protocol_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_protocols_protocol_draft_settings"),
        sa.UniqueConstraint("draft_id", name="uq_protocol_draft_settings_draft_id"),
        schema="protocols",
    )
    op.create_index(
        "ix_protocol_draft_settings_draft_id",
        "protocol_draft_settings",
        ["draft_id"],
        unique=False,
        schema="protocols",
    )


def downgrade() -> None:
    op.drop_index("ix_protocol_draft_settings_draft_id", table_name="protocol_draft_settings", schema="protocols")
    op.drop_table("protocol_draft_settings", schema="protocols")

    op.drop_column("compound_ingredients", "is_pulse_driver", schema="compound_catalog")
    op.drop_column("compound_ingredients", "dose_guidance_typical_mg_week", schema="compound_catalog")
    op.drop_column("compound_ingredients", "dose_guidance_max_mg_week", schema="compound_catalog")
    op.drop_column("compound_ingredients", "dose_guidance_min_mg_week", schema="compound_catalog")
    op.drop_column("compound_ingredients", "half_life_days", schema="compound_catalog")

    op.drop_column("compound_products", "composition_basis_notes", schema="compound_catalog")
    op.drop_column("compound_products", "pharmacology_notes", schema="compound_catalog")
    op.drop_column("compound_products", "is_automatable", schema="compound_catalog")
    op.drop_column("compound_products", "max_injection_volume_ml", schema="compound_catalog")
