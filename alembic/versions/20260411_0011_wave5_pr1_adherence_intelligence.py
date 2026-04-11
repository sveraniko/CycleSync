"""wave5 pr1 adherence intelligence

Revision ID: 20260411_0011
Revises: 20260411_0010
Create Date: 2026-04-11 02:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260411_0011"
down_revision = "20260411_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "protocol_adherence_summaries",
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pulse_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("snoozed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("expired_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_actionable_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("skip_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("expiry_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("integrity_state", sa.String(length=32), nullable=False, server_default="healthy"),
        sa.Column("integrity_reason_code", sa.String(length=64), nullable=True),
        sa.Column("broken_reason_code", sa.String(length=64), nullable=True),
        sa.Column(
            "integrity_detail_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.ForeignKeyConstraint(["protocol_id"], ["protocols.protocols.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pulse_plan_id"], ["pulse_engine.pulse_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_adherence_protocol_adherence_summaries"),
        sa.UniqueConstraint("protocol_id", name="uq_protocol_adherence_summaries_protocol"),
        schema="adherence",
    )
    op.create_index(
        "ix_protocol_adherence_summaries_user_updated",
        "protocol_adherence_summaries",
        ["user_id", "updated_at"],
        unique=False,
        schema="adherence",
    )
    op.create_index(
        "ix_protocol_adherence_summaries_integrity_state_updated",
        "protocol_adherence_summaries",
        ["integrity_state", "updated_at"],
        unique=False,
        schema="adherence",
    )

    op.add_column(
        "protocols",
        sa.Column("protocol_integrity_flagged_at", sa.DateTime(timezone=True), nullable=True),
        schema="protocols",
    )
    op.add_column(
        "protocols",
        sa.Column("protocol_broken_at", sa.DateTime(timezone=True), nullable=True),
        schema="protocols",
    )

    for col in [
        "completed_count",
        "skipped_count",
        "snoozed_count",
        "expired_count",
        "total_actionable_count",
        "completion_rate",
        "skip_rate",
        "expiry_rate",
        "integrity_state",
        "integrity_detail_json",
    ]:
        op.alter_column("protocol_adherence_summaries", col, server_default=None, schema="adherence")


def downgrade() -> None:
    op.drop_column("protocols", "protocol_broken_at", schema="protocols")
    op.drop_column("protocols", "protocol_integrity_flagged_at", schema="protocols")
    op.drop_index(
        "ix_protocol_adherence_summaries_integrity_state_updated",
        table_name="protocol_adherence_summaries",
        schema="adherence",
    )
    op.drop_index(
        "ix_protocol_adherence_summaries_user_updated",
        table_name="protocol_adherence_summaries",
        schema="adherence",
    )
    op.drop_table("protocol_adherence_summaries", schema="adherence")
