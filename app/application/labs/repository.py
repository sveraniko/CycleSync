from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.application.labs.schemas import (
    LabMarkerView,
    LabPanelView,
    LabReportDetailsView,
    LabReportEntryView,
    LabReportView,
)


class LabsRepository:
    async def list_markers(self) -> list[LabMarkerView]:
        raise NotImplementedError

    async def get_marker(self, marker_id: UUID) -> LabMarkerView | None:
        raise NotImplementedError

    async def list_panels(self) -> list[LabPanelView]:
        raise NotImplementedError

    async def list_panel_markers(self, panel_id: UUID) -> list[LabMarkerView]:
        raise NotImplementedError

    async def create_lab_report(
        self,
        *,
        user_id: str,
        protocol_id: UUID | None,
        report_date: date,
        source_lab_name: str | None,
        notes: str | None,
    ) -> LabReportView:
        raise NotImplementedError

    async def add_or_update_lab_report_entry(
        self,
        *,
        lab_report_id: UUID,
        marker_id: UUID,
        entered_value: str,
        numeric_value: Decimal | None,
        unit: str,
        reference_min: Decimal | None,
        reference_max: Decimal | None,
        entered_at: datetime,
    ) -> tuple[LabReportEntryView, bool]:
        raise NotImplementedError

    async def finalize_lab_report(self, report_id: UUID, finalized_at: datetime) -> None:
        raise NotImplementedError

    async def list_lab_reports(self, user_id: str) -> list[LabReportView]:
        raise NotImplementedError

    async def get_lab_report_details(self, report_id: UUID, user_id: str) -> LabReportDetailsView | None:
        raise NotImplementedError

    async def enqueue_event(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict,
    ) -> None:
        raise NotImplementedError
