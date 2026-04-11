from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.labs.repository import LabsRepository
from app.application.labs.schemas import (
    LabMarkerView,
    LabPanelView,
    LabReportDetailsView,
    LabReportEntryView,
    LabReportView,
)
from app.domain.models.labs import (
    LabMarker,
    LabPanel,
    LabPanelMarker,
    LabReport,
    LabReportEntry,
)
from app.domain.models.ops import OutboxEvent


class SqlAlchemyLabsRepository(LabsRepository):
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def list_markers(self) -> list[LabMarkerView]:
        async with self.session_factory() as session:
            rows = await session.scalars(
                select(LabMarker)
                .where(LabMarker.is_active.is_(True))
                .order_by(LabMarker.category_code.asc(), LabMarker.display_name.asc())
            )
            return [self._to_marker_view(row) for row in rows]

    async def get_marker(self, marker_id: UUID) -> LabMarkerView | None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(LabMarker).where(LabMarker.id == marker_id, LabMarker.is_active.is_(True))
            )
            return None if row is None else self._to_marker_view(row)

    async def list_panels(self) -> list[LabPanelView]:
        async with self.session_factory() as session:
            panels = list(
                await session.scalars(
                    select(LabPanel).where(LabPanel.is_active.is_(True)).order_by(LabPanel.display_name.asc())
                )
            )
            out: list[LabPanelView] = []
            for panel in panels:
                marker_ids = list(
                    await session.scalars(
                        select(LabPanelMarker.marker_id)
                        .where(LabPanelMarker.panel_id == panel.id)
                        .order_by(LabPanelMarker.sort_order.asc())
                    )
                )
                out.append(
                    LabPanelView(
                        panel_id=panel.id,
                        panel_code=panel.panel_code,
                        display_name=panel.display_name,
                        marker_ids=marker_ids,
                    )
                )
            return out

    async def list_panel_markers(self, panel_id: UUID) -> list[LabMarkerView]:
        async with self.session_factory() as session:
            rows = list(
                await session.scalars(
                    select(LabMarker)
                    .join(LabPanelMarker, LabPanelMarker.marker_id == LabMarker.id)
                    .where(LabPanelMarker.panel_id == panel_id, LabMarker.is_active.is_(True))
                    .order_by(LabPanelMarker.sort_order.asc())
                )
            )
            return [self._to_marker_view(row) for row in rows]

    async def create_lab_report(self, *, user_id: str, protocol_id: UUID | None, report_date: date, source_lab_name: str | None, notes: str | None) -> LabReportView:
        async with self.session_factory() as session:
            row = LabReport(
                user_id=user_id,
                protocol_id=protocol_id,
                report_date=report_date,
                source_lab_name=source_lab_name,
                notes=notes,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_report_view(row)

    async def add_or_update_lab_report_entry(self, *, lab_report_id: UUID, marker_id: UUID, entered_value: str, numeric_value: Decimal | None, unit: str, reference_min: Decimal | None, reference_max: Decimal | None, entered_at: datetime) -> tuple[LabReportEntryView, bool]:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(LabReportEntry).where(
                    LabReportEntry.lab_report_id == lab_report_id,
                    LabReportEntry.marker_id == marker_id,
                )
            )
            created = row is None
            if row is None:
                row = LabReportEntry(lab_report_id=lab_report_id, marker_id=marker_id, entered_at=entered_at)
            row.entered_value = entered_value
            row.numeric_value = numeric_value
            row.unit = unit
            row.reference_min = reference_min
            row.reference_max = reference_max
            row.entered_at = entered_at
            session.add(row)
            await session.commit()
            row_with_marker = await session.execute(
                select(LabReportEntry, LabMarker)
                .join(LabMarker, LabMarker.id == LabReportEntry.marker_id)
                .where(LabReportEntry.id == row.id)
            )
            entry_row, marker = row_with_marker.one()
            return self._to_entry_view(entry_row, marker), created

    async def finalize_lab_report(self, report_id: UUID, finalized_at: datetime) -> None:
        async with self.session_factory() as session:
            row = await session.scalar(select(LabReport).where(LabReport.id == report_id))
            if row is None:
                return
            row.finalized_at = finalized_at
            session.add(row)
            await session.commit()

    async def list_lab_reports(self, user_id: str) -> list[LabReportView]:
        async with self.session_factory() as session:
            rows = await session.scalars(
                select(LabReport)
                .where(LabReport.user_id == user_id)
                .order_by(LabReport.report_date.desc(), LabReport.created_at.desc())
            )
            return [self._to_report_view(row) for row in rows]

    async def get_lab_report_details(self, report_id: UUID, user_id: str) -> LabReportDetailsView | None:
        async with self.session_factory() as session:
            report = await session.scalar(
                select(LabReport).where(LabReport.id == report_id, LabReport.user_id == user_id)
            )
            if report is None:
                return None
            rows = await session.execute(
                select(LabReportEntry, LabMarker)
                .join(LabMarker, LabMarker.id == LabReportEntry.marker_id)
                .where(LabReportEntry.lab_report_id == report_id)
                .order_by(LabMarker.display_name.asc())
            )
            entries = [self._to_entry_view(entry, marker) for entry, marker in rows.all()]
            return LabReportDetailsView(report=self._to_report_view(report), entries=entries)

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
    def _to_marker_view(row: LabMarker) -> LabMarkerView:
        return LabMarkerView(
            marker_id=row.id,
            marker_code=row.marker_code,
            display_name=row.display_name,
            category_code=row.category_code,
            default_unit=row.default_unit,
            accepted_units=list(row.accepted_units),
            notes=row.notes,
        )

    @staticmethod
    def _to_report_view(row: LabReport) -> LabReportView:
        return LabReportView(
            report_id=row.id,
            user_id=row.user_id,
            protocol_id=row.protocol_id,
            report_date=row.report_date,
            source_lab_name=row.source_lab_name,
            notes=row.notes,
            finalized_at=row.finalized_at,
            created_at=row.created_at,
        )

    @staticmethod
    def _to_entry_view(row: LabReportEntry, marker: LabMarker) -> LabReportEntryView:
        return LabReportEntryView(
            entry_id=row.id,
            lab_report_id=row.lab_report_id,
            marker_id=row.marker_id,
            marker_code=marker.marker_code,
            marker_display_name=marker.display_name,
            entered_value=row.entered_value,
            numeric_value=row.numeric_value,
            unit=row.unit,
            reference_min=row.reference_min,
            reference_max=row.reference_max,
            entered_at=row.entered_at,
        )
