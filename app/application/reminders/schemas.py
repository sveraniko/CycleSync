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
class ReminderDiagnostics:
    pending_requests: int
    failed_requests: int
    materialized_rows: int
