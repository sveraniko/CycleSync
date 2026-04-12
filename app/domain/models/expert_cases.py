from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.db.base import BaseModel, SchemaTableMixin


class SpecialistCase(SchemaTableMixin, BaseModel):
    __tablename__ = "specialist_cases"
    __schema_name__ = "expert_cases"

    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("protocols.protocols.id", ondelete="SET NULL"), nullable=True
    )
    lab_report_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("labs.lab_reports.id", ondelete="SET NULL"), nullable=True
    )
    triage_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_triage.lab_triage_runs.id", ondelete="SET NULL"), nullable=True
    )
    case_status: Mapped[str] = mapped_column(String(32), nullable=False, default="opened")
    opened_reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("expert_cases.specialist_case_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    latest_response_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("expert_cases.specialist_case_responses.id", ondelete="SET NULL"), nullable=True
    )
    assigned_specialist_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes_from_user: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_expert_cases_specialist_cases_user_opened", "user_id", "opened_at"),
        Index("ix_expert_cases_specialist_cases_status_opened", "case_status", "opened_at"),
        Index("ix_expert_cases_specialist_cases_report_opened", "lab_report_id", "opened_at"),
        {"schema": __schema_name__},
    )


class SpecialistCaseSnapshot(SchemaTableMixin, BaseModel):
    __tablename__ = "specialist_case_snapshots"
    __schema_name__ = "expert_cases"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("expert_cases.specialist_cases.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("case_id", "snapshot_version", name="uq_specialist_case_snapshot_version"),
        Index(
            "ix_expert_cases_case_snapshots_case_version",
            "case_id",
            "snapshot_version",
        ),
        {"schema": __schema_name__},
    )


class SpecialistCaseResponse(SchemaTableMixin, BaseModel):
    __tablename__ = "specialist_case_responses"
    __schema_name__ = "expert_cases"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("expert_cases.specialist_cases.id", ondelete="CASCADE"), nullable=False
    )
    responded_by: Mapped[str] = mapped_column(String(64), nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (
        Index("ix_expert_cases_case_responses_case_created", "case_id", "created_at"),
        {"schema": __schema_name__},
    )
