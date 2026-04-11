from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.db.base import BaseModel, SchemaTableMixin


class ReminderScheduleRequest(SchemaTableMixin, BaseModel):
    __tablename__ = "reminder_schedule_requests"
    __schema_name__ = "reminders"

    protocol_id: Mapped[UUID] = mapped_column(
        ForeignKey("protocols.protocols.id", ondelete="CASCADE"),
        nullable=False,
    )
    pulse_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("pulse_engine.pulse_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="requested")
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index(
            "ix_reminder_schedule_requests_protocol_id_created_at",
            "protocol_id",
            "created_at",
        ),
        Index(
            "ix_reminder_schedule_requests_status_created_at", "status", "created_at"
        ),
        {"schema": __schema_name__},
    )


class ProtocolReminder(SchemaTableMixin, BaseModel):
    __tablename__ = "protocol_reminders"
    __schema_name__ = "reminders"

    protocol_id: Mapped[UUID] = mapped_column(
        ForeignKey("protocols.protocols.id", ondelete="CASCADE"),
        nullable=False,
    )
    pulse_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("pulse_engine.pulse_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    pulse_plan_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("pulse_engine.pulse_plan_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reminder_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="injection"
    )
    scheduled_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    scheduled_local_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_local_time: Mapped[time] = mapped_column(Time(), nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    injection_event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    day_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivery_attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_delivery_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_message_chat_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    awaiting_action_until_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    snoozed_until_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    action_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    clean_after_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "pulse_plan_entry_id",
            "reminder_kind",
            name="uq_protocol_reminders_entry_kind",
        ),
        Index(
            "ix_protocol_reminders_protocol_status_schedule",
            "protocol_id",
            "status",
            "scheduled_at_utc",
        ),
        Index("ix_protocol_reminders_user_schedule", "user_id", "scheduled_at_utc"),
        Index("ix_protocol_reminders_status_snooze", "status", "snoozed_until_utc"),
        {"schema": __schema_name__},
    )


class ProtocolAdherenceEvent(SchemaTableMixin, BaseModel):
    __tablename__ = "protocol_adherence_events"
    __schema_name__ = "adherence"

    protocol_id: Mapped[UUID] = mapped_column(
        ForeignKey("protocols.protocols.id", ondelete="CASCADE"), nullable=False
    )
    pulse_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("pulse_engine.pulse_plans.id", ondelete="CASCADE"), nullable=False
    )
    reminder_id: Mapped[UUID] = mapped_column(
        ForeignKey("reminders.protocol_reminders.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_code: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index(
            "ix_protocol_adherence_events_protocol_occurred",
            "protocol_id",
            "occurred_at",
        ),
        Index(
            "ix_protocol_adherence_events_user_occurred",
            "user_id",
            "occurred_at",
        ),
        {"schema": __schema_name__},
    )
