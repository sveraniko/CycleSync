import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.expert_cases import (
    AdherenceCaseContextView,
    LabReportCaseEntryView,
    LabReportCaseView,
    ProtocolCaseContextView,
    PulsePlanCaseContextView,
    SpecialistCaseAssemblyService,
    SpecialistCaseAccessError,
    SpecialistCaseDetailView,
    SpecialistCaseListItemView,
    SpecialistCaseResponseView,
    SpecialistCaseSnapshotView,
    SpecialistCaseStatus,
    SpecialistCaseView,
    TriageFlagCaseView,
    TriageRunCaseView,
)


@dataclass
class _FakeRepo:
    allow_access: bool = True

    def __post_init__(self) -> None:
        self.events: list[str] = []
        self.case_id = uuid4()
        self.report_id = uuid4()
        self.protocol_id = uuid4()
        self.triage_id = uuid4()
        self.snapshot_id = uuid4()
        self.created_case: SpecialistCaseView | None = None
        self.created_snapshot: SpecialistCaseSnapshotView | None = None
        self.latest_response: SpecialistCaseResponseView | None = None

    async def check_case_access(self, *, user_id: str):
        _ = user_id
        from app.application.expert_cases import SpecialistCaseAccessDecision

        return SpecialistCaseAccessDecision(allowed=self.allow_access, reason_code="ok" if self.allow_access else "denied")

    async def get_lab_report_case_view(self, *, report_id, user_id):
        _ = user_id
        if report_id != self.report_id:
            return None
        return LabReportCaseView(
            report_id=self.report_id,
            user_id="u1",
            protocol_id=self.protocol_id,
            report_date=date(2026, 4, 12),
            source_lab_name="LabX",
            notes=None,
            finalized_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            entries=[
                LabReportCaseEntryView(
                    marker_id=uuid4(),
                    marker_code="hematocrit",
                    marker_display_name="Hematocrit",
                    entered_value="55.0",
                    numeric_value=Decimal("55.0"),
                    unit="%",
                    reference_min=Decimal("40.0"),
                    reference_max=Decimal("50.0"),
                    entered_at=datetime.now(timezone.utc),
                )
            ],
        )

    async def get_latest_triage_for_report(self, *, report_id, user_id):
        _ = report_id, user_id
        return TriageRunCaseView(
            triage_run_id=self.triage_id,
            lab_report_id=self.report_id,
            user_id="u1",
            protocol_id=self.protocol_id,
            triage_status="completed",
            summary_text="summary",
            urgent_flag=False,
            model_name="gpt-test",
            prompt_version="w6",
            completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            flags=[
                TriageFlagCaseView(
                    marker_id=None,
                    severity="watch",
                    flag_code="data.reference_range_missing",
                    title="Reference missing",
                    explanation="missing",
                    suggested_followup=None,
                )
            ],
        )

    async def get_triage_case_view(self, *, triage_run_id, user_id):
        _ = triage_run_id, user_id
        return None

    async def get_protocol_case_context(self, *, protocol_id, user_id):
        _ = user_id
        return ProtocolCaseContextView(
            protocol_id=protocol_id,
            status="active",
            activated_at=datetime.now(timezone.utc),
            summary_snapshot_json={"products": ["Test E"]},
            settings_snapshot_json={"weekly_target_total_mg": 300},
        )

    async def get_active_pulse_plan_context(self, *, protocol_id):
        return PulsePlanCaseContextView(
            pulse_plan_id=uuid4(),
            status="active",
            preset_requested="golden",
            preset_applied="golden",
            summary_metrics_json={"weekly_target_total_mg": 300},
            warning_flags_json=[],
        )

    async def get_adherence_case_context(self, *, protocol_id):
        return AdherenceCaseContextView(
            protocol_id=protocol_id,
            pulse_plan_id=uuid4(),
            integrity_state="watch",
            integrity_reason_code="missed_recently",
            broken_reason_code=None,
            integrity_detail_json={"missed": 1},
            completion_rate=0.8,
            total_actionable_count=10,
            completed_count=8,
            skipped_count=1,
            snoozed_count=1,
            expired_count=0,
            last_action_at=datetime.now(timezone.utc),
        )

    async def create_case(self, **kwargs):
        self.created_case = SpecialistCaseView(
            case_id=self.case_id,
            user_id=kwargs["user_id"],
            protocol_id=kwargs["protocol_id"],
            lab_report_id=kwargs["lab_report_id"],
            triage_run_id=kwargs["triage_run_id"],
            case_status=kwargs["case_status"],
            opened_reason_code=kwargs["opened_reason_code"],
            opened_at=datetime.fromisoformat(kwargs["opened_at_iso"]),
            closed_at=None,
            answered_at=None,
            latest_snapshot_id=None,
            latest_response_id=None,
            assigned_specialist_id=None,
            notes_from_user=kwargs["notes_from_user"],
        )
        return self.created_case

    async def next_snapshot_version(self, *, case_id):
        assert case_id == self.case_id
        return 1

    async def create_snapshot(self, **kwargs):
        self.created_snapshot = SpecialistCaseSnapshotView(
            snapshot_id=self.snapshot_id,
            case_id=kwargs["case_id"],
            snapshot_version=kwargs["snapshot_version"],
            payload_json=kwargs["payload_json"],
            created_at=datetime.now(timezone.utc),
        )
        return self.created_snapshot

    async def update_case_status_and_latest_snapshot(self, **kwargs):
        assert self.created_case is not None
        self.created_case = SpecialistCaseView(
            case_id=self.created_case.case_id,
            user_id=self.created_case.user_id,
            protocol_id=self.created_case.protocol_id,
            lab_report_id=self.created_case.lab_report_id,
            triage_run_id=self.created_case.triage_run_id,
            case_status=kwargs["case_status"],
            opened_reason_code=self.created_case.opened_reason_code,
            opened_at=self.created_case.opened_at,
            closed_at=self.created_case.closed_at,
            answered_at=self.created_case.answered_at,
            latest_snapshot_id=kwargs["latest_snapshot_id"],
            latest_response_id=self.created_case.latest_response_id,
            assigned_specialist_id=self.created_case.assigned_specialist_id,
            notes_from_user=self.created_case.notes_from_user,
        )
        return self.created_case

    async def list_user_cases(self, *, user_id: str, limit: int = 20):
        _ = user_id, limit
        return [
            SpecialistCaseListItemView(
                case_id=self.case_id,
                case_status=SpecialistCaseStatus.AWAITING_SPECIALIST,
                opened_at=datetime.now(timezone.utc),
                lab_report_id=self.report_id,
                lab_report_date=date(2026, 4, 12),
                triage_run_id=self.triage_id,
                latest_snapshot_id=self.snapshot_id,
                latest_response_summary=self.latest_response.response_summary if self.latest_response else None,
                latest_response_created_at=self.latest_response.created_at if self.latest_response else None,
            )
        ]

    async def get_latest_user_case(self, *, user_id: str):
        return (await self.list_user_cases(user_id=user_id))[0]

    async def get_user_case_detail(self, *, user_id: str, case_id):
        detail = await self.get_case_detail(case_id=case_id)
        if detail is None or detail.case.user_id != user_id:
            return None
        return detail

    async def list_awaiting_cases(self, *, limit: int = 20):
        _ = limit
        if self.created_case and self.created_case.case_status == SpecialistCaseStatus.AWAITING_SPECIALIST:
            return await self.list_user_cases(user_id=self.created_case.user_id)
        return []

    async def get_case_detail(self, *, case_id):
        if self.created_case is None or self.created_case.case_id != case_id:
            return None
        return SpecialistCaseDetailView(case=self.created_case, latest_response=self.latest_response)

    async def assign_case_to_specialist(self, *, case_id, specialist_id: str, case_status: str):
        assert self.created_case is not None
        assert self.created_case.case_id == case_id
        self.created_case = SpecialistCaseView(
            case_id=self.created_case.case_id,
            user_id=self.created_case.user_id,
            protocol_id=self.created_case.protocol_id,
            lab_report_id=self.created_case.lab_report_id,
            triage_run_id=self.created_case.triage_run_id,
            case_status=case_status,
            opened_reason_code=self.created_case.opened_reason_code,
            opened_at=self.created_case.opened_at,
            closed_at=self.created_case.closed_at,
            answered_at=self.created_case.answered_at,
            latest_snapshot_id=self.created_case.latest_snapshot_id,
            latest_response_id=self.created_case.latest_response_id,
            assigned_specialist_id=specialist_id,
            notes_from_user=self.created_case.notes_from_user,
        )
        return self.created_case

    async def create_case_response(self, **kwargs):
        self.latest_response = SpecialistCaseResponseView(
            response_id=uuid4(),
            case_id=kwargs["case_id"],
            responded_by=kwargs["responded_by"],
            response_text=kwargs["response_text"],
            response_summary=kwargs["response_summary"],
            is_final=kwargs["is_final"],
            created_at=datetime.now(timezone.utc),
        )
        return self.latest_response

    async def set_case_answered(self, *, case_id, latest_response_id, answered_at_iso):
        assert self.created_case is not None
        assert self.created_case.case_id == case_id
        self.created_case = SpecialistCaseView(
            case_id=self.created_case.case_id,
            user_id=self.created_case.user_id,
            protocol_id=self.created_case.protocol_id,
            lab_report_id=self.created_case.lab_report_id,
            triage_run_id=self.created_case.triage_run_id,
            case_status=SpecialistCaseStatus.ANSWERED,
            opened_reason_code=self.created_case.opened_reason_code,
            opened_at=self.created_case.opened_at,
            closed_at=self.created_case.closed_at,
            answered_at=datetime.fromisoformat(answered_at_iso),
            latest_snapshot_id=self.created_case.latest_snapshot_id,
            latest_response_id=latest_response_id,
            assigned_specialist_id=self.created_case.assigned_specialist_id,
            notes_from_user=self.created_case.notes_from_user,
        )
        return self.created_case

    async def set_case_closed(self, *, case_id, closed_at_iso):
        assert self.created_case is not None
        assert self.created_case.case_id == case_id
        self.created_case = SpecialistCaseView(
            case_id=self.created_case.case_id,
            user_id=self.created_case.user_id,
            protocol_id=self.created_case.protocol_id,
            lab_report_id=self.created_case.lab_report_id,
            triage_run_id=self.created_case.triage_run_id,
            case_status=SpecialistCaseStatus.CLOSED,
            opened_reason_code=self.created_case.opened_reason_code,
            opened_at=self.created_case.opened_at,
            closed_at=datetime.fromisoformat(closed_at_iso),
            answered_at=self.created_case.answered_at,
            latest_snapshot_id=self.created_case.latest_snapshot_id,
            latest_response_id=self.created_case.latest_response_id,
            assigned_specialist_id=self.created_case.assigned_specialist_id,
            notes_from_user=self.created_case.notes_from_user,
        )
        return self.created_case

    async def enqueue_event(self, **kwargs):
        self.events.append(kwargs["event_type"])


