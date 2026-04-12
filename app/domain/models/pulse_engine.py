from datetime import date
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.db.base import BaseModel, SchemaTableMixin


class PulseCalculationRun(SchemaTableMixin, BaseModel):
    __tablename__ = "pulse_calculation_runs"
    __schema_name__ = "pulse_engine"

    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("protocols.protocol_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    protocol_input_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="total_target")
    preset_requested: Mapped[str] = mapped_column(String(32), nullable=False)
    preset_applied: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    degraded_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settings_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary_metrics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    warning_flags_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    allocation_mode: Mapped[str | None] = mapped_column(String(48), nullable=True)
    guidance_coverage_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    calculation_quality_flags_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    allocation_details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_pulse_calculation_runs_draft_id_created_at", "draft_id", "created_at"),
        Index("ix_pulse_calculation_runs_status", "status"),
        {"schema": __schema_name__},
    )


class PulsePlanPreview(SchemaTableMixin, BaseModel):
    __tablename__ = "pulse_plan_previews"
    __schema_name__ = "pulse_engine"

    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("protocols.protocol_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    protocol_input_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="total_target")
    calculation_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pulse_engine.pulse_calculation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    preset_requested: Mapped[str] = mapped_column(String(32), nullable=False)
    preset_applied: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    degraded_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settings_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary_metrics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    warning_flags_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    allocation_mode: Mapped[str | None] = mapped_column(String(48), nullable=True)
    guidance_coverage_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    calculation_quality_flags_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    allocation_details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, default="preview_ready")
    superseded_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        Index("ix_pulse_plan_previews_draft_id_created_at", "draft_id", "created_at"),
        Index("ix_pulse_plan_previews_status", "status"),
        {"schema": __schema_name__},
    )


class PulsePlanPreviewEntry(SchemaTableMixin, BaseModel):
    __tablename__ = "pulse_plan_preview_entries"
    __schema_name__ = "pulse_engine"

    preview_id: Mapped[UUID] = mapped_column(
        ForeignKey("pulse_engine.pulse_plan_previews.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("compound_catalog.compound_products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ingredient_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    volume_ml: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    computed_mg: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    injection_event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    __table_args__ = (
        Index("ix_pulse_plan_preview_entries_preview_day", "preview_id", "day_offset", "sequence_no"),
        Index("ix_pulse_plan_preview_entries_product_id", "product_id"),
        {"schema": __schema_name__},
    )


class PulsePlan(SchemaTableMixin, BaseModel):
    __tablename__ = "pulse_plans"
    __schema_name__ = "pulse_engine"

    protocol_id: Mapped[UUID] = mapped_column(
        ForeignKey("protocols.protocols.id", ondelete="CASCADE"),
        nullable=False,
    )
    protocol_input_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="total_target")
    source_preview_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pulse_engine.pulse_plan_previews.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    preset_requested: Mapped[str] = mapped_column(String(32), nullable=False)
    preset_applied: Mapped[str] = mapped_column(String(32), nullable=False)
    settings_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary_metrics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    warning_flags_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index("ix_pulse_plans_protocol_id_created_at", "protocol_id", "created_at"),
        UniqueConstraint("protocol_id", name="uq_pulse_plans_protocol_id"),
        {"schema": __schema_name__},
    )


class PulsePlanEntryRecord(SchemaTableMixin, BaseModel):
    __tablename__ = "pulse_plan_entries"
    __schema_name__ = "pulse_engine"

    pulse_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("pulse_engine.pulse_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("compound_catalog.compound_products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ingredient_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    volume_ml: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    computed_mg: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    injection_event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    __table_args__ = (
        Index("ix_pulse_plan_entries_plan_day", "pulse_plan_id", "day_offset", "sequence_no"),
        {"schema": __schema_name__},
    )
