"""wave4 pr2 reminder runtime execution

Revision ID: 20260411_0010
Revises: 20260411_0009
Create Date: 2026-04-11 01:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260411_0010"
down_revision = "20260411_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "protocol_reminders",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column(
            "delivery_attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("last_delivery_error", sa.String(length=255), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("last_message_chat_id", sa.String(length=128), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("last_message_id", sa.String(length=128), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column(
            "awaiting_action_until_utc", sa.DateTime(timezone=True), nullable=True
        ),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("snoozed_until_utc", sa.DateTime(timezone=True), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("action_code", sa.String(length=32), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("clean_after_utc", sa.DateTime(timezone=True), nullable=True),
        schema="reminders",
    )
    op.create_index(
        "ix_protocol_reminders_status_snooze",
        "protocol_reminders",
        ["status", "snoozed_until_utc"],
        unique=False,
        schema="reminders",
    )

    op.create_table(
        "protocol_adherence_events",
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pulse_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reminder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("action_code", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
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
            ["reminder_id"], ["reminders.protocol_reminders.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_adherence_protocol_adherence_events"),
        schema="adherence",
    )
    op.create_index(
        "ix_protocol_adherence_events_protocol_occurred",
        "protocol_adherence_events",
        ["protocol_id", "occurred_at"],
        unique=False,
        schema="adherence",
    )
    op.create_index(
        "ix_protocol_adherence_events_user_occurred",
        "protocol_adherence_events",
        ["user_id", "occurred_at"],
        unique=False,
        schema="adherence",
    )

    op.alter_column(
        "protocol_reminders",
        "delivery_attempt_count",
        server_default=None,
        schema="reminders",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_protocol_adherence_events_user_occurred",
        table_name="protocol_adherence_events",
        schema="adherence",
    )
    op.drop_index(
        "ix_protocol_adherence_events_protocol_occurred",
        table_name="protocol_adherence_events",
        schema="adherence",
    )
    op.drop_table("protocol_adherence_events", schema="adherence")

    op.drop_index(
        "ix_protocol_reminders_status_snooze",
        table_name="protocol_reminders",
        schema="reminders",
    )
    for column in [
        "clean_after_utc",
        "action_code",
        "acted_at",
        "snoozed_until_utc",
        "awaiting_action_until_utc",
        "last_message_id",
        "last_message_chat_id",
        "last_delivery_error",
        "delivery_attempt_count",
        "sent_at",
    ]:
        op.drop_column("protocol_reminders", column, schema="reminders")
