from datetime import datetime, time
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.reminders.repository import ReminderRepository
from app.application.reminders.schemas import (
    PulsePlanEntryView,
    ReminderDiagnostics,
    ReminderRuntimeView,
    ReminderScheduleRequestView,
    ReminderSettingsView,
)
from app.domain.models.ops import OutboxEvent
from app.domain.models.protocols import Protocol
from app.domain.models.pulse_engine import PulsePlanEntryRecord
from app.domain.models.reminders import (
    ProtocolAdherenceEvent,
    ProtocolReminder,
    ReminderScheduleRequest,
)
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

    async def claim_due_reminders(
        self, *, now_utc: datetime, limit: int = 100
    ) -> list[ReminderRuntimeView]:
        async with self.session_factory() as session:
            rows = await session.scalars(
                select(ProtocolReminder)
                .where(
                    ProtocolReminder.is_enabled.is_(True),
                    or_(
                        and_(
                            ProtocolReminder.status == "scheduled",
                            ProtocolReminder.scheduled_at_utc <= now_utc,
                        ),
                        and_(
                            ProtocolReminder.status == "snoozed",
                            ProtocolReminder.snoozed_until_utc.is_not(None),
                            ProtocolReminder.snoozed_until_utc <= now_utc,
                        ),
                    ),
                )
                .order_by(
                    ProtocolReminder.scheduled_at_utc.asc(), ProtocolReminder.id.asc()
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            found = list(rows)
            out = []
            for row in found:
                row.status = "delivery_in_progress"
                session.add(row)
                out.append(self._to_runtime_view(row))
            await session.commit()
            return out

    async def mark_delivery_success(
        self,
        *,
        reminder_id: UUID,
        sent_at: datetime,
        awaiting_action_until_utc: datetime,
        chat_id: str,
        message_id: str,
    ) -> bool:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(ProtocolReminder).where(ProtocolReminder.id == reminder_id)
            )
            if row is None:
                return False
            row.delivery_attempt_count += 1
            row.sent_at = sent_at
            row.awaiting_action_until_utc = awaiting_action_until_utc
            row.last_message_chat_id = chat_id
            row.last_message_id = message_id
            row.last_delivery_error = None
            row.status = "awaiting_action"
            row.snoozed_until_utc = None
            session.add(row)
            await session.commit()
            return True

    async def mark_delivery_failed(self, *, reminder_id: UUID, error: str) -> None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(ProtocolReminder).where(ProtocolReminder.id == reminder_id)
            )
            if row is None:
                return
            row.delivery_attempt_count += 1
            row.last_delivery_error = error[:255]
            row.status = "failed_delivery"
            session.add(row)
            await session.commit()

    async def expire_due_awaiting_actions(
        self, *, now_utc: datetime
    ) -> list[ReminderRuntimeView]:
        async with self.session_factory() as session:
            rows = await session.scalars(
                select(ProtocolReminder)
                .where(
                    ProtocolReminder.status == "awaiting_action",
                    ProtocolReminder.awaiting_action_until_utc.is_not(None),
                    ProtocolReminder.awaiting_action_until_utc <= now_utc,
                )
                .with_for_update(skip_locked=True)
            )
            found = list(rows)
            out = []
            for row in found:
                row.status = "expired"
                row.acted_at = now_utc
                row.action_code = "expired"
                row.clean_after_utc = now_utc
                session.add(row)
                out.append(self._to_runtime_view(row))
            await session.commit()
            return out

    async def mark_cleaned(self, reminder_id: UUID, *, now_utc: datetime) -> None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(ProtocolReminder).where(ProtocolReminder.id == reminder_id)
            )
            if row is None:
                return
            row.status = "cleaned"
            row.clean_after_utc = now_utc
            session.add(row)
            await session.commit()

    async def get_reminder_for_action(
        self, reminder_id: UUID
    ) -> ReminderRuntimeView | None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(ProtocolReminder).where(ProtocolReminder.id == reminder_id)
            )
            if row is None:
                return None
            return self._to_runtime_view(row)

    async def apply_user_action(
        self,
        *,
        reminder_id: UUID,
        action_code: str,
        acted_at: datetime,
        snoozed_until_utc: datetime | None,
    ) -> tuple[str, bool]:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(ProtocolReminder)
                .where(ProtocolReminder.id == reminder_id)
                .with_for_update()
            )
            if row is None:
                return "not_found", True

            if row.status in {
                "completed",
                "skipped",
                "expired",
                "cancelled",
                "cleaned",
            }:
                return row.status, True

            if action_code == "done":
                row.status = "completed"
                row.action_code = "done"
                row.acted_at = acted_at
                row.clean_after_utc = acted_at
            elif action_code == "skip":
                row.status = "skipped"
                row.action_code = "skip"
                row.acted_at = acted_at
                row.clean_after_utc = acted_at
            elif action_code == "snooze":
                row.status = "snoozed"
                row.action_code = "snooze"
                row.acted_at = acted_at
                row.snoozed_until_utc = snoozed_until_utc
                row.clean_after_utc = acted_at
            else:
                return row.status, True

            session.add(row)
            await session.commit()
            return row.status, False

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
        async with self.session_factory() as session:
            session.add(
                ProtocolAdherenceEvent(
                    protocol_id=protocol_id,
                    pulse_plan_id=pulse_plan_id,
                    reminder_id=reminder_id,
                    user_id=user_id,
                    action_code=action_code,
                    occurred_at=occurred_at,
                    payload_json=payload_json,
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
            state_rows = await session.execute(
                select(
                    ProtocolReminder.status, func.count(ProtocolReminder.id)
                ).group_by(ProtocolReminder.status)
            )
            failed_delivery = await session.scalar(
                select(func.count(ProtocolReminder.id)).where(
                    ProtocolReminder.status == "failed_delivery"
                )
            )
            return ReminderDiagnostics(
                pending_requests=int(pending or 0),
                failed_requests=int(failed or 0),
                materialized_rows=int(materialized_rows or 0),
                status_counts={k: int(v) for k, v in state_rows.all()},
                failed_delivery_count=int(failed_delivery or 0),
            )

    def _to_runtime_view(self, row: ProtocolReminder) -> ReminderRuntimeView:
        return ReminderRuntimeView(
            reminder_id=row.id,
            protocol_id=row.protocol_id,
            pulse_plan_id=row.pulse_plan_id,
            user_id=row.user_id,
            status=row.status,
            scheduled_at_utc=row.scheduled_at_utc,
            injection_event_key=row.injection_event_key,
            payload_json=row.payload_json,
            delivery_attempt_count=row.delivery_attempt_count,
            awaiting_action_until_utc=row.awaiting_action_until_utc,
            snoozed_until_utc=row.snoozed_until_utc,
            last_message_chat_id=row.last_message_chat_id,
            last_message_id=row.last_message_id,
        )
