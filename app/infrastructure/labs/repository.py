from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.labs.repository import LabsRepository
from app.application.labs.schemas import (
    LabTriageFlagCreate,
    LabTriageFlagView,
    LabTriageResultView,
    LabTriageRunView,
    ProtocolTriageContextView,
    LabMarkerView,
    LabPanelView,
    LabReportDetailsView,
    LabReportEntryView,
    LabReportView,
)
from app.domain.models.ai_triage import LabTriageFlag, LabTriageRun
from app.domain.models.labs import (
    LabMarker,
    LabPanel,
    LabPanelMarker,
    LabReport,
    LabReportEntry,
)
from app.domain.models.ops import OutboxEvent
from app.domain.models.protocols import Protocol
from app.domain.models.reminders import ProtocolAdherenceSummary


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

    async def get_active_protocol_context(
        self, *, protocol_id: UUID, user_id: str
    ) -> ProtocolTriageContextView | None:
        async with self.session_factory() as session:
            protocol = await session.scalar(
                select(Protocol).where(
                    Protocol.id == protocol_id,
                    Protocol.user_id == user_id,
                    Protocol.status == "active",
                )
            )
            if protocol is None:
                return None
            adherence = await session.scalar(
                select(ProtocolAdherenceSummary).where(
                    ProtocolAdherenceSummary.protocol_id == protocol.id
                )
            )
            summary = protocol.summary_snapshot_json or {}
            settings = protocol.settings_snapshot_json or {}
            return ProtocolTriageContextView(
                protocol_id=protocol.id,
                status=protocol.status,
                activated_at=protocol.activated_at,
                selected_products=list(summary.get("products", []))
                if isinstance(summary.get("products"), list)
                else [],
                pulse_plan_context={
                    "weekly_target_total_mg": settings.get("weekly_target_total_mg"),
                    "duration_weeks": settings.get("duration_weeks"),
                },
                adherence_integrity_state=adherence.integrity_state if adherence else None,
                adherence_integrity_detail=adherence.integrity_detail_json if adherence else None,
            )

    async def create_lab_triage_run(
        self,
        *,
        lab_report_id: UUID,
        user_id: str,
        protocol_id: UUID | None,
        triage_status: str,
        summary_text: str | None,
        urgent_flag: bool,
        model_name: str,
        prompt_version: str,
        raw_result_json: dict | None,
        completed_at: datetime | None,
    ) -> LabTriageRunView:
        async with self.session_factory() as session:
            row = LabTriageRun(
                lab_report_id=lab_report_id,
                user_id=user_id,
                protocol_id=protocol_id,
                triage_status=triage_status,
                summary_text=summary_text,
                urgent_flag=urgent_flag,
                model_name=model_name,
                prompt_version=prompt_version,
                raw_result_json=raw_result_json,
                completed_at=completed_at,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_triage_run_view(row)

    async def create_lab_triage_flags(
        self, *, triage_run_id: UUID, flags: list[LabTriageFlagCreate]
    ) -> list[LabTriageFlagView]:
        async with self.session_factory() as session:
            rows: list[LabTriageFlag] = []
            for flag in flags:
                row = LabTriageFlag(
                    triage_run_id=triage_run_id,
                    marker_id=flag.marker_id,
                    severity=flag.severity,
                    flag_code=flag.flag_code,
                    title=flag.title,
                    explanation=flag.explanation,
                    suggested_followup=flag.suggested_followup,
                )
                rows.append(row)
                session.add(row)
            await session.commit()
            for row in rows:
                await session.refresh(row)
            return [self._to_triage_flag_view(row) for row in rows]

    async def get_latest_triage_result(
        self, *, report_id: UUID, user_id: str
    ) -> LabTriageResultView | None:
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
                    select(LabTriageFlag)
                    .where(LabTriageFlag.triage_run_id == run.id)
                    .order_by(LabTriageFlag.created_at.asc())
                )
            )
            return LabTriageResultView(
                run=self._to_triage_run_view(run),
                flags=[self._to_triage_flag_view(flag) for flag in flags],
            )

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

    @staticmethod
    def _to_triage_run_view(row: LabTriageRun) -> LabTriageRunView:
        return LabTriageRunView(
            triage_run_id=row.id,
            lab_report_id=row.lab_report_id,
            user_id=row.user_id,
            protocol_id=row.protocol_id,
            triage_status=row.triage_status,
            summary_text=row.summary_text,
            urgent_flag=row.urgent_flag,
            model_name=row.model_name,
            prompt_version=row.prompt_version,
            raw_result_json=row.raw_result_json,
            created_at=row.created_at,
            completed_at=row.completed_at,
        )

    @staticmethod
    def _to_triage_flag_view(row: LabTriageFlag) -> LabTriageFlagView:
        return LabTriageFlagView(
            flag_id=row.id,
            triage_run_id=row.triage_run_id,
            marker_id=row.marker_id,
            severity=row.severity,
            flag_code=row.flag_code,
            title=row.title,
            explanation=row.explanation,
            suggested_followup=row.suggested_followup,
            created_at=row.created_at,
        )
