from datetime import date, datetime, time
from uuid import UUID

from app.application.reminders.schemas import (
    PulsePlanEntryView,
    ReminderDiagnostics,
    ReminderScheduleRequestView,
    ReminderSettingsView,
)


class ReminderRepository:
    async def dequeue_requested_schedule_requests(
        self, limit: int = 100
    ) -> list[ReminderScheduleRequestView]:
        raise NotImplementedError

    async def mark_request_materialized(self, request_id: UUID) -> None:
        raise NotImplementedError

    async def mark_request_failed(self, request_id: UUID, error_message: str) -> None:
        raise NotImplementedError

    async def get_protocol_user_id(self, protocol_id: UUID) -> str | None:
        raise NotImplementedError

    async def list_pulse_plan_entries(
        self, pulse_plan_id: UUID
    ) -> list[PulsePlanEntryView]:
        raise NotImplementedError

    async def get_reminder_settings(self, user_id: str) -> ReminderSettingsView | None:
        raise NotImplementedError

    async def upsert_reminder_settings(
        self,
        user_id: str,
        reminders_enabled: bool,
        preferred_reminder_time_local: time | None,
        timezone_name: str | None,
    ) -> ReminderSettingsView:
        raise NotImplementedError

    async def list_existing_materialized_entry_ids(
        self, pulse_plan_entry_ids: list[UUID]
    ) -> set[UUID]:
        raise NotImplementedError

    async def create_protocol_reminder(
        self,
        *,
        protocol_id: UUID,
        pulse_plan_id: UUID,
        pulse_plan_entry_id: UUID,
        user_id: str,
        reminder_kind: str,
        scheduled_at_utc: datetime,
        scheduled_local_date: date,
        scheduled_local_time: time,
        timezone_name: str,
        status: str,
        is_enabled: bool,
        injection_event_key: str,
        day_offset: int,
        payload_json: dict,
    ) -> None:
        raise NotImplementedError

    async def enqueue_event(
        self, *, event_type: str, aggregate_type: str, aggregate_id: UUID, payload: dict
    ) -> None:
        raise NotImplementedError

    async def get_diagnostics(self) -> ReminderDiagnostics:
        raise NotImplementedError
