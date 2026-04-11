from datetime import date, datetime, time
from uuid import UUID

from app.application.reminders.schemas import (
    PulsePlanEntryView,
    ReminderDiagnostics,
    ReminderRuntimeView,
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

    async def claim_due_reminders(
        self, *, now_utc: datetime, limit: int = 100
    ) -> list[ReminderRuntimeView]:
        raise NotImplementedError

    async def mark_delivery_success(
        self,
        *,
        reminder_id: UUID,
        sent_at: datetime,
        awaiting_action_until_utc: datetime,
        chat_id: str,
        message_id: str,
    ) -> bool:
        raise NotImplementedError

    async def mark_delivery_failed(self, *, reminder_id: UUID, error: str) -> None:
        raise NotImplementedError

    async def expire_due_awaiting_actions(
        self, *, now_utc: datetime
    ) -> list[ReminderRuntimeView]:
        raise NotImplementedError

    async def mark_cleaned(self, reminder_id: UUID, *, now_utc: datetime) -> None:
        raise NotImplementedError

    async def get_reminder_for_action(
        self, reminder_id: UUID
    ) -> ReminderRuntimeView | None:
        raise NotImplementedError

    async def apply_user_action(
        self,
        *,
        reminder_id: UUID,
        action_code: str,
        acted_at: datetime,
        snoozed_until_utc: datetime | None,
    ) -> tuple[str, bool]:
        raise NotImplementedError

    async def enqueue_event(
        self, *, event_type: str, aggregate_type: str, aggregate_id: UUID, payload: dict
    ) -> None:
        raise NotImplementedError

    async def record_adherence_event(
        self,
        *,
        protocol_id: UUID,
        pulse_plan_id: UUID,
        reminder_id: UUID,
        user_id: str,
        action_code: str,
        occurred_at: datetime,
        payload_json: dict,
    ) -> None:
        raise NotImplementedError

    async def get_diagnostics(self) -> ReminderDiagnostics:
        raise NotImplementedError