class _AllowAccess:
    async def evaluate(self, **kwargs):
        from app.application.access.schemas import EntitlementDecision

        return EntitlementDecision(
            allowed=True,
            reason_code="entitlement_active",
            entitlement_code=kwargs["entitlement_code"],
            grant_source="test",
            expires_at=None,
            grant_id=None,
        )


class _DenyAccess:
    async def evaluate(self, **kwargs):
        from app.application.access.schemas import EntitlementDecision

        return EntitlementDecision(
            allowed=False,
            reason_code="entitlement_absent",
            entitlement_code=kwargs["entitlement_code"],
            grant_source=None,
            expires_at=None,
            grant_id=None,
        )


def test_case_assembly_snapshot_contains_protocol_labs_triage_and_adherence() -> None:
    repo = _FakeRepo()
    service = SpecialistCaseAssemblyService(repository=repo, access_evaluator=_AllowAccess())

    opened = asyncio.run(
        service.open_case(
            user_id="u1",
            lab_report_id=repo.report_id,
            notes_from_user="Please review trend",
        )
    )

    payload = opened.snapshot.payload_json
    assert payload["protocol"]["protocol_id"] == str(repo.protocol_id)
    assert payload["pulse_plan"]["status"] == "active"
    assert payload["adherence"]["integrity_state"] == "watch"
    assert payload["lab_report"]["report_id"] == str(repo.report_id)
    assert payload["triage"]["triage_run_id"] == str(repo.triage_id)
    assert payload["user_note"] == "Please review trend"


