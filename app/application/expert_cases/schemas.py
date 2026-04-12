from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


class SpecialistCaseStatus:
    OPENED = "opened"
    ASSEMBLED = "assembled"
    AWAITING_SPECIALIST = "awaiting_specialist"
    IN_REVIEW = "in_review"
    ANSWERED = "answered"
    CLOSED = "closed"
    CANCELLED = "cancelled"


ALLOWED_CASE_STATUSES = {
    SpecialistCaseStatus.OPENED,
    SpecialistCaseStatus.ASSEMBLED,
    SpecialistCaseStatus.AWAITING_SPECIALIST,
    SpecialistCaseStatus.IN_REVIEW,
    SpecialistCaseStatus.ANSWERED,
    SpecialistCaseStatus.CLOSED,
    SpecialistCaseStatus.CANCELLED,
}


@dataclass(slots=True)
class SpecialistCaseView:
    case_id: UUID
    user_id: str
    protocol_id: UUID | None
    lab_report_id: UUID | None
    triage_run_id: UUID | None
    case_status: str
    opened_reason_code: str
    opened_at: datetime
    closed_at: datetime | None
    answered_at: datetime | None
    latest_snapshot_id: UUID | None
    latest_response_id: UUID | None
    assigned_specialist_id: str | None
    notes_from_user: str | None


@dataclass(slots=True)
class SpecialistCaseSnapshotView:
    snapshot_id: UUID
    case_id: UUID
    snapshot_version: int
    payload_json: dict
    created_at: datetime


@dataclass(slots=True)
class LabReportCaseEntryView:
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
class LabReportCaseView:
    report_id: UUID
    user_id: str
    protocol_id: UUID | None
    report_date: date
    source_lab_name: str | None
    notes: str | None
    finalized_at: datetime | None
    created_at: datetime
    entries: list[LabReportCaseEntryView]


@dataclass(slots=True)
class TriageFlagCaseView:
    marker_id: UUID | None
    severity: str
    flag_code: str
    title: str
    explanation: str
    suggested_followup: str | None


@dataclass(slots=True)
class TriageRunCaseView:
    triage_run_id: UUID
    lab_report_id: UUID
    user_id: str
    protocol_id: UUID | None
    triage_status: str
    summary_text: str | None
    urgent_flag: bool
    model_name: str
    prompt_version: str
    completed_at: datetime | None
    created_at: datetime
    flags: list[TriageFlagCaseView]


@dataclass(slots=True)
class ProtocolCaseContextView:
    protocol_id: UUID
    status: str
    activated_at: datetime | None
    summary_snapshot_json: dict | None
    settings_snapshot_json: dict


@dataclass(slots=True)
class PulsePlanCaseContextView:
    pulse_plan_id: UUID
    status: str
    preset_requested: str
    preset_applied: str
    summary_metrics_json: dict | None
    warning_flags_json: list[str]


@dataclass(slots=True)
class AdherenceCaseContextView:
    protocol_id: UUID
    pulse_plan_id: UUID
    integrity_state: str
    integrity_reason_code: str | None
    broken_reason_code: str | None
    integrity_detail_json: dict
    completion_rate: float
    total_actionable_count: int
    completed_count: int
    skipped_count: int
    snoozed_count: int
    expired_count: int
    last_action_at: datetime | None


@dataclass(slots=True)
class SpecialistCaseListItemView:
    case_id: UUID
    case_status: str
    opened_at: datetime
    lab_report_id: UUID | None
    lab_report_date: date | None
    triage_run_id: UUID | None
    latest_snapshot_id: UUID | None
    latest_response_summary: str | None
    latest_response_created_at: datetime | None


@dataclass(slots=True)
class SpecialistCaseResponseView:
    response_id: UUID
    case_id: UUID
    responded_by: str
    response_text: str
    response_summary: str | None
    is_final: bool
    created_at: datetime


@dataclass(slots=True)
class SpecialistCaseDetailView:
    case: SpecialistCaseView
    latest_response: SpecialistCaseResponseView | None


@dataclass(slots=True)
class SpecialistCaseOpenedResult:
    case: SpecialistCaseView
    snapshot: SpecialistCaseSnapshotView


@dataclass(slots=True)
class SpecialistCaseAccessDecision:
    allowed: bool
    reason_code: str
