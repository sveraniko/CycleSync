from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.application.reminders.repository import ReminderRepository
from app.application.reminders.schemas import (
    ReminderMaterializationResult,
    ReminderSettingsView,
)


class ReminderApplicationService:
    def __init__(
        self,
        repository: ReminderRepository,
        *,
        default_timezone: str = "UTC",
        default_local_time: time = time(9, 0),
    ) -> None:
        self.repository = repository
        self.default_timezone = default_timezone
        self.default_local_time = default_local_time

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

        for entry in entries:
            if entry.entry_id in existing_entry_ids:
                existing_count += 1
                continue

            local_date = entry.scheduled_day or (
                request.created_at.date() + timedelta_days(entry.day_offset)
            )
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


def settings_user_uuid(user_id: str):
    import uuid

    return uuid.uuid5(
        uuid.NAMESPACE_URL, f"cyclesync:user-notification-settings:{user_id}"
    )


def timedelta_days(days: int) -> timedelta:
    return timedelta(days=days)
