from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.db.base import BaseModel, SchemaTableMixin


class OutboxEvent(SchemaTableMixin, BaseModel):
    __tablename__ = "outbox_events"
    __schema_name__ = "ops"

    event_type: Mapped[str] = mapped_column(nullable=False)
    aggregate_type: Mapped[str] = mapped_column(nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="pending")
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(nullable=True)
    causation_id: Mapped[str | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_ops_outbox_events_status_next_attempt", "status", "next_attempt_at"),
        {"schema": __schema_name__},
    )


class JobRun(SchemaTableMixin, BaseModel):
    __tablename__ = "job_runs"
    __schema_name__ = "ops"

    job_name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ProjectionCheckpoint(SchemaTableMixin, BaseModel):
    __tablename__ = "projection_checkpoints"
    __schema_name__ = "ops"

    projection_name: Mapped[str] = mapped_column(nullable=False, unique=True)
    checkpoint: Mapped[str] = mapped_column(nullable=False)
    checkpointed_at: Mapped[datetime] = mapped_column(nullable=False)
