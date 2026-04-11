from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.application.reminders.repository import ReminderRepository
from app.application.reminders.schemas import (
    ReminderActionResult,
    ReminderDispatchReport,
    ReminderMaterializationResult,
    ReminderSettingsView,
    SentMessageRef,
)


class ReminderDeliveryGateway:
    async def send_reminder(
        self,
        *,
        user_id: str,
        text: str,
        callback_prefix: str,
    ) -> SentMessageRef:
        raise NotImplementedError

    async def cleanup_message(
        self, *, chat_id: str, message_id: str, text: str
    ) -> None:
        raise NotImplementedError


class ReminderApplicationService:
    def __init__(
        self,
        repository: ReminderRepository,
        *,
        default_timezone: str = "UTC",
        default_local_time: time = time(9, 0),
        awaiting_action_ttl_minutes: int = 180,
        snooze_minutes: int = 30,
    ) -> None:
        self.repository = repository
        self.default_timezone = default_timezone
        self.default_local_time = default_local_time
        self.awaiting_action_ttl_minutes = awaiting_action_ttl_minutes
        self.snooze_minutes = snooze_minutes

    async def materialize_requested_schedules(
        self, *, limit: int = 100
    ) -> list[ReminderMaterializationResult]:
        requests = await self.repository.dequeue_requested_schedule_requests(
            limit=limit
        )
        results: list[ReminderMaterializationResult] = []

        for request in requests:
            await self.repository.enqueue_event(
                event_type="reminder_schedule_materialization_started",
                aggregate_type="reminder_schedule_request",
                aggregate_id=request.request_id,
                payload={
                    "protocol_id": str(request.protocol_id),
                    "pulse_plan_id": str(request.pulse_plan_id),
                },
            )
            try:
                result = await self._materialize_single_request(request)
            except Exception as exc:
                await self.repository.mark_request_failed(
                    request.request_id, str(exc)[:250]
                )
                await self.repository.enqueue_event(
                    event_type="reminder_schedule_materialization_failed",
                    aggregate_type="reminder_schedule_request",
                    aggregate_id=request.request_id,
                    payload={
                        "error": str(exc),
                        "protocol_id": str(request.protocol_id),
                    },
                )
                continue

            await self.repository.mark_request_materialized(request.request_id)
            await self.repository.enqueue_event(
                event_type="reminder_schedule_materialized",
                aggregate_type="reminder_schedule_request",
                aggregate_id=request.request_id,
                payload={
                    "protocol_id": str(request.protocol_id),
                    "pulse_plan_id": str(request.pulse_plan_id),
                    "created_count": result.created_count,
                    "existing_count": result.existing_count,
                    "suppressed_count": result.suppressed_count,
                },
            )
            results.append(result)

        return results

    async def dispatch_due_reminders(
        self,
        *,
        delivery_gateway: ReminderDeliveryGateway,
        now_utc: datetime | None = None,
        limit: int = 100,
    ) -> ReminderDispatchReport:
        now = now_utc or datetime.now(timezone.utc)
        due = await self.repository.claim_due_reminders(now_utc=now, limit=limit)
        sent = 0
        failed = 0

        for reminder in due:
            try:
                text = self._render_reminder_text(reminder)
                sent_ref = await delivery_gateway.send_reminder(
                    user_id=reminder.user_id,
                    text=text,
                    callback_prefix=f"reminder:{reminder.reminder_id}",
                )
                await self.repository.mark_delivery_success(
                    reminder_id=reminder.reminder_id,
                    sent_at=now,
                    awaiting_action_until_utc=now
                    + timedelta(minutes=self.awaiting_action_ttl_minutes),
                    chat_id=sent_ref.chat_id,
                    message_id=sent_ref.message_id,
                )
                sent += 1
            except Exception as exc:
                await self.repository.mark_delivery_failed(
                    reminder_id=reminder.reminder_id, error=str(exc)
                )
                failed += 1

        expired = await self.repository.expire_due_awaiting_actions(now_utc=now)
        cleaned = 0
        for reminder in expired:
            if reminder.last_message_chat_id and reminder.last_message_id:
                await delivery_gateway.cleanup_message(
                    chat_id=reminder.last_message_chat_id,
                    message_id=reminder.last_message_id,
                    text="Reminder expired. Marked as non-actionable.",
                )
            await self.repository.mark_cleaned(reminder.reminder_id, now_utc=now)
            await self.repository.record_adherence_event(
                protocol_id=reminder.protocol_id,
                pulse_plan_id=reminder.pulse_plan_id,
                reminder_id=reminder.reminder_id,
                user_id=reminder.user_id,
                action_code="expired",
                occurred_at=now,
                payload_json={"source": "expiry_worker"},
            )
            cleaned += 1

        return ReminderDispatchReport(
            due_selected=len(due),
            sent=sent,
            expired=len(expired),
            cleaned=cleaned,
            failed_delivery=failed,
        )

    async def handle_reminder_action(
        self,
        *,
        reminder_id,
        action_code: str,
        delivery_gateway: ReminderDeliveryGateway | None = None,
        now_utc: datetime | None = None,
    ) -> ReminderActionResult:
        now = now_utc or datetime.now(timezone.utc)
        reminder = await self.repository.get_reminder_for_action(reminder_id)
        if reminder is None:
            return ReminderActionResult(
                reminder_id=reminder_id,
                action_code=action_code,
                status="not_found",
                idempotent=True,
            )

        snoozed_until = None
        if action_code == "snooze":
            snoozed_until = now + timedelta(minutes=self.snooze_minutes)

        status, idempotent = await self.repository.apply_user_action(
            reminder_id=reminder_id,
            action_code=action_code,
            acted_at=now,
            snoozed_until_utc=snoozed_until,
        )

        if status in {"completed", "skipped", "snoozed"} and not idempotent:
            await self.repository.record_adherence_event(
                protocol_id=reminder.protocol_id,
                pulse_plan_id=reminder.pulse_plan_id,
                reminder_id=reminder.reminder_id,
                user_id=reminder.user_id,
                action_code=action_code,
                occurred_at=now,
                payload_json={"injection_event_key": reminder.injection_event_key},
            )

        if (
            status in {"completed", "skipped", "snoozed"}
            and delivery_gateway
            and reminder.last_message_chat_id
            and reminder.last_message_id
        ):
            await delivery_gateway.cleanup_message(
                chat_id=reminder.last_message_chat_id,
                message_id=reminder.last_message_id,
                text=f"Reminder {status}.",
            )
            if status == "snoozed":
                await self.repository.mark_message_cleaned(reminder_id, now_utc=now)
            else:
                await self.repository.mark_cleaned(reminder_id, now_utc=now)

        return ReminderActionResult(
            reminder_id=reminder_id,
            action_code=action_code,
            status=status,
            idempotent=idempotent,
        )

    async def update_reminder_settings(
        self,
        *,
        user_id: str,
        reminders_enabled: bool,
        preferred_reminder_time_local: time | None,
        timezone_name: str | None,
    ) -> ReminderSettingsView:
        settings = await self.repository.upsert_reminder_settings(
            user_id=user_id,
            reminders_enabled=reminders_enabled,
            preferred_reminder_time_local=preferred_reminder_time_local,
            timezone_name=timezone_name,
        )
        await self.repository.enqueue_event(
            event_type="reminder_settings_updated",
            aggregate_type="user_notification_settings",
            aggregate_id=settings_user_uuid(user_id),
            payload={
                "user_id": user_id,
                "reminders_enabled": settings.reminders_enabled,
                "preferred_reminder_time_local": (
                    settings.preferred_reminder_time_local.isoformat()
                    if settings.preferred_reminder_time_local
                    else None
                ),
                "timezone_name": settings.timezone_name,
            },
        )
        return settings

    async def get_reminder_settings(self, user_id: str) -> ReminderSettingsView:
        settings = await self.repository.get_reminder_settings(user_id)
        if settings:
            return settings
        return ReminderSettingsView(
            user_id=user_id,
            reminders_enabled=True,
            preferred_reminder_time_local=None,
            timezone_name=None,
        )

    async def get_diagnostics(self):
        return await self.repository.get_diagnostics()

    async def rebuild_protocol_adherence_summary(self, protocol_id):
        return await self.repository.rebuild_adherence_summary_for_protocol(protocol_id)

    async def get_user_protocol_status(self, user_id: str):
        return await self.repository.get_protocol_status_for_user(user_id)

    async def _materialize_single_request(
        self, request
    ) -> ReminderMaterializationResult:
        user_id = await self.repository.get_protocol_user_id(request.protocol_id)
        if not user_id:
            raise ValueError("protocol_not_found")

        entries = await self.repository.list_pulse_plan_entries(request.pulse_plan_id)
        settings = await self.get_reminder_settings(user_id)

        entry_ids = [entry.entry_id for entry in entries]
        existing_entry_ids = await self.repository.list_existing_materialized_entry_ids(
            entry_ids
        )

        tz_name = settings.timezone_name or self.default_timezone
        local_tz = ZoneInfo(tz_name)
        local_time = settings.preferred_reminder_time_local or self.default_local_time
        status = "scheduled" if settings.reminders_enabled else "suppressed"

        created_count = 0
        existing_count = 0
        suppressed_count = 0
        anchor_date = await self.repository.get_protocol_schedule_anchor_date(
            request.protocol_id
        )

        for entry in entries:
            if entry.entry_id in existing_entry_ids:
                existing_count += 1
                continue

            local_date = entry.scheduled_day
            if local_date is None:
                if anchor_date is None:
                    raise ValueError("protocol_schedule_anchor_missing")
                local_date = anchor_date + timedelta_days(entry.day_offset)
            local_dt = datetime.combine(local_date, local_time, tzinfo=local_tz)
            utc_dt = local_dt.astimezone(timezone.utc)

            await self.repository.create_protocol_reminder(
                protocol_id=request.protocol_id,
                pulse_plan_id=request.pulse_plan_id,
                pulse_plan_entry_id=entry.entry_id,
                user_id=user_id,
                reminder_kind="injection",
                scheduled_at_utc=utc_dt,
                scheduled_local_date=local_date,
                scheduled_local_time=local_time,
                timezone_name=tz_name,
                status=status,
                is_enabled=settings.reminders_enabled,
                injection_event_key=entry.injection_event_key,
                day_offset=entry.day_offset,
                payload_json={
                    "product_id": str(entry.product_id),
                    "ingredient_context": entry.ingredient_context,
                    "volume_ml": float(entry.volume_ml),
                    "computed_mg": float(entry.computed_mg),
                    "sequence_no": entry.sequence_no,
                },
            )
            created_count += 1
            if not settings.reminders_enabled:
                suppressed_count += 1

        return ReminderMaterializationResult(
            request_id=request.request_id,
            created_count=created_count,
            existing_count=existing_count,
            suppressed_count=suppressed_count,
            status="materialized",
        )

    def _render_reminder_text(self, reminder) -> str:
        payload = reminder.payload_json or {}
        return (
            f"Injection reminder: {reminder.injection_event_key}\n"
            f"Product: {payload.get('product_id', 'n/a')}\n"
            f"mg: {payload.get('computed_mg', 'n/a')}\n"
            f"ml: {payload.get('volume_ml', 'n/a')}\n"
            "Select action: Done / Snooze / Skip"
        )


def settings_user_uuid(user_id: str):
    import uuid

    return uuid.uuid5(
        uuid.NAMESPACE_URL, f"cyclesync:user-notification-settings:{user_id}"
    )


def timedelta_days(days: int) -> timedelta:
    return timedelta(days=days)
