from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.application.labs.repository import LabsRepository
from app.application.labs.schemas import (
    LabEntryInput,
    LabMarkerView,
    LabPanelView,
    LabReportDetailsView,
    LabReportEntryView,
    LabReportView,
)


class LabsValidationError(ValueError):
    pass


class LabsApplicationService:
    def __init__(self, repository: LabsRepository) -> None:
        self.repository = repository

    async def list_markers(self) -> list[LabMarkerView]:
        return await self.repository.list_markers()

    async def list_panels(self) -> list[LabPanelView]:
        return await self.repository.list_panels()

    async def list_panel_markers(self, panel_id: UUID) -> list[LabMarkerView]:
        return await self.repository.list_panel_markers(panel_id)

    async def create_report(
        self,
        *,
        user_id: str,
        report_date: date,
        source_lab_name: str | None,
        notes: str | None,
        protocol_id: UUID | None = None,
    ) -> LabReportView:
        report = await self.repository.create_lab_report(
            user_id=user_id,
            protocol_id=protocol_id,
            report_date=report_date,
            source_lab_name=source_lab_name,
            notes=notes,
        )
        await self.repository.enqueue_event(
            event_type="lab_report_created",
            aggregate_type="lab_report",
            aggregate_id=report.report_id,
            payload={"user_id": user_id, "report_date": report_date.isoformat()},
        )
        return report

    async def add_entry(self, *, user_id: str, report_id: UUID, entry: LabEntryInput) -> LabReportEntryView:
        marker = await self.repository.get_marker(entry.marker_id)
        if marker is None:
            raise LabsValidationError("Unknown marker.")
        if entry.unit not in marker.accepted_units:
            raise LabsValidationError(f"Unsupported unit for {marker.display_name}: {entry.unit}.")

        numeric_value = _parse_decimal(entry.value_text)
        if numeric_value is None:
            raise LabsValidationError("Value must be numeric.")

        if (
            entry.reference_min is not None
            and entry.reference_max is not None
            and entry.reference_min > entry.reference_max
        ):
            raise LabsValidationError("Reference min cannot be greater than max.")

        persisted, created = await self.repository.add_or_update_lab_report_entry(
            lab_report_id=report_id,
            marker_id=entry.marker_id,
            entered_value=entry.value_text.strip(),
            numeric_value=numeric_value,
            unit=entry.unit,
            reference_min=entry.reference_min,
            reference_max=entry.reference_max,
            entered_at=datetime.now(timezone.utc),
        )
        await self.repository.enqueue_event(
            event_type="lab_result_entry_added" if created else "lab_result_entry_updated",
            aggregate_type="lab_report",
            aggregate_id=report_id,
            payload={
                "user_id": user_id,
                "entry_id": str(persisted.entry_id),
                "marker_id": str(entry.marker_id),
                "unit": entry.unit,
            },
        )
        return persisted


    async def mark_panel_started(self, *, user_id: str, report_id: UUID, panel_id: UUID) -> None:
        await self.repository.enqueue_event(
            event_type="lab_panel_started",
            aggregate_type="lab_report",
            aggregate_id=report_id,
            payload={"user_id": user_id, "panel_id": str(panel_id)},
        )

    async def mark_panel_completed(self, *, user_id: str, report_id: UUID, panel_id: UUID) -> None:
        await self.repository.enqueue_event(
            event_type="lab_panel_completed",
            aggregate_type="lab_report",
            aggregate_id=report_id,
            payload={"user_id": user_id, "panel_id": str(panel_id)},
        )

    async def finalize_report(self, *, user_id: str, report_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        await self.repository.finalize_lab_report(report_id, finalized_at=now)
        await self.repository.enqueue_event(
            event_type="lab_report_finalized",
            aggregate_type="lab_report",
            aggregate_id=report_id,
            payload={"user_id": user_id, "finalized_at": now.isoformat()},
        )

    async def list_history(self, user_id: str) -> list[LabReportView]:
        return await self.repository.list_lab_reports(user_id)

    async def get_report(self, user_id: str, report_id: UUID) -> LabReportDetailsView | None:
        return await self.repository.get_lab_report_details(report_id, user_id)


def _parse_decimal(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    token = raw.strip().replace(",", ".")
    if not token:
        return None
    try:
        return Decimal(token)
    except InvalidOperation:
        return None
