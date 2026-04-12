from uuid import UUID

from app.application.expert_cases.schemas import (
    AdherenceCaseContextView,
    LabReportCaseView,
    ProtocolCaseContextView,
    PulsePlanCaseContextView,
    SpecialistCaseAccessDecision,
    SpecialistCaseListItemView,
    SpecialistCaseSnapshotView,
    SpecialistCaseView,
    TriageRunCaseView,
)


class SpecialistCasesRepository:
    async def get_lab_report_case_view(self, *, report_id: UUID, user_id: str) -> LabReportCaseView | None:
        raise NotImplementedError

    async def get_latest_triage_for_report(self, *, report_id: UUID, user_id: str) -> TriageRunCaseView | None:
        raise NotImplementedError

    async def get_triage_case_view(self, *, triage_run_id: UUID, user_id: str) -> TriageRunCaseView | None:
        raise NotImplementedError

    async def get_protocol_case_context(self, *, protocol_id: UUID, user_id: str) -> ProtocolCaseContextView | None:
        raise NotImplementedError

    async def get_active_pulse_plan_context(self, *, protocol_id: UUID) -> PulsePlanCaseContextView | None:
        raise NotImplementedError

    async def get_adherence_case_context(self, *, protocol_id: UUID) -> AdherenceCaseContextView | None:
        raise NotImplementedError

    async def check_case_access(self, *, user_id: str) -> SpecialistCaseAccessDecision:
        raise NotImplementedError

    async def create_case(
        self,
        *,
        user_id: str,
        protocol_id: UUID | None,
        lab_report_id: UUID | None,
        triage_run_id: UUID | None,
        case_status: str,
        opened_reason_code: str,
        opened_at_iso: str,
        notes_from_user: str | None,
    ) -> SpecialistCaseView:
        raise NotImplementedError

    async def next_snapshot_version(self, *, case_id: UUID) -> int:
        raise NotImplementedError

    async def create_snapshot(
        self,
        *,
        case_id: UUID,
        snapshot_version: int,
        payload_json: dict,
    ) -> SpecialistCaseSnapshotView:
        raise NotImplementedError

    async def update_case_status_and_latest_snapshot(
        self,
        *,
        case_id: UUID,
        case_status: str,
        latest_snapshot_id: UUID,
    ) -> SpecialistCaseView:
        raise NotImplementedError

    async def list_user_cases(self, *, user_id: str, limit: int = 20) -> list[SpecialistCaseListItemView]:
        raise NotImplementedError

    async def get_latest_user_case(self, *, user_id: str) -> SpecialistCaseListItemView | None:
        raise NotImplementedError

    async def enqueue_event(self, *, event_type: str, aggregate_type: str, aggregate_id: UUID, payload: dict) -> None:
        raise NotImplementedError
