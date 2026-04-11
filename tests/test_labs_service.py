import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.application.labs import LabEntryInput, LabsApplicationService, LabsValidationError
from app.application.labs.schemas import (
    LabMarkerView,
    LabReportDetailsView,
    LabReportEntryView,
    LabReportView,
)


@dataclass
class _FakeRepo:
    marker: LabMarkerView

    def __post_init__(self):
        self.events = []
        self.entries = []
        self.report = LabReportView(
            report_id=uuid4(),
            user_id="u1",
            protocol_id=None,
            report_date=date(2026, 4, 11),
            source_lab_name="Lab",
            notes=None,
            finalized_at=None,
            created_at=datetime.now(timezone.utc),
        )

    async def list_markers(self):
        return [self.marker]

    async def get_marker(self, marker_id):
        return self.marker if marker_id == self.marker.marker_id else None

    async def list_panels(self):
        return []

    async def list_panel_markers(self, panel_id):
        return [self.marker]

    async def create_lab_report(self, **kwargs):
        return self.report

    async def add_or_update_lab_report_entry(self, **kwargs):
        entry = LabReportEntryView(
            entry_id=uuid4(),
            lab_report_id=kwargs["lab_report_id"],
            marker_id=kwargs["marker_id"],
            marker_code=self.marker.marker_code,
            marker_display_name=self.marker.display_name,
            entered_value=kwargs["entered_value"],
            numeric_value=kwargs["numeric_value"],
            unit=kwargs["unit"],
            reference_min=kwargs["reference_min"],
            reference_max=kwargs["reference_max"],
            entered_at=kwargs["entered_at"],
        )
        self.entries.append(entry)
        return entry, True

    async def finalize_lab_report(self, report_id, finalized_at):
        pass

    async def list_lab_reports(self, user_id):
        return [self.report]

    async def get_lab_report_details(self, report_id, user_id):
        return LabReportDetailsView(report=self.report, entries=self.entries)

    async def enqueue_event(self, **kwargs):
        self.events.append(kwargs["event_type"])


def _build_service():
    marker = LabMarkerView(
        marker_id=uuid4(),
        marker_code="testosterone_total",
        display_name="Total Testosterone",
        category_code="male_hormones",
        default_unit="ng/dL",
        accepted_units=["ng/dL", "nmol/L"],
        notes=None,
    )
    repo = _FakeRepo(marker)
    return LabsApplicationService(repo), repo, marker


def test_lab_report_creation_and_history() -> None:
    service, repo, _ = _build_service()

    report = asyncio.run(
        service.create_report(
            user_id="u1",
            report_date=date(2026, 4, 11),
            source_lab_name="Invitro",
            notes=None,
        )
    )
    history = asyncio.run(service.list_history("u1"))

    assert report.report_id == repo.report.report_id
    assert history
    assert "lab_report_created" in repo.events


def test_lab_entry_validation_and_units() -> None:
    service, repo, marker = _build_service()

    entry = asyncio.run(
        service.add_entry(
            user_id="u1",
            report_id=repo.report.report_id,
            entry=LabEntryInput(
                marker_id=marker.marker_id,
                value_text="12.3",
                unit="ng/dL",
                reference_min=Decimal("8"),
                reference_max=Decimal("30"),
            ),
        )
    )
    assert entry.numeric_value == Decimal("12.3")
    assert "lab_result_entry_added" in repo.events

    try:
        asyncio.run(
            service.add_entry(
                user_id="u1",
                report_id=repo.report.report_id,
                entry=LabEntryInput(marker_id=marker.marker_id, value_text="abc", unit="ng/dL"),
            )
        )
        assert False, "expected validation error"
    except LabsValidationError:
        pass

    try:
        asyncio.run(
            service.add_entry(
                user_id="u1",
                report_id=repo.report.report_id,
                entry=LabEntryInput(marker_id=marker.marker_id, value_text="10", unit="pg/mL"),
            )
        )
        assert False, "expected unit validation error"
    except LabsValidationError:
        pass


def test_history_retrieval_details() -> None:
    service, repo, _ = _build_service()
    details = asyncio.run(service.get_report("u1", repo.report.report_id))
    assert details is not None
    assert details.report.report_id == repo.report.report_id
