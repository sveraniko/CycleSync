import asyncio
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import httpx

from app.application.labs.schemas import LabTriageInputMarker, LabTriageInputPayload, ProtocolTriageContextView
from app.application.labs.triage_gateway import LabsTriageGatewayError
from app.infrastructure.labs.heuristic_triage_gateway import HeuristicLabsTriageGateway
from app.infrastructure.labs.openai_triage_gateway import OpenAILabsTriageGateway
from app.infrastructure.labs.provider_triage_prompt import LabsTriagePromptBuilder
from app.infrastructure.labs.triage_gateway_selector import GatewayModeLabsTriageGateway


def _payload() -> LabTriageInputPayload:
    return LabTriageInputPayload(
        report_id=uuid4(),
        user_id="u1",
        report_date=date(2026, 4, 12),
        protocol_context=ProtocolTriageContextView(
            protocol_id=uuid4(),
            status="active",
            activated_at=datetime.now(timezone.utc),
            selected_products=["Test E"],
            pulse_plan_context={"weekly_target_total_mg": 300},
            adherence_integrity_state="watch",
            adherence_integrity_detail={"missed": 1},
        ),
        markers=[
            LabTriageInputMarker(
                marker_id=uuid4(),
                marker_code="hematocrit",
                marker_display_name="Hematocrit",
                category_code="hematology",
                numeric_value=Decimal("54.0"),
                unit="%",
                reference_min=Decimal("40.0"),
                reference_max=Decimal("50.0"),
            )
        ],
    )


def test_provider_prompt_builder_contains_structured_context() -> None:
    prompt = LabsTriagePromptBuilder(prompt_version="w6_pr3_v1").build(_payload())
    assert "structured_input=" in prompt["user_prompt"]
    assert "adherence_integrity_snapshot" in prompt["user_prompt"]
    assert "output_contract" in prompt["user_prompt"]


def test_provider_gateway_happy_path_with_mocked_http() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Detected one warning.",
                                    "urgent_flag": False,
                                    "flags": [
                                        {
                                            "marker_code": "hematocrit",
                                            "severity": "warning",
                                            "flag_code": "marker.above_reference",
                                            "title": "HCT high",
                                            "explanation": "Above max",
                                            "suggested_followup": "Retest",
                                        }
                                    ],
                                    "recommended_followups": [],
                                }
                            )
                        }
                    }
                ]
            },
        )

    gateway = OpenAILabsTriageGateway(
        api_key="test-key",
        model_name="gpt-test",
        prompt_builder=LabsTriagePromptBuilder(prompt_version="w6_pr3_v1"),
        timeout_seconds=1.0,
        base_url="https://example.test/v1",
    )
    gateway.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://example.test/v1")

    result = asyncio.run(gateway.run_triage(_payload()))
    asyncio.run(gateway.close())

    assert captured["body"]["model"] == "gpt-test"
    assert captured["body"]["response_format"]["type"] == "json_object"
    assert result["summary"] == "Detected one warning."
    assert result["model_name"] == "gpt-test"
    assert result["prompt_version"] == "w6_pr3_v1"


def test_provider_gateway_malformed_output_fails_safely() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json={"choices": [{"message": {"content": "not-json"}}]})

    gateway = OpenAILabsTriageGateway(
        api_key="test-key",
        model_name="gpt-test",
        prompt_builder=LabsTriagePromptBuilder(prompt_version="w6_pr3_v1"),
        timeout_seconds=1.0,
        base_url="https://example.test/v1",
    )
    gateway.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://example.test/v1")

    try:
        asyncio.run(gateway.run_triage(_payload()))
        assert False, "expected gateway failure"
    except LabsTriageGatewayError:
        pass
    finally:
        asyncio.run(gateway.close())

    assert gateway.last_failure_category == "malformed_provider_payload"


def test_gateway_mode_selection() -> None:
    payload = _payload()
    heuristic = HeuristicLabsTriageGateway()

    provider_selector = GatewayModeLabsTriageGateway(
        mode="provider",
        heuristic_gateway=heuristic,
        provider_gateway=heuristic,
    )
    heuristic_selector = GatewayModeLabsTriageGateway(
        mode="heuristic",
        heuristic_gateway=heuristic,
        provider_gateway=None,
    )

    provider_result = asyncio.run(provider_selector.run_triage(payload))
    heuristic_result = asyncio.run(heuristic_selector.run_triage(payload))

    assert provider_selector.diagnostics()["mode"] == "provider"
    assert heuristic_selector.diagnostics()["mode"] == "heuristic"
    assert provider_result["model_name"] == "heuristic-baseline"
    assert heuristic_result["model_name"] == "heuristic-baseline"


def test_provider_fallback_mode_uses_heuristic_on_failure() -> None:
    class _FailingProvider:
        async def run_triage(self, _payload):
            raise LabsTriageGatewayError("provider unavailable")

        def diagnostics(self):
            return {"mode": "provider"}

    selector = GatewayModeLabsTriageGateway(
        mode="provider_with_heuristic_fallback",
        heuristic_gateway=HeuristicLabsTriageGateway(),
        provider_gateway=_FailingProvider(),
    )

    result = asyncio.run(selector.run_triage(_payload()))
    assert result["model_name"] == "heuristic-baseline"
