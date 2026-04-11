from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.reminders.repository import ReminderRepository
from app.application.reminders.adherence import (
    AdherenceCounterSnapshot,
    classify_protocol_integrity,
    compute_consecutive_negative_windows,
)
from app.application.reminders.schemas import (
    ProtocolAdherenceSummaryView,
    ProtocolStatusView,
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
    ProtocolAdherenceSummary,
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
            row.last_message_chat_id = None
            row.last_message_id = None
            session.add(row)
            await session.commit()

    async def mark_message_cleaned(self, reminder_id: UUID, *, now_utc: datetime) -> None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(ProtocolReminder).where(ProtocolReminder.id == reminder_id)
            )
            if row is None:
                return
            row.clean_after_utc = now_utc
            row.last_message_chat_id = None
            row.last_message_id = None
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
                row.awaiting_action_until_utc = None
                row.snoozed_until_utc = None
            elif action_code == "skip":
                row.status = "skipped"
                row.action_code = "skip"
                row.acted_at = acted_at
                row.clean_after_utc = acted_at
                row.awaiting_action_until_utc = None
                row.snoozed_until_utc = None
            elif action_code == "snooze":
                row.status = "snoozed"
                row.action_code = "snooze"
                row.acted_at = acted_at
                row.snoozed_until_utc = snoozed_until_utc
                row.awaiting_action_until_utc = None
            else:
                return row.status, True

            session.add(row)
            await session.commit()
            return row.status, False

    async def get_protocol_schedule_anchor_date(
        self, protocol_id: UUID
    ) -> date | None:
        async with self.session_factory() as session:
            protocol = await session.scalar(
                select(Protocol).where(Protocol.id == protocol_id)
            )
            if protocol is None:
                return None

            snapshot = protocol.settings_snapshot_json or {}
            planned_start_raw = snapshot.get("planned_start_date")
            if isinstance(planned_start_raw, str):
                try:
                    return datetime.fromisoformat(planned_start_raw).date()
                except ValueError:
                    pass

            if protocol.activated_at is not None:
                return protocol.activated_at.date()
            return protocol.created_at.date()

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
            previous_state = await session.scalar(
                select(ProtocolAdherenceSummary.integrity_state).where(
                    ProtocolAdherenceSummary.protocol_id == protocol_id
                )
            )
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
            summary = await self._rebuild_protocol_summary_in_session(session, protocol_id)
            await self._emit_integrity_events(
                session=session,
                protocol_id=protocol_id,
                summary=summary,
                previous_state=previous_state,
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
            integrity_rows = await session.execute(
                select(
                    ProtocolAdherenceSummary.integrity_state,
                    func.count(ProtocolAdherenceSummary.id),
                ).group_by(ProtocolAdherenceSummary.integrity_state)
            )
            reason_rows = await session.execute(
                select(
                    ProtocolAdherenceSummary.integrity_reason_code,
                    func.count(ProtocolAdherenceSummary.id),
                )
                .where(ProtocolAdherenceSummary.integrity_reason_code.is_not(None))
                .group_by(ProtocolAdherenceSummary.integrity_reason_code)
            )
            integrity_counts = {k: int(v) for k, v in integrity_rows.all()}
            return ReminderDiagnostics(
                pending_requests=int(pending or 0),
                failed_requests=int(failed or 0),
                materialized_rows=int(materialized_rows or 0),
                status_counts={k: int(v) for k, v in state_rows.all()},
                failed_delivery_count=int(failed_delivery or 0),
                integrity_state_counts=integrity_counts,
                broken_protocol_count=int(integrity_counts.get("broken", 0)),
                degraded_protocol_count=int(integrity_counts.get("degraded", 0)),
                top_integrity_reason_codes={k: int(v) for k, v in reason_rows.all()},
            )

    async def rebuild_adherence_summary_for_protocol(
        self, protocol_id: UUID
    ) -> ProtocolAdherenceSummaryView | None:
        async with self.session_factory() as session:
            summary = await self._rebuild_protocol_summary_in_session(session, protocol_id)
            await session.commit()
            return summary

    async def get_protocol_status_for_user(self, user_id: str) -> ProtocolStatusView:
        async with self.session_factory() as session:
            active_protocol = await session.scalar(
                select(Protocol)
                .where(Protocol.user_id == user_id, Protocol.status == "active")
                .order_by(Protocol.created_at.desc())
            )
            if active_protocol is None:
                return ProtocolStatusView(
                    has_active_protocol=False,
                    integrity_state=None,
                    explanation="No active protocol.",
                    summary=None,
                )

            summary_row = await session.scalar(
                select(ProtocolAdherenceSummary).where(
                    ProtocolAdherenceSummary.protocol_id == active_protocol.id
                )
            )
            if summary_row is None:
                return ProtocolStatusView(
                    has_active_protocol=True,
                    integrity_state="healthy",
                    explanation="No adherence actions yet.",
                    summary=None,
                )

            summary = self._to_adherence_summary_view(summary_row)
            misses = summary.skipped_count + summary.expired_count
            explanation = (
                f"State={summary.integrity_state}. "
                f"Completion {summary.completion_rate:.0%}, misses {misses}."
            )
            return ProtocolStatusView(
                has_active_protocol=True,
                integrity_state=summary.integrity_state,
                explanation=explanation,
                summary=summary,
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

    @staticmethod
    def _to_adherence_summary_view(
        row: ProtocolAdherenceSummary,
    ) -> ProtocolAdherenceSummaryView:
        return ProtocolAdherenceSummaryView(
            protocol_id=row.protocol_id,
            pulse_plan_id=row.pulse_plan_id,
            user_id=row.user_id,
            completed_count=row.completed_count,
            skipped_count=row.skipped_count,
            snoozed_count=row.snoozed_count,
            expired_count=row.expired_count,
            total_actionable_count=row.total_actionable_count,
            completion_rate=float(row.completion_rate),
            skip_rate=float(row.skip_rate),
            expiry_rate=float(row.expiry_rate),
            last_action_at=row.last_action_at,
            integrity_state=row.integrity_state,
            integrity_reason_code=row.integrity_reason_code,
            broken_reason_code=row.broken_reason_code,
            integrity_detail_json=row.integrity_detail_json or {},
            updated_at=row.updated_at,
        )

    async def _rebuild_protocol_summary_in_session(
        self, session, protocol_id: UUID
    ) -> ProtocolAdherenceSummaryView | None:
        counts = (
            await session.execute(
                select(
                    ProtocolAdherenceEvent.action_code,
                    func.count(ProtocolAdherenceEvent.id),
                )
                .where(ProtocolAdherenceEvent.protocol_id == protocol_id)
                .group_by(ProtocolAdherenceEvent.action_code)
            )
        ).all()
        if not counts:
            return None

        latest = await session.scalar(
            select(ProtocolAdherenceEvent)
            .where(ProtocolAdherenceEvent.protocol_id == protocol_id)
            .order_by(ProtocolAdherenceEvent.occurred_at.desc())
        )
        if latest is None:
            return None

        count_map = {code: int(value) for code, value in counts}
        completed = count_map.get("done", 0)
        skipped = count_map.get("skip", 0)
        snoozed = count_map.get("snooze", 0)
        expired = count_map.get("expired", 0)
        actionable = completed + skipped + expired
        completion_rate = (completed / actionable) if actionable else 0.0
        skip_rate = (skipped / actionable) if actionable else 0.0
        expiry_rate = (expired / actionable) if actionable else 0.0

        recent_actions = list(
            await session.scalars(
                select(ProtocolAdherenceEvent.action_code)
                .where(ProtocolAdherenceEvent.protocol_id == protocol_id)
                .order_by(ProtocolAdherenceEvent.occurred_at.desc())
                .limit(12)
            )
        )
        consecutive_negative, consecutive_expired = compute_consecutive_negative_windows(
            recent_actions
        )
        classification = classify_protocol_integrity(
            AdherenceCounterSnapshot(
                completed_count=completed,
                skipped_count=skipped,
                snoozed_count=snoozed,
                expired_count=expired,
                total_actionable_count=actionable,
                completion_rate=completion_rate,
                skip_rate=skip_rate,
                expiry_rate=expiry_rate,
                last_action_at=latest.occurred_at,
                consecutive_negative_count=consecutive_negative,
                consecutive_expiry_count=consecutive_expired,
            )
        )

        row = await session.scalar(
            select(ProtocolAdherenceSummary).where(
                ProtocolAdherenceSummary.protocol_id == protocol_id
            )
        )
        if row is None:
            row = ProtocolAdherenceSummary(
                protocol_id=protocol_id,
                pulse_plan_id=latest.pulse_plan_id,
                user_id=latest.user_id,
            )
        row.pulse_plan_id = latest.pulse_plan_id
        row.user_id = latest.user_id
        row.completed_count = completed
        row.skipped_count = skipped
        row.snoozed_count = snoozed
        row.expired_count = expired
        row.total_actionable_count = actionable
        row.completion_rate = completion_rate
        row.skip_rate = skip_rate
        row.expiry_rate = expiry_rate
        row.last_action_at = latest.occurred_at
        row.integrity_state = classification.integrity_state
        row.integrity_reason_code = classification.reason_code
        row.broken_reason_code = (
            classification.reason_code if classification.integrity_state == "broken" else None
        )
        row.integrity_detail_json = classification.detail_payload
        session.add(row)

        protocol = await session.scalar(select(Protocol).where(Protocol.id == protocol_id))
        if protocol is not None:
            if classification.integrity_state in {"degraded", "broken"}:
                if protocol.protocol_integrity_flagged_at is None:
                    protocol.protocol_integrity_flagged_at = datetime.now(
                        latest.occurred_at.tzinfo
                    )
            if classification.integrity_state == "broken" and protocol.protocol_broken_at is None:
                protocol.protocol_broken_at = datetime.now(latest.occurred_at.tzinfo)
            session.add(protocol)
        await session.flush()
        return self._to_adherence_summary_view(row)

    async def _emit_integrity_events(
        self,
        *,
        session,
        protocol_id: UUID,
        summary: ProtocolAdherenceSummaryView | None,
        previous_state: str | None,
    ) -> None:
        if summary is None:
            return
        session.add(
            OutboxEvent(
                event_type="protocol_integrity_updated",
                aggregate_type="protocol",
                aggregate_id=protocol_id,
                payload_json={
                    "protocol_id": str(summary.protocol_id),
                    "user_id": summary.user_id,
                    "integrity_state": summary.integrity_state,
                    "integrity_reason_code": summary.integrity_reason_code,
                    "completion_rate": summary.completion_rate,
                    "skip_rate": summary.skip_rate,
                    "expiry_rate": summary.expiry_rate,
                    "total_actionable_count": summary.total_actionable_count,
                },
                status="pending",
            )
        )
        if summary.integrity_state == "degraded" and previous_state != "degraded":
            session.add(
                OutboxEvent(
                    event_type="protocol_degraded",
                    aggregate_type="protocol",
                    aggregate_id=protocol_id,
                    payload_json={
                        "protocol_id": str(summary.protocol_id),
                        "reason_code": summary.integrity_reason_code,
                    },
                    status="pending",
                )
            )
        if summary.integrity_state == "broken" and previous_state != "broken":
            session.add(
                OutboxEvent(
                    event_type="protocol_broken",
                    aggregate_type="protocol",
                    aggregate_id=protocol_id,
                    payload_json={
                        "protocol_id": str(summary.protocol_id),
                        "reason_code": summary.broken_reason_code,
                    },
                    status="pending",
                )
            )
        if (
            summary.integrity_state == "healthy"
            and previous_state in {"watch", "degraded", "broken"}
        ):
            session.add(
                OutboxEvent(
                    event_type="protocol_integrity_recovered",
                    aggregate_type="protocol",
                    aggregate_id=protocol_id,
                    payload_json={"protocol_id": str(summary.protocol_id)},
                    status="pending",
                )
            )
