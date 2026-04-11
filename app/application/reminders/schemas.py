from dataclasses import dataclass
from datetime import date, datetime, time
from uuid import UUID


@dataclass(slots=True)
class ReminderSettingsView:
    user_id: str
    reminders_enabled: bool
    preferred_reminder_time_local: time | None
    timezone_name: str | None


@dataclass(slots=True)
class ReminderScheduleRequestView:
    request_id: UUID
    protocol_id: UUID
    pulse_plan_id: UUID
    status: str
    created_at: datetime


@dataclass(slots=True)
class PulsePlanEntryView:
    entry_id: UUID
    day_offset: int
    scheduled_day: date | None
    injection_event_key: str
    product_id: UUID
    ingredient_context: str | None
    volume_ml: float
    computed_mg: float
    sequence_no: int


@dataclass(slots=True)
class ReminderMaterializationResult:
    request_id: UUID
    created_count: int
    existing_count: int
    suppressed_count: int
    status: str


@dataclass(slots=True)
class ReminderRuntimeView:
    reminder_id: UUID
    protocol_id: UUID
    pulse_plan_id: UUID
    user_id: str
    status: str
    scheduled_at_utc: datetime
    injection_event_key: str
    payload_json: dict
    delivery_attempt_count: int
    awaiting_action_until_utc: datetime | None
    snoozed_until_utc: datetime | None
    last_message_chat_id: str | None
    last_message_id: str | None


@dataclass(slots=True)
class ReminderDiagnostics:
    pending_requests: int
    failed_requests: int
    materialized_rows: int
    status_counts: dict[str, int]
    failed_delivery_count: int
    integrity_state_counts: dict[str, int] | None = None
    broken_protocol_count: int = 0
    degraded_protocol_count: int = 0
    top_integrity_reason_codes: dict[str, int] | None = None


@dataclass(slots=True)
class ReminderDispatchReport:
    due_selected: int
    sent: int
    expired: int
    cleaned: int
    failed_delivery: int


@dataclass(slots=True)
class ReminderActionResult:
    reminder_id: UUID
    action_code: str
    status: str
    idempotent: bool


@dataclass(slots=True)
class SentMessageRef:
    chat_id: str
    message_id: str


@dataclass(slots=True)
class ProtocolAdherenceSummaryView:
    protocol_id: UUID
    pulse_plan_id: UUID
    user_id: str
    completed_count: int
    skipped_count: int
    snoozed_count: int
    expired_count: int
    total_actionable_count: int
    completion_rate: float
    skip_rate: float
    expiry_rate: float
    last_action_at: datetime | None
    integrity_state: str
    integrity_reason_code: str | None
    broken_reason_code: str | None
    integrity_detail_json: dict
    updated_at: datetime


@dataclass(slots=True)
class ProtocolStatusView:
    has_active_protocol: bool
    integrity_state: str | None
    explanation: str
    summary: ProtocolAdherenceSummaryView | None
