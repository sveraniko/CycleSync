from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


@dataclass(slots=True)
class LabMarkerView:
    marker_id: UUID
    marker_code: str
    display_name: str
    category_code: str
    default_unit: str
    accepted_units: list[str]
    notes: str | None


@dataclass(slots=True)
class LabPanelView:
    panel_id: UUID
    panel_code: str
    display_name: str
    marker_ids: list[UUID]


@dataclass(slots=True)
class LabReportView:
    report_id: UUID
    user_id: str
    protocol_id: UUID | None
    report_date: date
    source_lab_name: str | None
    notes: str | None
    finalized_at: datetime | None
    created_at: datetime


@dataclass(slots=True)
class LabReportEntryView:
    entry_id: UUID
    lab_report_id: UUID
    marker_id: UUID
    marker_code: str
    marker_display_name: str
    entered_value: str
    numeric_value: Decimal | None
    unit: str
    reference_min: Decimal | None
    reference_max: Decimal | None
    entered_at: datetime


@dataclass(slots=True)
class LabEntryInput:
    marker_id: UUID
    value_text: str
    unit: str
    reference_min: Decimal | None = None
    reference_max: Decimal | None = None


@dataclass(slots=True)
class LabReportDetailsView:
    report: LabReportView
    entries: list[LabReportEntryView]
