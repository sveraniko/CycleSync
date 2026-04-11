from datetime import time
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.reminders.repository import ReminderRepository
from app.application.reminders.schemas import (
    PulsePlanEntryView,
    ReminderDiagnostics,
    ReminderScheduleRequestView,
    ReminderSettingsView,
)
from app.domain.models.ops import OutboxEvent
from app.domain.models.protocols import Protocol
from app.domain.models.pulse_engine import PulsePlanEntryRecord
from app.domain.models.reminders import ProtocolReminder, ReminderScheduleRequest
from app.domain.models.user_registry import UserNotificationSettings


class SqlAlchemyReminderRepository(ReminderRepository):
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def dequeue_requested_schedule_requests(
        self, limit: int = 100
    ) -> list[ReminderScheduleRequestView]:
        async with self.session_factory() as session:
            rows = await session.scalars(
                select(ReminderScheduleRequest)
                .where(ReminderScheduleRequest.status == "requested")
                .order_by(ReminderScheduleRequest.created_at.asc())
                .limit(limit)
            )
            return [
                ReminderScheduleRequestView(
                    request_id=row.id,
                    protocol_id=row.protocol_id,
                    pulse_plan_id=row.pulse_plan_id,
                    status=row.status,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    async def mark_request_materialized(self, request_id: UUID) -> None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(ReminderScheduleRequest).where(
                    ReminderScheduleRequest.id == request_id
                )
            )
            if row is None:
                return
            row.status = "materialized"
            row.error_message = None
            session.add(row)
            await session.commit()

    async def mark_request_failed(self, request_id: UUID, error_message: str) -> None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(ReminderScheduleRequest).where(
                    ReminderScheduleRequest.id == request_id
                )
            )
            if row is None:
                return
            row.status = "failed"
            row.error_message = error_message[:255]
            session.add(row)
            await session.commit()

    async def get_protocol_user_id(self, protocol_id: UUID) -> str | None:
        async with self.session_factory() as session:
            return await session.scalar(
                select(Protocol.user_id).where(Protocol.id == protocol_id)
            )

    async def list_pulse_plan_entries(
        self, pulse_plan_id: UUID
    ) -> list[PulsePlanEntryView]:
        async with self.session_factory() as session:
            rows = await session.scalars(
                select(PulsePlanEntryRecord)
                .where(PulsePlanEntryRecord.pulse_plan_id == pulse_plan_id)
                .order_by(
                    PulsePlanEntryRecord.day_offset.asc(),
                    PulsePlanEntryRecord.sequence_no.asc(),
                )
            )
            return [
                PulsePlanEntryView(
                    entry_id=row.id,
                    day_offset=row.day_offset,
                    scheduled_day=row.scheduled_day,
                    injection_event_key=row.injection_event_key,
                    product_id=row.product_id,
                    ingredient_context=row.ingredient_context,
                    volume_ml=float(row.volume_ml),
                    computed_mg=float(row.computed_mg),
                    sequence_no=row.sequence_no,
                )
                for row in rows
            ]

    async def get_reminder_settings(self, user_id: str) -> ReminderSettingsView | None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(UserNotificationSettings).where(
                    UserNotificationSettings.user_id == user_id
                )
            )
            if row is None:
                return None
            return ReminderSettingsView(
                user_id=row.user_id,
                reminders_enabled=row.reminders_enabled,
                preferred_reminder_time_local=row.preferred_reminder_time_local,
                timezone_name=row.timezone_name,
            )

    async def upsert_reminder_settings(
        self,
        user_id: str,
        reminders_enabled: bool,
        preferred_reminder_time_local: time | None,
        timezone_name: str | None,
    ) -> ReminderSettingsView:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(UserNotificationSettings).where(
                    UserNotificationSettings.user_id == user_id
                )
            )
            if row is None:
                row = UserNotificationSettings(user_id=user_id)
            row.reminders_enabled = reminders_enabled
            row.preferred_reminder_time_local = preferred_reminder_time_local
            row.timezone_name = timezone_name
            session.add(row)
            await session.commit()
            return ReminderSettingsView(
                user_id=row.user_id,
                reminders_enabled=row.reminders_enabled,
                preferred_reminder_time_local=row.preferred_reminder_time_local,
                timezone_name=row.timezone_name,
            )

    async def list_existing_materialized_entry_ids(
        self, pulse_plan_entry_ids: list[UUID]
    ) -> set[UUID]:
        if not pulse_plan_entry_ids:
            return set()
        async with self.session_factory() as session:
            rows = await session.scalars(
                select(ProtocolReminder.pulse_plan_entry_id).where(
                    ProtocolReminder.pulse_plan_entry_id.in_(pulse_plan_entry_ids),
                    ProtocolReminder.reminder_kind == "injection",
                )
            )
            return set(rows)

    async def create_protocol_reminder(self, **kwargs) -> None:
        async with self.session_factory() as session:
            session.add(ProtocolReminder(**kwargs))
            await session.commit()

    async def enqueue_event(
        self, *, event_type: str, aggregate_type: str, aggregate_id: UUID, payload: dict
    ) -> None:
        async with self.session_factory() as session:
            session.add(
                OutboxEvent(
                    event_type=event_type,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    payload_json=payload,
                    status="pending",
                )
            )
            await session.commit()

    async def get_diagnostics(self) -> ReminderDiagnostics:
        async with self.session_factory() as session:
            pending = await session.scalar(
                select(func.count(ReminderScheduleRequest.id)).where(
                    ReminderScheduleRequest.status == "requested"
                )
            )
            failed = await session.scalar(
                select(func.count(ReminderScheduleRequest.id)).where(
                    ReminderScheduleRequest.status == "failed"
                )
            )
            materialized_rows = await session.scalar(
                select(func.count(ProtocolReminder.id))
            )
            return ReminderDiagnostics(
                pending_requests=int(pending or 0),
                failed_requests=int(failed or 0),
                materialized_rows=int(materialized_rows or 0),
            )
