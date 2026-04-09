"""wave2 pr2 pulse engine preview

Revision ID: 20260409_0006
Revises: 20260409_0005
Create Date: 2026-04-09 08:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260409_0006"
down_revision: Union[str, Sequence[str], None] = "20260409_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS pulse_engine")

    op.create_table(
        "pulse_calculation_runs",
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preset_requested", sa.String(length=32), nullable=False),
        sa.Column("preset_applied", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("degraded_fallback", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("settings_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warning_flags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["protocols.protocol_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_pulse_engine_pulse_calculation_runs"),
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_calculation_runs_draft_id_created_at",
        "pulse_calculation_runs",
        ["draft_id", "created_at"],
        unique=False,
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_calculation_runs_status",
        "pulse_calculation_runs",
        ["status"],
        unique=False,
        schema="pulse_engine",
    )

    op.create_table(
        "pulse_plan_previews",
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calculation_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("preset_requested", sa.String(length=32), nullable=False),
        sa.Column("preset_applied", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("degraded_fallback", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("settings_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warning_flags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["calculation_run_id"], ["pulse_engine.pulse_calculation_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["draft_id"], ["protocols.protocol_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_pulse_engine_pulse_plan_previews"),
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_plan_previews_draft_id_created_at",
        "pulse_plan_previews",
        ["draft_id", "created_at"],
        unique=False,
        schema="pulse_engine",
    )
    op.create_index("ix_pulse_plan_previews_status", "pulse_plan_previews", ["status"], unique=False, schema="pulse_engine")

    op.create_table(
        "pulse_plan_preview_entries",
        sa.Column("preview_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_offset", sa.Integer(), nullable=False),
        sa.Column("scheduled_day", sa.Date(), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient_context", sa.Text(), nullable=True),
        sa.Column("volume_ml", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("computed_mg", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("injection_event_key", sa.String(length=64), nullable=False),
        sa.Column("sequence_no", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["preview_id"], ["pulse_engine.pulse_plan_previews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["compound_catalog.compound_products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_pulse_engine_pulse_plan_preview_entries"),
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_plan_preview_entries_preview_day",
        "pulse_plan_preview_entries",
        ["preview_id", "day_offset", "sequence_no"],
        unique=False,
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_plan_preview_entries_product_id",
        "pulse_plan_preview_entries",
        ["product_id"],
        unique=False,
        schema="pulse_engine",
    )


def downgrade() -> None:
    op.drop_index("ix_pulse_plan_preview_entries_product_id", table_name="pulse_plan_preview_entries", schema="pulse_engine")
    op.drop_index("ix_pulse_plan_preview_entries_preview_day", table_name="pulse_plan_preview_entries", schema="pulse_engine")
    op.drop_table("pulse_plan_preview_entries", schema="pulse_engine")

    op.drop_index("ix_pulse_plan_previews_status", table_name="pulse_plan_previews", schema="pulse_engine")
    op.drop_index("ix_pulse_plan_previews_draft_id_created_at", table_name="pulse_plan_previews", schema="pulse_engine")
    op.drop_table("pulse_plan_previews", schema="pulse_engine")

    op.drop_index("ix_pulse_calculation_runs_status", table_name="pulse_calculation_runs", schema="pulse_engine")
    op.drop_index("ix_pulse_calculation_runs_draft_id_created_at", table_name="pulse_calculation_runs", schema="pulse_engine")
    op.drop_table("pulse_calculation_runs", schema="pulse_engine")

    op.execute("DROP SCHEMA IF EXISTS pulse_engine")
