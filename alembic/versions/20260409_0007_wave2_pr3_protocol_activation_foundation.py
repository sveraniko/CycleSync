"""wave2 pr3 protocol activation foundation

Revision ID: 20260409_0007
Revises: 20260409_0006
Create Date: 2026-04-09 12:30:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260409_0007"
down_revision: Union[str, Sequence[str], None] = "20260409_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE protocols.protocol_drafts SET status = 'draft' WHERE status = 'active'")
    op.drop_index("uq_protocol_drafts_user_active", table_name="protocol_drafts", schema="protocols")
    op.create_index(
        "uq_protocol_drafts_user_active",
        "protocol_drafts",
        ["user_id"],
        unique=True,
        schema="protocols",
        postgresql_where=sa.text("status = 'draft'"),
    )

    op.add_column(
        "pulse_plan_previews",
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="preview_ready"),
        schema="pulse_engine",
    )
    op.add_column("pulse_plan_previews", sa.Column("superseded_at", sa.Date(), nullable=True), schema="pulse_engine")

    op.create_table(
        "protocols",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_preview_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="preview_ready"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_protocol_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("settings_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["protocols.protocol_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_preview_id"], ["pulse_engine.pulse_plan_previews.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["superseded_by_protocol_id"], ["protocols.protocols.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_protocols_protocols"),
        sa.UniqueConstraint("source_preview_id", name="uq_protocols_source_preview_id"),
        schema="protocols",
    )
    op.create_index(
        "ix_protocols_user_status_created_at",
        "protocols",
        ["user_id", "status", "created_at"],
        unique=False,
        schema="protocols",
    )
    op.create_index(
        "ix_protocols_draft_id_created_at",
        "protocols",
        ["draft_id", "created_at"],
        unique=False,
        schema="protocols",
    )

    op.create_table(
        "pulse_plans",
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_preview_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("preset_requested", sa.String(length=32), nullable=False),
        sa.Column("preset_applied", sa.String(length=32), nullable=False),
        sa.Column("settings_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warning_flags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocols.protocols.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_preview_id"], ["pulse_engine.pulse_plan_previews.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_pulse_engine_pulse_plans"),
        sa.UniqueConstraint("protocol_id", name="uq_pulse_plans_protocol_id"),
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_plans_protocol_id_created_at",
        "pulse_plans",
        ["protocol_id", "created_at"],
        unique=False,
        schema="pulse_engine",
    )

    op.create_table(
        "pulse_plan_entries",
        sa.Column("pulse_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(["pulse_plan_id"], ["pulse_engine.pulse_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["compound_catalog.compound_products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_pulse_engine_pulse_plan_entries"),
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_plan_entries_plan_day",
        "pulse_plan_entries",
        ["pulse_plan_id", "day_offset", "sequence_no"],
        unique=False,
        schema="pulse_engine",
    )

    op.create_table(
        "reminder_schedule_requests",
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pulse_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="requested"),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocols.protocols.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pulse_plan_id"], ["pulse_engine.pulse_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_reminders_reminder_schedule_requests"),
        schema="reminders",
    )
    op.create_index(
        "ix_reminder_schedule_requests_protocol_id_created_at",
        "reminder_schedule_requests",
        ["protocol_id", "created_at"],
        unique=False,
        schema="reminders",
    )
    op.create_index(
        "ix_reminder_schedule_requests_status_created_at",
        "reminder_schedule_requests",
        ["status", "created_at"],
        unique=False,
        schema="reminders",
    )


def downgrade() -> None:
    op.drop_index("uq_protocol_drafts_user_active", table_name="protocol_drafts", schema="protocols")
    op.create_index(
        "uq_protocol_drafts_user_active",
        "protocol_drafts",
        ["user_id"],
        unique=True,
        schema="protocols",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.execute("UPDATE protocols.protocol_drafts SET status = 'active' WHERE status = 'draft'")

    op.drop_index(
        "ix_reminder_schedule_requests_status_created_at",
        table_name="reminder_schedule_requests",
        schema="reminders",
    )
    op.drop_index(
        "ix_reminder_schedule_requests_protocol_id_created_at",
        table_name="reminder_schedule_requests",
        schema="reminders",
    )
    op.drop_table("reminder_schedule_requests", schema="reminders")

    op.drop_index("ix_pulse_plan_entries_plan_day", table_name="pulse_plan_entries", schema="pulse_engine")
    op.drop_table("pulse_plan_entries", schema="pulse_engine")

    op.drop_index("ix_pulse_plans_protocol_id_created_at", table_name="pulse_plans", schema="pulse_engine")
    op.drop_table("pulse_plans", schema="pulse_engine")

    op.drop_index("ix_protocols_draft_id_created_at", table_name="protocols", schema="protocols")
    op.drop_index("ix_protocols_user_status_created_at", table_name="protocols", schema="protocols")
    op.drop_table("protocols", schema="protocols")

    op.drop_column("pulse_plan_previews", "superseded_at", schema="pulse_engine")
    op.drop_column("pulse_plan_previews", "lifecycle_status", schema="pulse_engine")
