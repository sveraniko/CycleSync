from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.expert_cases.repository import SpecialistCasesRepository
from app.application.expert_cases.schemas import (
    AdherenceCaseContextView,
    LabReportCaseEntryView,
    LabReportCaseView,
    ProtocolCaseContextView,
    PulsePlanCaseContextView,
    SpecialistCaseAccessDecision,
    SpecialistCaseListItemView,
    SpecialistCaseSnapshotView,
    SpecialistCaseView,
    TriageFlagCaseView,
    TriageRunCaseView,
)
from app.domain.models.ai_triage import LabTriageFlag, LabTriageRun
from app.domain.models.expert_cases import SpecialistCase, SpecialistCaseSnapshot
from app.domain.models.labs import LabMarker, LabReport, LabReportEntry
from app.domain.models.ops import OutboxEvent
from app.domain.models.protocols import Protocol
from app.domain.models.pulse_engine import PulsePlan
from app.domain.models.reminders import ProtocolAdherenceSummary


class SqlAlchemySpecialistCasesRepository(SpecialistCasesRepository):
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def get_lab_report_case_view(self, *, report_id: UUID, user_id: str) -> LabReportCaseView | None:
        async with self.session_factory() as session:
            report = await session.scalar(select(LabReport).where(LabReport.id == report_id, LabReport.user_id == user_id))
            if report is None:
                return None
            rows = await session.execute(
                select(LabReportEntry, LabMarker)
                .join(LabMarker, LabMarker.id == LabReportEntry.marker_id)
                .where(LabReportEntry.lab_report_id == report.id)
                .order_by(LabMarker.marker_code.asc())
            )
            entries = [
                LabReportCaseEntryView(
                    marker_id=entry.marker_id,
                    marker_code=marker.marker_code,
                    marker_display_name=marker.display_name,
                    entered_value=entry.entered_value,
                    numeric_value=entry.numeric_value,
                    unit=entry.unit,
                    reference_min=entry.reference_min,
                    reference_max=entry.reference_max,
                    entered_at=entry.entered_at,
                )
                for entry, marker in rows.all()
            ]
            return LabReportCaseView(
                report_id=report.id,
                user_id=report.user_id,
                protocol_id=report.protocol_id,
                report_date=report.report_date,
                source_lab_name=report.source_lab_name,
                notes=report.notes,
                finalized_at=report.finalized_at,
                created_at=report.created_at,
                entries=entries,
            )

    async def get_latest_triage_for_report(self, *, report_id: UUID, user_id: str) -> TriageRunCaseView | None:
        async with self.session_factory() as session:
            run = await session.scalar(
                select(LabTriageRun)
                .where(LabTriageRun.lab_report_id == report_id, LabTriageRun.user_id == user_id)
                .order_by(LabTriageRun.created_at.desc())
            )
            if run is None:
                return None
            flags = list(
                await session.scalars(
                    select(LabTriageFlag).where(LabTriageFlag.triage_run_id == run.id).order_by(LabTriageFlag.created_at.asc())
                )
            )
            return self._to_triage_view(run, flags)

    async def get_triage_case_view(self, *, triage_run_id: UUID, user_id: str) -> TriageRunCaseView | None:
        async with self.session_factory() as session:
            run = await session.scalar(
                select(LabTriageRun).where(LabTriageRun.id == triage_run_id, LabTriageRun.user_id == user_id)
            )
            if run is None:
                return None
            flags = list(
                await session.scalars(
                    select(LabTriageFlag).where(LabTriageFlag.triage_run_id == run.id).order_by(LabTriageFlag.created_at.asc())
                )
            )
            return self._to_triage_view(run, flags)

    async def get_protocol_case_context(self, *, protocol_id: UUID, user_id: str) -> ProtocolCaseContextView | None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(Protocol).where(Protocol.id == protocol_id, Protocol.user_id == user_id, Protocol.status == "active")
            )
            if row is None:
                return None
            return ProtocolCaseContextView(
                protocol_id=row.id,
                status=row.status,
                activated_at=row.activated_at,
                summary_snapshot_json=row.summary_snapshot_json,
                settings_snapshot_json=row.settings_snapshot_json,
            )

    async def get_active_pulse_plan_context(self, *, protocol_id: UUID) -> PulsePlanCaseContextView | None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(PulsePlan)
                .where(PulsePlan.protocol_id == protocol_id)
                .order_by(PulsePlan.created_at.desc())
            )
            if row is None:
                return None
            return PulsePlanCaseContextView(
                pulse_plan_id=row.id,
                status=row.status,
                preset_requested=row.preset_requested,
                preset_applied=row.preset_applied,
                summary_metrics_json=row.summary_metrics_json,
                warning_flags_json=list(row.warning_flags_json or []),
            )

    async def get_adherence_case_context(self, *, protocol_id: UUID) -> AdherenceCaseContextView | None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(ProtocolAdherenceSummary)
                .where(ProtocolAdherenceSummary.protocol_id == protocol_id)
                .order_by(ProtocolAdherenceSummary.updated_at.desc())
            )
            if row is None:
                return None
            return AdherenceCaseContextView(
                protocol_id=row.protocol_id,
                pulse_plan_id=row.pulse_plan_id,
                integrity_state=row.integrity_state,
                integrity_reason_code=row.integrity_reason_code,
                broken_reason_code=row.broken_reason_code,
                integrity_detail_json=row.integrity_detail_json,
                completion_rate=row.completion_rate,
                total_actionable_count=row.total_actionable_count,
                completed_count=row.completed_count,
                skipped_count=row.skipped_count,
                snoozed_count=row.snoozed_count,
                expired_count=row.expired_count,
                last_action_at=row.last_action_at,
            )

    async def check_case_access(self, *, user_id: str) -> SpecialistCaseAccessDecision:
        _ = user_id
        # TODO(W7/PR2): replace baseline allow-all with entitlement check for `expert_case_access`.
        return SpecialistCaseAccessDecision(allowed=True, reason_code="allow_baseline")

    async def create_case(self, *, user_id: str, protocol_id: UUID | None, lab_report_id: UUID | None, triage_run_id: UUID | None, case_status: str, opened_reason_code: str, opened_at_iso: str, notes_from_user: str | None) -> SpecialistCaseView:
        async with self.session_factory() as session:
            row = SpecialistCase(
                user_id=user_id,
                protocol_id=protocol_id,
                lab_report_id=lab_report_id,
                triage_run_id=triage_run_id,
                case_status=case_status,
                opened_reason_code=opened_reason_code,
                opened_at=datetime.fromisoformat(opened_at_iso),
                notes_from_user=notes_from_user,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_case_view(row)

    async def next_snapshot_version(self, *, case_id: UUID) -> int:
        async with self.session_factory() as session:
            current = await session.scalar(
                select(func.max(SpecialistCaseSnapshot.snapshot_version)).where(SpecialistCaseSnapshot.case_id == case_id)
            )
            return int(current or 0) + 1

    async def create_snapshot(self, *, case_id: UUID, snapshot_version: int, payload_json: dict) -> SpecialistCaseSnapshotView:
        async with self.session_factory() as session:
            row = SpecialistCaseSnapshot(
                case_id=case_id,
                snapshot_version=snapshot_version,
                payload_json=payload_json,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_snapshot_view(row)

    async def update_case_status_and_latest_snapshot(self, *, case_id: UUID, case_status: str, latest_snapshot_id: UUID) -> SpecialistCaseView:
        async with self.session_factory() as session:
            row = await session.scalar(select(SpecialistCase).where(SpecialistCase.id == case_id))
            if row is None:
                raise ValueError("specialist_case_not_found")
            row.case_status = case_status
            row.latest_snapshot_id = latest_snapshot_id
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_case_view(row)

    async def list_user_cases(self, *, user_id: str, limit: int = 20) -> list[SpecialistCaseListItemView]:
        async with self.session_factory() as session:
            rows = await session.execute(
                select(SpecialistCase, LabReport.report_date)
                .join(LabReport, LabReport.id == SpecialistCase.lab_report_id, isouter=True)
                .where(SpecialistCase.user_id == user_id)
                .order_by(SpecialistCase.opened_at.desc())
                .limit(limit)
            )
            return [
                SpecialistCaseListItemView(
                    case_id=case.id,
                    case_status=case.case_status,
                    opened_at=case.opened_at,
                    lab_report_id=case.lab_report_id,
                    lab_report_date=report_date,
                    triage_run_id=case.triage_run_id,
                    latest_snapshot_id=case.latest_snapshot_id,
                )
                for case, report_date in rows.all()
            ]

    async def get_latest_user_case(self, *, user_id: str) -> SpecialistCaseListItemView | None:
        items = await self.list_user_cases(user_id=user_id, limit=1)
        return items[0] if items else None

    async def enqueue_event(self, *, event_type: str, aggregate_type: str, aggregate_id: UUID, payload: dict) -> None:
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

    @staticmethod
    def _to_triage_view(run: LabTriageRun, flags: list[LabTriageFlag]) -> TriageRunCaseView:
        return TriageRunCaseView(
            triage_run_id=run.id,
            lab_report_id=run.lab_report_id,
            user_id=run.user_id,
            protocol_id=run.protocol_id,
            triage_status=run.triage_status,
            summary_text=run.summary_text,
            urgent_flag=run.urgent_flag,
            model_name=run.model_name,
            prompt_version=run.prompt_version,
            completed_at=run.completed_at,
            created_at=run.created_at,
            flags=[
                TriageFlagCaseView(
                    marker_id=flag.marker_id,
                    severity=flag.severity,
                    flag_code=flag.flag_code,
                    title=flag.title,
                    explanation=flag.explanation,
                    suggested_followup=flag.suggested_followup,
                )
                for flag in flags
            ],
        )

    @staticmethod
    def _to_case_view(row: SpecialistCase) -> SpecialistCaseView:
        return SpecialistCaseView(
            case_id=row.id,
            user_id=row.user_id,
            protocol_id=row.protocol_id,
            lab_report_id=row.lab_report_id,
            triage_run_id=row.triage_run_id,
            case_status=row.case_status,
            opened_reason_code=row.opened_reason_code,
            opened_at=row.opened_at,
            closed_at=row.closed_at,
            latest_snapshot_id=row.latest_snapshot_id,
            notes_from_user=row.notes_from_user,
        )

    @staticmethod
    def _to_snapshot_view(row: SpecialistCaseSnapshot) -> SpecialistCaseSnapshotView:
        return SpecialistCaseSnapshotView(
            snapshot_id=row.id,
            case_id=row.case_id,
            snapshot_version=row.snapshot_version,
            payload_json=row.payload_json,
            created_at=row.created_at,
        )
