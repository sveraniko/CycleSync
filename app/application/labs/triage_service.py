from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.application.labs.repository import LabsRepository
from app.application.labs.schemas import (
    LabTriageFlagCreate,
    LabTriageInputMarker,
    LabTriageInputPayload,
    LabTriageResultView,
)
from app.application.labs.triage_gateway import LabsTriageGateway, LabsTriageGatewayError

ALLOWED_SEVERITIES = {"info", "watch", "warning", "urgent"}


class LabsTriageError(ValueError):
    pass


class LabsTriageParsingError(LabsTriageError):
    pass


@dataclass(slots=True)
class ParsedTriageOutput:
    summary: str
    urgent_flag: bool
    flags: list[LabTriageFlagCreate]
    recommended_followups: list[str]
    model_name: str
    prompt_version: str


class LabsTriageService:
    def __init__(self, repository: LabsRepository, gateway: LabsTriageGateway) -> None:
        self.repository = repository
        self.gateway = gateway

    async def run_triage(
        self, *, user_id: str, report_id: UUID, regenerate: bool = False
    ) -> LabTriageResultView:
        existing = await self.repository.get_latest_triage_result(report_id=report_id, user_id=user_id)
        if existing is not None and not regenerate:
            return existing

        report = await self.repository.get_lab_report_details(report_id=report_id, user_id=user_id)
        if report is None:
            raise LabsTriageError("Lab report not found.")
        if not report.entries:
            raise LabsTriageError("Cannot triage empty report.")

        marker_map = {m.marker_id: m for m in await self.repository.list_markers()}
        markers: list[LabTriageInputMarker] = []
        for entry in report.entries:
            marker = marker_map.get(entry.marker_id)
            if marker is None:
                raise LabsTriageError(f"Unknown marker: {entry.marker_id}.")
            if entry.numeric_value is None:
                raise LabsTriageError(f"Marker {marker.display_name} must be numeric.")
            if entry.unit not in marker.accepted_units:
                raise LabsTriageError(f"Unsupported unit for {marker.display_name}: {entry.unit}.")
            markers.append(
                LabTriageInputMarker(
                    marker_id=entry.marker_id,
                    marker_code=entry.marker_code,
                    marker_display_name=entry.marker_display_name,
                    category_code=marker.category_code,
                    numeric_value=entry.numeric_value,
                    unit=entry.unit,
                    reference_min=entry.reference_min,
                    reference_max=entry.reference_max,
                )
            )

        protocol_context = None
        if report.report.protocol_id is not None:
            protocol_context = await self.repository.get_active_protocol_context(
                protocol_id=report.report.protocol_id, user_id=user_id
            )

        payload = LabTriageInputPayload(
            report_id=report.report.report_id,
            user_id=user_id,
            report_date=report.report.report_date,
            protocol_context=protocol_context,
            markers=markers,
        )
        await self.repository.enqueue_event(
            event_type="lab_triage_requested",
            aggregate_type="lab_report",
            aggregate_id=report.report.report_id,
            payload={"user_id": user_id, "regenerate": regenerate},
        )

        if existing is not None and regenerate:
            await self.repository.enqueue_event(
                event_type="lab_triage_regenerated",
                aggregate_type="lab_report",
                aggregate_id=report.report.report_id,
                payload={"user_id": user_id},
            )

        try:
            raw = await self.gateway.run_triage(payload)
            parsed = parse_triage_output(raw=raw, marker_code_map={m.marker_code: m.marker_id for m in markers})
            guardrail_flags = self._build_guardrail_flags(markers=markers)
            flags = parsed.flags + guardrail_flags
            completed_at = datetime.now(timezone.utc)
            run = await self.repository.create_lab_triage_run(
                lab_report_id=report.report.report_id,
                user_id=user_id,
                protocol_id=report.report.protocol_id,
                triage_status="completed",
                summary_text=parsed.summary,
                urgent_flag=parsed.urgent_flag or any(flag.severity == "urgent" for flag in flags),
                model_name=parsed.model_name,
                prompt_version=parsed.prompt_version,
                raw_result_json=raw,
                completed_at=completed_at,
            )
            persisted_flags = await self.repository.create_lab_triage_flags(triage_run_id=run.triage_run_id, flags=flags)
            await self.repository.enqueue_event(
                event_type="lab_triage_completed",
                aggregate_type="lab_report",
                aggregate_id=report.report.report_id,
                payload={"user_id": user_id, "triage_run_id": str(run.triage_run_id)},
            )
            if run.urgent_flag:
                await self.repository.enqueue_event(
                    event_type="lab_triage_urgent_detected",
                    aggregate_type="lab_report",
                    aggregate_id=report.report.report_id,
                    payload={"user_id": user_id, "triage_run_id": str(run.triage_run_id)},
                )
            return LabTriageResultView(run=run, flags=persisted_flags)
        except (LabsTriageParsingError, LabsTriageError, LabsTriageGatewayError) as exc:
            failed_run = await self.repository.create_lab_triage_run(
                lab_report_id=report.report.report_id,
                user_id=user_id,
                protocol_id=report.report.protocol_id,
                triage_status="failed",
                summary_text=None,
                urgent_flag=False,
                model_name="unknown",
                prompt_version="unknown",
                raw_result_json={"error": str(exc)},
                completed_at=datetime.now(timezone.utc),
            )
            await self.repository.enqueue_event(
                event_type="lab_triage_failed",
                aggregate_type="lab_report",
                aggregate_id=report.report.report_id,
                payload={"user_id": user_id, "triage_run_id": str(failed_run.triage_run_id), "error": str(exc)},
            )
            raise

    async def get_latest_triage(self, *, user_id: str, report_id: UUID) -> LabTriageResultView | None:
        return await self.repository.get_latest_triage_result(report_id=report_id, user_id=user_id)

    @staticmethod
    def _build_guardrail_flags(*, markers: list[LabTriageInputMarker]) -> list[LabTriageFlagCreate]:
        flags: list[LabTriageFlagCreate] = []
        if any(m.reference_min is None and m.reference_max is None for m in markers):
            flags.append(
                LabTriageFlagCreate(
                    marker_id=None,
                    severity="watch",
                    flag_code="data.reference_range_missing",
                    title="Reference ranges are incomplete",
                    explanation="Some markers do not include reference min/max values, so interpretation confidence is lower.",
                    suggested_followup="Add lab-provided reference ranges where possible.",
                )
            )
        if len(markers) < 2:
            flags.append(
                LabTriageFlagCreate(
                    marker_id=None,
                    severity="warning",
                    flag_code="data.missing_required_markers",
                    title="Report has low marker completeness",
                    explanation="This report has too few markers for stable pre-triage interpretation.",
                    suggested_followup="Add the rest of panel markers before requesting triage.",
                )
            )
        return flags


