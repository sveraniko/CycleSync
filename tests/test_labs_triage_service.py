import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.application.labs.schemas import (
    LabMarkerView,
    LabReportDetailsView,
    LabReportEntryView,
    LabReportView,
    LabTriageFlagView,
    LabTriageResultView,
    LabTriageRunView,
    ProtocolTriageContextView,
)
from app.application.labs.triage_service import (
    LabsTriageAccessError,
    LabsTriageParsingError,
    LabsTriageService,
    parse_triage_output,
)


@dataclass
class _FakeGateway:
    payloads: list
    raw: dict

    async def run_triage(self, payload):
        self.payloads.append(payload)
        return self.raw


class _FakeRepo:
    def __init__(self) -> None:
        self.events = []
        self.runs = []
        self.flags = []
        self.marker = LabMarkerView(
            marker_id=uuid4(),
            marker_code="hematocrit",
            display_name="Hematocrit",
            category_code="hematology",
            default_unit="%",
            accepted_units=["%"],
            notes=None,
        )
        self.report = LabReportView(
            report_id=uuid4(),
            user_id="u1",
            protocol_id=uuid4(),
            report_date=date(2026, 4, 12),
            source_lab_name="LabX",
            notes=None,
            finalized_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        self.entries = [
            LabReportEntryView(
                entry_id=uuid4(),
                lab_report_id=self.report.report_id,
                marker_id=self.marker.marker_id,
                marker_code=self.marker.marker_code,
                marker_display_name=self.marker.display_name,
                entered_value="55.0",
                numeric_value=Decimal("55.0"),
                unit="%",
                reference_min=Decimal("40.0"),
                reference_max=Decimal("50.0"),
                entered_at=datetime.now(timezone.utc),
            )
        ]
        self.protocol_context = ProtocolTriageContextView(
            protocol_id=self.report.protocol_id,
            status="active",
            activated_at=datetime.now(timezone.utc),
            selected_products=["Test E"],
            pulse_plan_context={"weekly_target_total_mg": 300},
            adherence_integrity_state="watch",
            adherence_integrity_detail={"missed": 1},
        )

    async def list_markers(self):
        return [self.marker]

    async def get_lab_report_details(self, report_id, user_id):
        return LabReportDetailsView(report=self.report, entries=self.entries)

    async def get_active_protocol_context(self, **kwargs):
        return self.protocol_context

    async def get_latest_triage_result(self, **kwargs):
        if not self.runs:
            return None
        return LabTriageResultView(run=self.runs[-1], flags=self.flags)

    async def create_lab_triage_run(self, **kwargs):
        run = LabTriageRunView(
            triage_run_id=uuid4(),
            lab_report_id=kwargs["lab_report_id"],
            user_id=kwargs["user_id"],
            protocol_id=kwargs["protocol_id"],
            triage_status=kwargs["triage_status"],
            summary_text=kwargs["summary_text"],
            urgent_flag=kwargs["urgent_flag"],
            model_name=kwargs["model_name"],
            prompt_version=kwargs["prompt_version"],
            raw_result_json=kwargs["raw_result_json"],
            created_at=datetime.now(timezone.utc),
            completed_at=kwargs["completed_at"],
        )
        self.runs.append(run)
        return run

    async def create_lab_triage_flags(self, **kwargs):
        out = []
        for item in kwargs["flags"]:
            out.append(
                LabTriageFlagView(
                    flag_id=uuid4(),
                    triage_run_id=kwargs["triage_run_id"],
                    marker_id=item.marker_id,
                    severity=item.severity,
                    flag_code=item.flag_code,
                    title=item.title,
                    explanation=item.explanation,
                    suggested_followup=item.suggested_followup,
                    created_at=datetime.now(timezone.utc),
                )
            )
        self.flags = out
        return out

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


def test_parse_triage_output_contract() -> None:
    marker_id = uuid4()
    parsed = parse_triage_output(
        raw={
            "summary": "Test summary",
            "urgent_flag": True,
            "flags": [
                {
                    "marker_code": "hematocrit",
                    "severity": "urgent",
                    "flag_code": "marker.above_reference",
                    "title": "HCT high",
                    "explanation": "Above max",
                    "suggested_followup": "Repeat",
                }
            ],
            "recommended_followups": ["Repeat CBC"],
            "model_name": "gpt-x",
            "prompt_version": "v1",
        },
        marker_code_map={"hematocrit": marker_id},
    )
    assert parsed.urgent_flag is True
    assert parsed.flags[0].marker_id == marker_id


def test_invalid_triage_output_fails_safe() -> None:
    try:
        parse_triage_output(raw={"summary": "", "urgent_flag": "yes", "flags": []}, marker_code_map={})
        assert False, "expected parse failure"
    except LabsTriageParsingError:
        pass


def test_triage_persistence_protocol_context_and_regenerate() -> None:
    repo = _FakeRepo()
    gateway = _FakeGateway(
        payloads=[],
        raw={
            "summary": "Detected issue",
            "urgent_flag": False,
            "flags": [
                {
                    "marker_code": "hematocrit",
                    "severity": "warning",
                    "flag_code": "marker.above_reference",
                    "title": "HCT high",
                    "explanation": "Above max",
                    "suggested_followup": None,
                }
            ],
            "recommended_followups": [],
            "model_name": "gpt-test",
            "prompt_version": "w6",
        },
    )
    service = LabsTriageService(repository=repo, gateway=gateway, access_evaluator=_AllowAccess())

    first = asyncio.run(service.run_triage(user_id="u1", report_id=repo.report.report_id))
    second = asyncio.run(
        service.run_triage(user_id="u1", report_id=repo.report.report_id, regenerate=True)
    )

    assert first.run.triage_status == "completed"
    assert second.run.triage_status == "completed"
    assert repo.flags
    assert "lab_triage_completed" in repo.events
    assert "lab_triage_regenerated" in repo.events
    assert gateway.payloads[0].protocol_context is not None


def test_triage_gate_denies_without_entitlement() -> None:
    repo = _FakeRepo()
    gateway = _FakeGateway(payloads=[], raw={})
    service = LabsTriageService(repository=repo, gateway=gateway, access_evaluator=_DenyAccess())

    try:
        asyncio.run(service.run_triage(user_id="u1", report_id=repo.report.report_id))
        assert False, "expected access denial"
    except LabsTriageAccessError as exc:
        assert str(exc) == "AI triage requires access."
    assert "feature_access_denied" in repo.events
