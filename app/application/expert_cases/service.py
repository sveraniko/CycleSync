from datetime import datetime, timezone
from uuid import UUID

from app.application.expert_cases.repository import SpecialistCasesRepository
from app.application.expert_cases.schemas import (
    ALLOWED_CASE_STATUSES,
    SpecialistCaseListItemView,
    SpecialistCaseOpenedResult,
    SpecialistCaseStatus,
)


class SpecialistCaseError(ValueError):
    pass


class SpecialistCaseAccessError(SpecialistCaseError):
    pass


class SpecialistCaseAssemblyService:
    def __init__(self, repository: SpecialistCasesRepository) -> None:
        self.repository = repository

    async def open_case(
        self,
        *,
        user_id: str,
        lab_report_id: UUID,
        triage_run_id: UUID | None = None,
        notes_from_user: str | None = None,
        opened_reason_code: str = "user_consult_specialist",
    ) -> SpecialistCaseOpenedResult:
        access = await self.repository.check_case_access(user_id=user_id)
        if not access.allowed:
            raise SpecialistCaseAccessError(access.reason_code)

        report = await self.repository.get_lab_report_case_view(report_id=lab_report_id, user_id=user_id)
        if report is None:
            raise SpecialistCaseError("lab_report_not_found")

        triage = None
        if triage_run_id is not None:
            triage = await self.repository.get_triage_case_view(triage_run_id=triage_run_id, user_id=user_id)
        if triage is None:
            triage = await self.repository.get_latest_triage_for_report(report_id=lab_report_id, user_id=user_id)

        protocol_id = report.protocol_id or (triage.protocol_id if triage else None)
        protocol_context = None
        pulse_plan_context = None
        adherence_context = None
        if protocol_id is not None:
            protocol_context = await self.repository.get_protocol_case_context(protocol_id=protocol_id, user_id=user_id)
            pulse_plan_context = await self.repository.get_active_pulse_plan_context(protocol_id=protocol_id)
            adherence_context = await self.repository.get_adherence_case_context(protocol_id=protocol_id)

        opened_at = datetime.now(timezone.utc)
        opened_at_iso = opened_at.isoformat()
        trimmed_note = (notes_from_user or "").strip() or None

        await self.repository.enqueue_event(
            event_type="specialist_case_open_requested",
            aggregate_type="lab_report",
            aggregate_id=report.report_id,
            payload={"user_id": user_id, "opened_reason_code": opened_reason_code},
        )

        case = await self.repository.create_case(
            user_id=user_id,
            protocol_id=protocol_id,
            lab_report_id=report.report_id,
            triage_run_id=triage.triage_run_id if triage else None,
            case_status=SpecialistCaseStatus.OPENED,
            opened_reason_code=opened_reason_code,
            opened_at_iso=opened_at_iso,
            notes_from_user=trimmed_note,
        )
        await self.repository.enqueue_event(
            event_type="specialist_case_created",
            aggregate_type="specialist_case",
            aggregate_id=case.case_id,
            payload={"user_id": user_id, "case_status": case.case_status},
        )

        snapshot_version = await self.repository.next_snapshot_version(case_id=case.case_id)
        payload = {
            "user_id": user_id,
            "protocol": {
                "protocol_id": str(protocol_context.protocol_id),
                "status": protocol_context.status,
                "activated_at": protocol_context.activated_at.isoformat() if protocol_context.activated_at else None,
                "summary": protocol_context.summary_snapshot_json,
                "settings": protocol_context.settings_snapshot_json,
            }
            if protocol_context
            else None,
            "pulse_plan": {
                "pulse_plan_id": str(pulse_plan_context.pulse_plan_id),
                "status": pulse_plan_context.status,
                "preset_requested": pulse_plan_context.preset_requested,
                "preset_applied": pulse_plan_context.preset_applied,
                "summary_metrics": pulse_plan_context.summary_metrics_json,
                "warning_flags": pulse_plan_context.warning_flags_json,
            }
            if pulse_plan_context
            else None,
            "adherence": {
                "protocol_id": str(adherence_context.protocol_id),
                "pulse_plan_id": str(adherence_context.pulse_plan_id),
                "integrity_state": adherence_context.integrity_state,
                "integrity_reason_code": adherence_context.integrity_reason_code,
                "broken_reason_code": adherence_context.broken_reason_code,
                "integrity_detail": adherence_context.integrity_detail_json,
                "completion_rate": adherence_context.completion_rate,
                "counts": {
                    "total_actionable": adherence_context.total_actionable_count,
                    "completed": adherence_context.completed_count,
                    "skipped": adherence_context.skipped_count,
                    "snoozed": adherence_context.snoozed_count,
                    "expired": adherence_context.expired_count,
                },
                "last_action_at": adherence_context.last_action_at.isoformat() if adherence_context.last_action_at else None,
            }
            if adherence_context
            else None,
            "lab_report": {
                "report_id": str(report.report_id),
                "report_date": report.report_date.isoformat(),
                "source_lab_name": report.source_lab_name,
                "finalized_at": report.finalized_at.isoformat() if report.finalized_at else None,
                "entries": [
                    {
                        "marker_id": str(entry.marker_id),
                        "marker_code": entry.marker_code,
                        "marker_display_name": entry.marker_display_name,
                        "entered_value": entry.entered_value,
                        "numeric_value": str(entry.numeric_value) if entry.numeric_value is not None else None,
                        "unit": entry.unit,
                        "reference_min": str(entry.reference_min) if entry.reference_min is not None else None,
                        "reference_max": str(entry.reference_max) if entry.reference_max is not None else None,
                        "entered_at": entry.entered_at.isoformat(),
                    }
                    for entry in sorted(report.entries, key=lambda x: (x.marker_code, x.entered_at.isoformat()))
                ],
            },
            "triage": {
                "triage_run_id": str(triage.triage_run_id),
                "triage_status": triage.triage_status,
                "summary_text": triage.summary_text,
                "urgent_flag": triage.urgent_flag,
                "model_name": triage.model_name,
                "prompt_version": triage.prompt_version,
                "completed_at": triage.completed_at.isoformat() if triage.completed_at else None,
                "flags": [
                    {
                        "marker_id": str(flag.marker_id) if flag.marker_id else None,
                        "severity": flag.severity,
                        "flag_code": flag.flag_code,
                        "title": flag.title,
                        "explanation": flag.explanation,
                        "suggested_followup": flag.suggested_followup,
                    }
                    for flag in triage.flags
                ],
            }
            if triage
            else None,
            "user_note": trimmed_note,
            "assembled_at": opened_at_iso,
            "assembly_version": 1,
        }

        snapshot = await self.repository.create_snapshot(
            case_id=case.case_id,
            snapshot_version=snapshot_version,
            payload_json=payload,
        )
        await self.repository.enqueue_event(
            event_type="specialist_case_snapshot_created",
            aggregate_type="specialist_case",
            aggregate_id=case.case_id,
            payload={"snapshot_id": str(snapshot.snapshot_id), "snapshot_version": snapshot.snapshot_version},
        )

        case = await self.repository.update_case_status_and_latest_snapshot(
            case_id=case.case_id,
            case_status=SpecialistCaseStatus.AWAITING_SPECIALIST,
            latest_snapshot_id=snapshot.snapshot_id,
        )
        await self.repository.enqueue_event(
            event_type="specialist_case_status_updated",
            aggregate_type="specialist_case",
            aggregate_id=case.case_id,
            payload={
                "from_status": SpecialistCaseStatus.OPENED,
                "to_status": SpecialistCaseStatus.AWAITING_SPECIALIST,
            },
        )
        return SpecialistCaseOpenedResult(case=case, snapshot=snapshot)

    async def list_user_cases(self, *, user_id: str, limit: int = 20) -> list[SpecialistCaseListItemView]:
        return await self.repository.list_user_cases(user_id=user_id, limit=limit)

    async def get_latest_user_case(self, *, user_id: str) -> SpecialistCaseListItemView | None:
        return await self.repository.get_latest_user_case(user_id=user_id)

    @staticmethod
    def validate_status(status: str) -> str:
        if status not in ALLOWED_CASE_STATUSES:
            raise SpecialistCaseError(f"invalid_case_status:{status}")
        return status