def test_case_status_initialization_and_latest_snapshot_reference() -> None:
    repo = _FakeRepo()
    service = SpecialistCaseAssemblyService(repository=repo, access_evaluator=_AllowAccess())

    opened = asyncio.run(service.open_case(user_id="u1", lab_report_id=repo.report_id, notes_from_user=None))

    assert opened.case.case_status == SpecialistCaseStatus.AWAITING_SPECIALIST
    assert opened.case.latest_snapshot_id == opened.snapshot.snapshot_id
    assert opened.snapshot.snapshot_version == 1


def test_case_opening_flow_emits_expected_events() -> None:
    repo = _FakeRepo()
    service = SpecialistCaseAssemblyService(repository=repo, access_evaluator=_AllowAccess())

    asyncio.run(service.open_case(user_id="u1", lab_report_id=repo.report_id, notes_from_user="q"))

    assert "specialist_case_open_requested" in repo.events
    assert "specialist_case_created" in repo.events
    assert "specialist_case_snapshot_created" in repo.events
    assert "specialist_case_status_updated" in repo.events


def test_case_taken_into_review_transition() -> None:
    repo = _FakeRepo()
    service = SpecialistCaseAssemblyService(repository=repo, access_evaluator=_AllowAccess())
    opened = asyncio.run(service.open_case(user_id="u1", lab_report_id=repo.report_id, notes_from_user=None))

    detail = asyncio.run(service.take_case_in_review(case_id=opened.case.case_id, specialist_id="spec-1"))

    assert detail.case.case_status == SpecialistCaseStatus.IN_REVIEW
    assert detail.case.assigned_specialist_id == "spec-1"
    assert "specialist_case_taken_in_review" in repo.events


