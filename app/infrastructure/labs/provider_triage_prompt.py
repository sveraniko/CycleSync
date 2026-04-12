import json
from decimal import Decimal

from app.application.labs.schemas import LabTriageInputPayload


SYSTEM_INSTRUCTION = (
    "You are CycleSync Labs AI pre-triage assistant. "
    "Only use supplied structured data. "
    "Do not prescribe treatment. "
    "Do not invent unsupported claims. "
    "Return strict JSON object only."
)


class LabsTriagePromptBuilder:
    def __init__(self, *, prompt_version: str) -> None:
        self.prompt_version = prompt_version

    def build(self, payload: LabTriageInputPayload) -> dict[str, object]:
        markers = [
            {
                "marker_code": marker.marker_code,
                "marker_display_name": marker.marker_display_name,
                "category_code": marker.category_code,
                "numeric_value": _stringify_decimal(marker.numeric_value),
                "unit": marker.unit,
                "reference_min": _stringify_decimal(marker.reference_min),
                "reference_max": _stringify_decimal(marker.reference_max),
            }
            for marker in payload.markers
        ]

        structured_input = {
            "report_id": str(payload.report_id),
            "user_id": payload.user_id,
            "report_date": payload.report_date.isoformat(),
            "markers": markers,
            "protocol_context": _render_protocol_context(payload),
            "adherence_integrity_snapshot": _render_adherence_snapshot(payload),
            "output_contract": {
                "summary": "string (required)",
                "urgent_flag": "boolean (required)",
                "flags": [
                    {
                        "marker_code": "string|null",
                        "severity": "info|watch|warning|urgent",
                        "flag_code": "string",
                        "title": "string",
                        "explanation": "string",
                        "suggested_followup": "string|null",
                    }
                ],
                "recommended_followups": ["string"],
                "model_name": "string",
                "prompt_version": self.prompt_version,
            },
            "constraints": [
                "No prose outside JSON.",
                "No treatment prescription.",
                "No unsupported claims.",
                "Use only marker/protocol/adherence data supplied.",
            ],
        }

        user_prompt = (
            "Generate labs pre-triage JSON according to output_contract. "
            "Return valid JSON object and include prompt_version exactly as provided.\n"
            f"structured_input={json.dumps(structured_input, ensure_ascii=False)}"
        )
        return {
            "system_prompt": SYSTEM_INSTRUCTION,
            "user_prompt": user_prompt,
            "prompt_version": self.prompt_version,
            "structured_input": structured_input,
        }


def _render_protocol_context(payload: LabTriageInputPayload) -> dict | None:
    protocol_context = payload.protocol_context
    if protocol_context is None:
        return None
    return {
        "protocol_id": str(protocol_context.protocol_id),
        "status": protocol_context.status,
        "activated_at": protocol_context.activated_at.isoformat() if protocol_context.activated_at else None,
        "selected_products": protocol_context.selected_products,
        "pulse_plan_context": protocol_context.pulse_plan_context,
    }


def _render_adherence_snapshot(payload: LabTriageInputPayload) -> dict | None:
    protocol_context = payload.protocol_context
    if protocol_context is None:
        return None
    if protocol_context.adherence_integrity_state is None and protocol_context.adherence_integrity_detail is None:
        return None
    return {
        "integrity_state": protocol_context.adherence_integrity_state,
        "integrity_detail": protocol_context.adherence_integrity_detail,
    }


def _stringify_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")
