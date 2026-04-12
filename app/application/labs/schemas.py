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


@dataclass(slots=True)
class ProtocolTriageContextView:
    protocol_id: UUID
    status: str
    activated_at: datetime | None
    selected_products: list[str]
    pulse_plan_context: dict
    adherence_integrity_state: str | None
    adherence_integrity_detail: dict | None


@dataclass(slots=True)
class LabTriageInputMarker:
    marker_id: UUID
    marker_code: str
    marker_display_name: str
    category_code: str
    numeric_value: Decimal
    unit: str
    reference_min: Decimal | None
    reference_max: Decimal | None


@dataclass(slots=True)
class LabTriageInputPayload:
    report_id: UUID
    user_id: str
    report_date: date
    protocol_context: ProtocolTriageContextView | None
    markers: list[LabTriageInputMarker]


@dataclass(slots=True)
class LabTriageFlagCreate:
    marker_id: UUID | None
    severity: str
    flag_code: str
    title: str
    explanation: str
    suggested_followup: str | None


@dataclass(slots=True)
class LabTriageFlagView:
    flag_id: UUID
    triage_run_id: UUID
    marker_id: UUID | None
    severity: str
    flag_code: str
    title: str
    explanation: str
    suggested_followup: str | None
    created_at: datetime


@dataclass(slots=True)
class LabTriageRunView:
    triage_run_id: UUID
    lab_report_id: UUID
    user_id: str
    protocol_id: UUID | None
    triage_status: str
    summary_text: str | None
    urgent_flag: bool
    model_name: str
    prompt_version: str
    raw_result_json: dict | None
    created_at: datetime
    completed_at: datetime | None


@dataclass(slots=True)
class LabTriageResultView:
    run: LabTriageRunView
    flags: list[LabTriageFlagView]
