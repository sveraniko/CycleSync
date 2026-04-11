from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.db.base import BaseModel, SchemaTableMixin


class LabMarker(SchemaTableMixin, BaseModel):
    __tablename__ = "markers"
    __schema_name__ = "labs"

    marker_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category_code: Mapped[str] = mapped_column(String(64), nullable=False)
    default_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    accepted_units: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("marker_code", name="uq_labs_markers_marker_code"),
        Index("ix_labs_markers_category_active", "category_code", "is_active"),
        {"schema": __schema_name__},
    )


class LabMarkerAlias(SchemaTableMixin, BaseModel):
    __tablename__ = "marker_aliases"
    __schema_name__ = "labs"

    marker_id: Mapped[UUID] = mapped_column(
        ForeignKey("labs.markers.id", ondelete="CASCADE"), nullable=False
    )
    alias_text: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("marker_id", "normalized_alias", name="uq_labs_marker_aliases_marker_alias"),
        Index("ix_labs_marker_aliases_normalized_alias", "normalized_alias"),
        {"schema": __schema_name__},
    )


class LabPanel(SchemaTableMixin, BaseModel):
    __tablename__ = "lab_panels"
    __schema_name__ = "labs"

    panel_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("panel_code", name="uq_labs_lab_panels_panel_code"),
        Index("ix_labs_lab_panels_active", "is_active"),
        {"schema": __schema_name__},
    )


class LabPanelMarker(SchemaTableMixin, BaseModel):
    __tablename__ = "lab_panel_markers"
    __schema_name__ = "labs"

    panel_id: Mapped[UUID] = mapped_column(
        ForeignKey("labs.lab_panels.id", ondelete="CASCADE"), nullable=False
    )
    marker_id: Mapped[UUID] = mapped_column(
        ForeignKey("labs.markers.id", ondelete="RESTRICT"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("panel_id", "marker_id", name="uq_labs_panel_markers_pair"),
        Index("ix_labs_lab_panel_markers_panel_order", "panel_id", "sort_order"),
        {"schema": __schema_name__},
    )


class LabReport(SchemaTableMixin, BaseModel):
    __tablename__ = "lab_reports"
    __schema_name__ = "labs"

    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("protocols.protocols.id", ondelete="SET NULL"), nullable=True
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_lab_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_labs_lab_reports_user_date", "user_id", "report_date"),
        Index("ix_labs_lab_reports_protocol_date", "protocol_id", "report_date"),
        {"schema": __schema_name__},
    )


class LabReportEntry(SchemaTableMixin, BaseModel):
    __tablename__ = "lab_report_entries"
    __schema_name__ = "labs"

    lab_report_id: Mapped[UUID] = mapped_column(
        ForeignKey("labs.lab_reports.id", ondelete="CASCADE"), nullable=False
    )
    marker_id: Mapped[UUID] = mapped_column(
        ForeignKey("labs.markers.id", ondelete="RESTRICT"), nullable=False
    )
    entered_value: Mapped[str] = mapped_column(String(64), nullable=False)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    reference_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("lab_report_id", "marker_id", name="uq_labs_report_entries_report_marker"),
        Index("ix_labs_lab_report_entries_report_entered", "lab_report_id", "entered_at"),
        {"schema": __schema_name__},
    )
