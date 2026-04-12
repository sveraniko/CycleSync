from decimal import Decimal

from app.application.labs.schemas import LabTriageInputPayload
from app.application.labs.triage_gateway import LabsTriageGateway


class HeuristicLabsTriageGateway(LabsTriageGateway):
    def diagnostics(self) -> dict:
        return {
            "gateway": self.__class__.__name__,
            "mode": "heuristic",
            "provider_configured": False,
        }

    async def run_triage(self, payload: LabTriageInputPayload) -> dict:
        flags: list[dict] = []
        urgent_flag = False

        for marker in payload.markers:
            if marker.reference_max is not None and marker.numeric_value > marker.reference_max:
                severity = "warning"
                if marker.reference_max > 0 and marker.numeric_value >= marker.reference_max * Decimal("1.2"):
                    severity = "urgent"
                    urgent_flag = True
                flags.append(
                    {
                        "marker_code": marker.marker_code,
                        "severity": severity,
                        "flag_code": "marker.above_reference",
                        "title": f"{marker.marker_display_name} above reference",
                        "explanation": f"{marker.numeric_value} {marker.unit} is above report reference maximum.",
                        "suggested_followup": "Retest and review trend with specialist if persistent.",
                    }
                )
            if marker.reference_min is not None and marker.numeric_value < marker.reference_min:
                flags.append(
                    {
                        "marker_code": marker.marker_code,
                        "severity": "watch",
                        "flag_code": "marker.below_reference",
                        "title": f"{marker.marker_display_name} below reference",
                        "explanation": f"{marker.numeric_value} {marker.unit} is below report reference minimum.",
                        "suggested_followup": "Check repeat testing and protocol fit.",
                    }
                )

        summary = "No major deviations detected."
        if flags:
            summary = f"Detected {len(flags)} structured triage flag(s)."
        if payload.protocol_context is not None:
            summary += f" Protocol context status: {payload.protocol_context.status}."

        return {
            "summary": summary,
            "urgent_flag": urgent_flag,
            "flags": flags,
            "recommended_followups": [],
            "model_name": "heuristic-baseline",
            "prompt_version": "w6_pr2_v1",
        }
