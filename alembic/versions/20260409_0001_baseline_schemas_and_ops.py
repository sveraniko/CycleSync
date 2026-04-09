"""baseline schemas and ops foundation

Revision ID: 20260409_0001
Revises: 
Create Date: 2026-04-09 00:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260409_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMAS: tuple[str, ...] = (
    "compound_catalog",
    "user_registry",
    "protocols",
    "pulse_engine",
    "reminders",
    "adherence",
    "labs",
    "ai_triage",
    "expert_cases",
    "search_read",
    "analytics_raw",
    "analytics_views",
    "ops",
)


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    op.create_table(
        "outbox_events",
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("aggregate_type", sa.String(), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("causation_id", sa.String(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ops_outbox_events"),
        schema="ops",
    )
    op.create_index(
        "ix_ops_outbox_events_status_next_attempt",
        "outbox_events",
        ["status", "next_attempt_at"],
        unique=False,
        schema="ops",
    )

    op.create_table(
        "job_runs",
        sa.Column("job_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ops_job_runs"),
        schema="ops",
    )

    op.create_table(
        "projection_checkpoints",
        sa.Column("projection_name", sa.String(), nullable=False),
        sa.Column("checkpoint", sa.String(), nullable=False),
        sa.Column("checkpointed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ops_projection_checkpoints"),
        sa.UniqueConstraint("projection_name", name="uq_ops_projection_checkpoints_projection_name"),
        schema="ops",
    )


def downgrade() -> None:
    op.drop_table("projection_checkpoints", schema="ops")
    op.drop_table("job_runs", schema="ops")
    op.drop_index("ix_ops_outbox_events_status_next_attempt", table_name="outbox_events", schema="ops")
    op.drop_table("outbox_events", schema="ops")

    for schema in reversed(SCHEMAS):
        op.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
