"""wave4 pr1 reminder materialization foundation

Revision ID: 20260411_0009
Revises: 20260410_0008
Create Date: 2026-04-11 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260411_0009"
down_revision = "20260410_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reminder_schedule_requests",
        sa.Column("error_message", sa.String(length=255), nullable=True),
        schema="reminders",
    )

    op.create_table(
        "protocol_reminders",
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pulse_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pulse_plan_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column(
            "reminder_kind",
            sa.String(length=32),
            nullable=False,
            server_default="injection",
        ),
        sa.Column("scheduled_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_local_date", sa.Date(), nullable=False),
        sa.Column("scheduled_local_time", sa.Time(), nullable=False),
        sa.Column("timezone_name", sa.String(length=64), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="scheduled"
        ),
        sa.Column(
            "is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("injection_event_key", sa.String(length=64), nullable=False),
        sa.Column("day_offset", sa.Integer(), nullable=False),
        sa.Column(
            "payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["protocol_id"], ["protocols.protocols.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["pulse_plan_id"], ["pulse_engine.pulse_plans.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["pulse_plan_entry_id"],
            ["pulse_engine.pulse_plan_entries.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reminders_protocol_reminders"),
        sa.UniqueConstraint(
            "pulse_plan_entry_id",
            "reminder_kind",
            name="uq_protocol_reminders_entry_kind",
        ),
        schema="reminders",
    )
    op.create_index(
        "ix_protocol_reminders_protocol_status_schedule",
        "protocol_reminders",
        ["protocol_id", "status", "scheduled_at_utc"],
        unique=False,
        schema="reminders",
    )
    op.create_index(
        "ix_protocol_reminders_user_schedule",
        "protocol_reminders",
        ["user_id", "scheduled_at_utc"],
        unique=False,
        schema="reminders",
    )

    op.create_table(
        "user_notification_settings",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column(
            "reminders_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("preferred_reminder_time_local", sa.Time(), nullable=True),
        sa.Column("timezone_name", sa.String(length=64), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id", name="pk_user_registry_user_notification_settings"
        ),
        sa.UniqueConstraint(
            "user_id", name="uq_user_registry_user_notification_settings_user_id"
        ),
        schema="user_registry",
    )

    op.alter_column(
        "protocol_reminders", "reminder_kind", server_default=None, schema="reminders"
    )
    op.alter_column(
        "protocol_reminders", "status", server_default=None, schema="reminders"
    )
    op.alter_column(
        "protocol_reminders", "is_enabled", server_default=None, schema="reminders"
    )
    op.alter_column(
        "user_notification_settings",
        "reminders_enabled",
        server_default=None,
        schema="user_registry",
    )


def downgrade() -> None:
    op.drop_table("user_notification_settings", schema="user_registry")

    op.drop_index(
        "ix_protocol_reminders_user_schedule",
        table_name="protocol_reminders",
        schema="reminders",
    )
    op.drop_index(
        "ix_protocol_reminders_protocol_status_schedule",
        table_name="protocol_reminders",
        schema="reminders",
    )
    op.drop_table("protocol_reminders", schema="reminders")

    op.drop_column("reminder_schedule_requests", "error_message", schema="reminders")
