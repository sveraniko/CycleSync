from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

from app.application.reminders.service import ReminderApplicationService
from app.application.reminders.schemas import (
    PulsePlanEntryView,
    ReminderDiagnostics,
    ReminderRuntimeView,
    ReminderScheduleRequestView,
    ReminderSettingsView,
    SentMessageRef,
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
        rid = uuid4()
        self.runtime = ReminderRuntimeView(
            reminder_id=rid,
            protocol_id=self.request.protocol_id,
            pulse_plan_id=self.request.pulse_plan_id,
            user_id=self.protocol_user,
            status="scheduled",
            scheduled_at_utc=now - timedelta(minutes=1),
            injection_event_key="evt_1",
            payload_json={"computed_mg": 100.0, "volume_ml": 1.0, "product_id": "p1"},
            delivery_attempt_count=0,
            awaiting_action_until_utc=None,
            snoozed_until_utc=None,
            last_message_chat_id="100",
            last_message_id="99",
        )
        self.created = []
        self.materialized = []
        self.failed = []
        self.events = []
        self.adherence_events = []
        self.action_status = "awaiting_action"
        self.expire_list: list[ReminderRuntimeView] = []
        self.anchor_date = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc).date()

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

    async def claim_due_reminders(self, *, now_utc, limit=100):
        if self.runtime.status == "scheduled" and self.runtime.scheduled_at_utc <= now_utc:
            return [self.runtime]
        if (
            self.runtime.status == "snoozed"
            and self.runtime.snoozed_until_utc
            and self.runtime.snoozed_until_utc <= now_utc
        ):
            return [self.runtime]
        return []

    async def mark_delivery_success(self, **kwargs):
        self.runtime.status = "awaiting_action"
        self.runtime.awaiting_action_until_utc = kwargs["awaiting_action_until_utc"]
        self.runtime.snoozed_until_utc = None
        self.runtime.last_message_chat_id = kwargs["chat_id"]
        self.runtime.last_message_id = kwargs["message_id"]
        return True

    async def mark_delivery_failed(self, **kwargs):
        self.runtime.status = "failed_delivery"

    async def expire_due_awaiting_actions(self, *, now_utc):
        return self.expire_list

    async def mark_cleaned(self, reminder_id, *, now_utc):
        self.runtime.status = "cleaned"
        self.runtime.last_message_chat_id = None
        self.runtime.last_message_id = None

    async def mark_message_cleaned(self, reminder_id, *, now_utc):
        self.runtime.last_message_chat_id = None
        self.runtime.last_message_id = None

    async def get_reminder_for_action(self, reminder_id):
        return self.runtime

    async def apply_user_action(self, **kwargs):
        action_code = kwargs["action_code"]
        if self.action_status in {"completed", "skipped"}:
            return self.action_status, True
        mapping = {"done": "completed", "skip": "skipped", "snooze": "snoozed"}
        self.action_status = mapping[action_code]
        self.runtime.status = self.action_status
        if action_code == "snooze":
            self.runtime.snoozed_until_utc = kwargs["snoozed_until_utc"]
            self.runtime.awaiting_action_until_utc = None
        return self.action_status, False

    async def enqueue_event(self, **kwargs):
        self.events.append(kwargs)

    async def record_adherence_event(self, **kwargs):
        self.adherence_events.append(kwargs)

    async def get_diagnostics(self):
        return ReminderDiagnostics(0, 0, len(self.created), {"scheduled": 1}, 0)

    async def get_protocol_schedule_anchor_date(self, protocol_id):
        return self.anchor_date


class FakeGateway:
    def __init__(self):
        self.sent = []
        self.cleaned = []

    async def send_reminder(self, *, user_id, text, callback_prefix):
        self.sent.append((user_id, text, callback_prefix))
        return SentMessageRef(chat_id="100", message_id="101")

    async def cleanup_message(self, *, chat_id, message_id, text):
        self.cleaned.append((chat_id, message_id, text))


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


def test_due_selection_and_delivery_path() -> None:
    repo = FakeReminderRepo()
    gateway = FakeGateway()
    service = ReminderApplicationService(repo)

    import asyncio

    report = asyncio.run(service.dispatch_due_reminders(delivery_gateway=gateway))
    assert report.due_selected == 1
    assert report.sent == 1
    assert report.failed_delivery == 0
    assert gateway.sent


def test_done_transition_records_adherence() -> None:
    repo = FakeReminderRepo()
    gateway = FakeGateway()
    service = ReminderApplicationService(repo)

    import asyncio

    result = asyncio.run(
        service.handle_reminder_action(
            reminder_id=repo.runtime.reminder_id,
            action_code="done",
            delivery_gateway=gateway,
        )
    )
    assert result.status == "completed"
    assert repo.adherence_events[-1]["action_code"] == "done"


def test_snooze_transition_records_adherence() -> None:
    repo = FakeReminderRepo()
    service = ReminderApplicationService(repo)

    import asyncio

    result = asyncio.run(
        service.handle_reminder_action(
            reminder_id=repo.runtime.reminder_id,
            action_code="snooze",
        )
    )
    assert result.status == "snoozed"
    assert repo.adherence_events[-1]["action_code"] == "snooze"


