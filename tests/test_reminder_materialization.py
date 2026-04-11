from datetime import datetime, time, timezone
from uuid import uuid4

from app.application.reminders.service import ReminderApplicationService
from app.application.reminders.schemas import (
    PulsePlanEntryView,
    ReminderDiagnostics,
    ReminderScheduleRequestView,
    ReminderSettingsView,
)


class FakeReminderRepo:
    def __init__(self):
        now = datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc)
        self.request = ReminderScheduleRequestView(
            request_id=uuid4(),
            protocol_id=uuid4(),
            pulse_plan_id=uuid4(),
            status="requested",
            created_at=now,
        )
        self.protocol_user = "tg:100"
        self.settings = ReminderSettingsView(
            user_id=self.protocol_user,
            reminders_enabled=True,
            preferred_reminder_time_local=time(8, 30),
            timezone_name="Europe/Moscow",
        )
        self.entries = [
            PulsePlanEntryView(
                entry_id=uuid4(),
                day_offset=1,
                scheduled_day=None,
                injection_event_key="evt_1",
                product_id=uuid4(),
                ingredient_context="ctx",
                volume_ml=1.0,
                computed_mg=100.0,
                sequence_no=0,
            )
        ]
        self.created = []
        self.materialized = []
        self.failed = []
        self.events = []

    async def dequeue_requested_schedule_requests(self, limit=100):
        return [self.request]

    async def mark_request_materialized(self, request_id):
        self.materialized.append(request_id)

    async def mark_request_failed(self, request_id, error_message):
        self.failed.append((request_id, error_message))

    async def get_protocol_user_id(self, protocol_id):
        return self.protocol_user

    async def list_pulse_plan_entries(self, pulse_plan_id):
        return self.entries

    async def get_reminder_settings(self, user_id):
        return self.settings

    async def upsert_reminder_settings(
        self, user_id, reminders_enabled, preferred_reminder_time_local, timezone_name
    ):
        self.settings = ReminderSettingsView(
            user_id=user_id,
            reminders_enabled=reminders_enabled,
            preferred_reminder_time_local=preferred_reminder_time_local,
            timezone_name=timezone_name,
        )
        return self.settings

    async def list_existing_materialized_entry_ids(self, pulse_plan_entry_ids):
        return set()

    async def create_protocol_reminder(self, **kwargs):
        self.created.append(kwargs)

    async def enqueue_event(self, **kwargs):
        self.events.append(kwargs)

    async def get_diagnostics(self):
        return ReminderDiagnostics(0, 0, len(self.created))


def test_materialization_idempotent_and_timezone_applied() -> None:
    repo = FakeReminderRepo()
    service = ReminderApplicationService(
        repo, default_timezone="UTC", default_local_time=time(9, 0)
    )

    import asyncio

    first = asyncio.run(service.materialize_requested_schedules())
    assert len(first) == 1
    assert first[0].created_count == 1
    assert repo.created[0]["timezone_name"] == "Europe/Moscow"
    assert repo.created[0]["scheduled_local_time"] == time(8, 30)
    assert repo.created[0]["scheduled_at_utc"].hour == 5

    async def existing(_ids):
        return {repo.entries[0].entry_id}

    repo.list_existing_materialized_entry_ids = existing
    second = asyncio.run(service.materialize_requested_schedules())
    assert second[0].existing_count == 1
    assert len(repo.created) == 1


def test_disabled_reminders_materialize_suppressed() -> None:
    repo = FakeReminderRepo()
    repo.settings = ReminderSettingsView(
        user_id=repo.protocol_user,
        reminders_enabled=False,
        preferred_reminder_time_local=time(10, 0),
        timezone_name="UTC",
    )
    service = ReminderApplicationService(repo)

    import asyncio

    result = asyncio.run(service.materialize_requested_schedules())
    assert result[0].suppressed_count == 1
    assert repo.created[0]["status"] == "suppressed"
    assert repo.created[0]["is_enabled"] is False


def test_request_status_transitions_to_failed_on_missing_protocol() -> None:
    repo = FakeReminderRepo()
    repo.protocol_user = None
    service = ReminderApplicationService(repo)

    import asyncio

    result = asyncio.run(service.materialize_requested_schedules())
    assert result == []
    assert len(repo.failed) == 1
    assert repo.materialized == []
