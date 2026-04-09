from datetime import date
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text
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
    preset_requested: Mapped[str] = mapped_column(String(32), nullable=False)
    preset_applied: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    degraded_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settings_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary_metrics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    warning_flags_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
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
