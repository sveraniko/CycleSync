from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
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

    __table_args__ = (
        Index("ix_reminder_schedule_requests_protocol_id_created_at", "protocol_id", "created_at"),
        Index("ix_reminder_schedule_requests_status_created_at", "status", "created_at"),
        {"schema": __schema_name__},
    )