def test_specialist_response_persisted_and_case_answered() -> None:
    repo = _FakeRepo()
    service = SpecialistCaseAssemblyService(repository=repo, access_evaluator=_AllowAccess())
    opened = asyncio.run(service.open_case(user_id="u1", lab_report_id=repo.report_id, notes_from_user=None))
    asyncio.run(service.take_case_in_review(case_id=opened.case.case_id, specialist_id="spec-1"))

    response = asyncio.run(
        service.submit_specialist_response(
            case_id=opened.case.case_id,
            specialist_id="spec-1",
            response_text="Hydrate and repeat CBC in 2 weeks.",
            response_summary="Repeat CBC",
        )
    )

    assert response.response_text.startswith("Hydrate")
    assert repo.created_case is not None
    assert repo.created_case.case_status == SpecialistCaseStatus.ANSWERED
    assert repo.created_case.latest_response_id == response.response_id
    assert "specialist_case_response_created" in repo.events
    assert "specialist_case_answered" in repo.events


def test_user_can_read_answered_case_and_latest_response() -> None:
    repo = _FakeRepo()
    service = SpecialistCaseAssemblyService(repository=repo, access_evaluator=_AllowAccess())
    opened = asyncio.run(service.open_case(user_id="u1", lab_report_id=repo.report_id, notes_from_user=None))
    asyncio.run(service.take_case_in_review(case_id=opened.case.case_id, specialist_id="spec-1"))
    asyncio.run(
        service.submit_specialist_response(
            case_id=opened.case.case_id,
            specialist_id="spec-1",
            response_text="Final recommendation",
            response_summary="Recommendation",
        )
    )

    detail = asyncio.run(service.get_user_case_detail(user_id="u1", case_id=opened.case.case_id))
    latest = asyncio.run(service.get_latest_user_case(user_id="u1"))

    assert detail is not None
    assert detail.case.case_status == SpecialistCaseStatus.ANSWERED
    assert detail.latest_response is not None
    assert detail.latest_response.response_text == "Final recommendation"
    assert latest is not None
    assert latest.latest_response_summary == "Recommendation"


def test_access_gate_denies_without_entitlement() -> None:
    repo = _FakeRepo(allow_access=False)
    service = SpecialistCaseAssemblyService(repository=repo, access_evaluator=_DenyAccess())

    with pytest.raises(SpecialistCaseAccessError):
        asyncio.run(service.open_case(user_id="u1", lab_report_id=repo.report_id, notes_from_user=None))
    assert "feature_access_denied" in repo.events
