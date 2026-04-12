from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.db.base import BaseModel, SchemaTableMixin


class LabTriageRun(SchemaTableMixin, BaseModel):
    __tablename__ = "lab_triage_runs"
    __schema_name__ = "ai_triage"

    lab_report_id: Mapped[UUID] = mapped_column(
        ForeignKey("labs.lab_reports.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("protocols.protocols.id", ondelete="SET NULL"), nullable=True
    )
    triage_status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    urgent_flag: Mapped[bool] = mapped_column(nullable=False, default=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ai_triage_runs_report_created", "lab_report_id", "created_at"),
        Index("ix_ai_triage_runs_user_created", "user_id", "created_at"),
        {"schema": __schema_name__},
    )


class LabTriageFlag(SchemaTableMixin, BaseModel):
    __tablename__ = "lab_triage_flags"
    __schema_name__ = "ai_triage"

    triage_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_triage.lab_triage_runs.id", ondelete="CASCADE"), nullable=False
    )
    marker_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("labs.markers.id", ondelete="SET NULL"), nullable=True
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    flag_code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_followup: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_ai_triage_flags_run_severity", "triage_run_id", "severity"),
        {"schema": __schema_name__},
    )