def parse_triage_output(*, raw: dict, marker_code_map: dict[str, UUID]) -> ParsedTriageOutput:
    if not isinstance(raw, dict):
        raise LabsTriageParsingError("Triage result must be a JSON object.")

    summary = raw.get("summary")
    urgent_flag = raw.get("urgent_flag")
    model_name = raw.get("model_name", "unknown")
    prompt_version = raw.get("prompt_version", "unknown")
    flags_raw = raw.get("flags")
    recommended_followups = raw.get("recommended_followups", [])

    if not isinstance(summary, str) or not summary.strip():
        raise LabsTriageParsingError("Missing summary.")
    if not isinstance(urgent_flag, bool):
        raise LabsTriageParsingError("urgent_flag must be boolean.")
    if not isinstance(flags_raw, list):
        raise LabsTriageParsingError("flags must be a list.")
    if not isinstance(recommended_followups, list):
        raise LabsTriageParsingError("recommended_followups must be a list.")

    flags: list[LabTriageFlagCreate] = []
    for row in flags_raw:
        if not isinstance(row, dict):
            raise LabsTriageParsingError("Each flag must be an object.")
        severity = row.get("severity")
        if severity not in ALLOWED_SEVERITIES:
            raise LabsTriageParsingError(f"Invalid severity: {severity}.")
        marker_code = row.get("marker_code")
        marker_id = None
        if marker_code is not None:
            if not isinstance(marker_code, str):
                raise LabsTriageParsingError("marker_code must be string or null.")
            marker_id = marker_code_map.get(marker_code)
        title = row.get("title")
        explanation = row.get("explanation")
        flag_code = row.get("flag_code")
        suggested_followup = row.get("suggested_followup")
        if not isinstance(title, str) or not title.strip():
            raise LabsTriageParsingError("Flag title is required.")
        if not isinstance(explanation, str) or not explanation.strip():
            raise LabsTriageParsingError("Flag explanation is required.")
        if not isinstance(flag_code, str) or not flag_code.strip():
            raise LabsTriageParsingError("Flag code is required.")
        if suggested_followup is not None and not isinstance(suggested_followup, str):
            raise LabsTriageParsingError("suggested_followup must be string or null.")
        flags.append(
            LabTriageFlagCreate(
                marker_id=marker_id,
                severity=severity,
                flag_code=flag_code,
                title=title,
                explanation=explanation,
                suggested_followup=suggested_followup,
            )
        )
    return ParsedTriageOutput(
        summary=summary.strip(),
        urgent_flag=urgent_flag,
        flags=flags,
        recommended_followups=[item for item in recommended_followups if isinstance(item, str) and item.strip()],
        model_name=model_name if isinstance(model_name, str) else "unknown",
        prompt_version=prompt_version if isinstance(prompt_version, str) else "unknown",
    )