def test_snooze_is_not_terminal_and_is_redispatched_when_due() -> None:
    repo = FakeReminderRepo()
    gateway = FakeGateway()
    service = ReminderApplicationService(repo, snooze_minutes=10)

    import asyncio

    t0 = datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc)
    report1 = asyncio.run(
        service.dispatch_due_reminders(delivery_gateway=gateway, now_utc=t0)
    )
    assert report1.sent == 1
    assert repo.runtime.status == "awaiting_action"
    first_message_id = repo.runtime.last_message_id

    action_result = asyncio.run(
        service.handle_reminder_action(
            reminder_id=repo.runtime.reminder_id,
            action_code="snooze",
            delivery_gateway=gateway,
            now_utc=t0,
        )
    )
    assert action_result.status == "snoozed"
    assert repo.runtime.status == "snoozed"
    assert repo.runtime.last_message_id is None
    assert gateway.cleaned[-1][1] == first_message_id

    report2 = asyncio.run(
        service.dispatch_due_reminders(
            delivery_gateway=gateway,
            now_utc=t0 + timedelta(minutes=9),
        )
    )
    assert report2.sent == 0

    report3 = asyncio.run(
        service.dispatch_due_reminders(
            delivery_gateway=gateway,
            now_utc=t0 + timedelta(minutes=10),
        )
    )
    assert report3.sent == 1
    assert repo.runtime.status == "awaiting_action"
    assert len(gateway.sent) == 2


def test_skip_transition_records_adherence() -> None:
    repo = FakeReminderRepo()
    service = ReminderApplicationService(repo)

    import asyncio

    result = asyncio.run(
        service.handle_reminder_action(
            reminder_id=repo.runtime.reminder_id,
            action_code="skip",
        )
    )
    assert result.status == "skipped"
    assert repo.adherence_events[-1]["action_code"] == "skip"


def test_expiry_path_and_cleanup() -> None:
    repo = FakeReminderRepo()
    repo.expire_list = [repo.runtime]
    gateway = FakeGateway()
    service = ReminderApplicationService(repo)

    import asyncio

    report = asyncio.run(service.dispatch_due_reminders(delivery_gateway=gateway))
    assert report.expired == 1
    assert report.cleaned == 1
    assert repo.adherence_events[-1]["action_code"] == "expired"
    assert gateway.cleaned


def test_stale_message_cleanup_behavior() -> None:
    repo = FakeReminderRepo()
    gateway = FakeGateway()
    service = ReminderApplicationService(repo)

    import asyncio

    asyncio.run(
        service.handle_reminder_action(
            reminder_id=repo.runtime.reminder_id,
            action_code="done",
            delivery_gateway=gateway,
        )
    )
    assert gateway.cleaned[-1][0] == "100"


def test_idempotent_callback_behavior() -> None:
    repo = FakeReminderRepo()
    repo.action_status = "completed"
    service = ReminderApplicationService(repo)

    import asyncio

    result = asyncio.run(
        service.handle_reminder_action(
            reminder_id=repo.runtime.reminder_id,
            action_code="done",
        )
    )
    assert result.idempotent is True
    assert repo.adherence_events == []


def test_materialization_uses_protocol_anchor_when_scheduled_day_missing() -> None:
    repo = FakeReminderRepo()
    repo.entries[0] = PulsePlanEntryView(
        entry_id=repo.entries[0].entry_id,
        day_offset=2,
        scheduled_day=None,
        injection_event_key=repo.entries[0].injection_event_key,
        product_id=repo.entries[0].product_id,
        ingredient_context=repo.entries[0].ingredient_context,
        volume_ml=repo.entries[0].volume_ml,
        computed_mg=repo.entries[0].computed_mg,
        sequence_no=repo.entries[0].sequence_no,
    )
    repo.request.created_at = datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc)
    repo.anchor_date = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc).date()
    service = ReminderApplicationService(repo)

    import asyncio

    asyncio.run(service.materialize_requested_schedules())
    assert repo.created[0]["scheduled_local_date"] == datetime(
        2026, 4, 3, 0, 0, tzinfo=timezone.utc
    ).date()


def test_materialization_prefers_entry_scheduled_day_over_anchor() -> None:
    repo = FakeReminderRepo()
    explicit_day = datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc).date()
    repo.entries[0] = PulsePlanEntryView(
        entry_id=repo.entries[0].entry_id,
        day_offset=10,
        scheduled_day=explicit_day,
        injection_event_key=repo.entries[0].injection_event_key,
        product_id=repo.entries[0].product_id,
        ingredient_context=repo.entries[0].ingredient_context,
        volume_ml=repo.entries[0].volume_ml,
        computed_mg=repo.entries[0].computed_mg,
        sequence_no=repo.entries[0].sequence_no,
    )
    repo.anchor_date = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc).date()
    service = ReminderApplicationService(repo)

    import asyncio

    asyncio.run(service.materialize_requested_schedules())
    assert repo.created[0]["scheduled_local_date"] == explicit_day


def test_adherence_event_recording_payload_contains_reminder_id() -> None:
    repo = FakeReminderRepo()
    service = ReminderApplicationService(repo)

    import asyncio

    asyncio.run(
        service.handle_reminder_action(
            reminder_id=repo.runtime.reminder_id,
            action_code="done",
        )
    )
    assert repo.adherence_events[-1]["reminder_id"] == repo.runtime.reminder_id
