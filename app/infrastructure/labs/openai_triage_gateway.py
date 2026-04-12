import json
from typing import Any

import httpx

from app.application.labs.schemas import LabTriageInputPayload
from app.application.labs.triage_gateway import LabsTriageGateway, LabsTriageGatewayError
from app.infrastructure.labs.provider_triage_prompt import LabsTriagePromptBuilder


class OpenAILabsTriageGateway(LabsTriageGateway):
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        prompt_builder: LabsTriagePromptBuilder,
        timeout_seconds: float,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self.model_name = model_name
        self.prompt_builder = prompt_builder
        self.last_failure_category: str | None = None
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout_seconds)

    async def close(self) -> None:
        await self.client.aclose()

    async def run_triage(self, payload: LabTriageInputPayload) -> dict:
        rendered = self.prompt_builder.build(payload)
        body = {
            "model": self.model_name,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": rendered["system_prompt"]},
                {"role": "user", "content": rendered["user_prompt"]},
            ],
        }
        try:
            response = await self.client.post("/chat/completions", json=body)
            response.raise_for_status()
            parsed = _extract_json(response.json())
            parsed.setdefault("model_name", self.model_name)
            parsed.setdefault("prompt_version", rendered["prompt_version"])
            self.last_failure_category = None
            return parsed
        except httpx.TimeoutException as exc:
            self.last_failure_category = "timeout"
            raise LabsTriageGatewayError("Provider triage timeout.") from exc
        except httpx.HTTPStatusError as exc:
            self.last_failure_category = f"http_{exc.response.status_code}"
            raise LabsTriageGatewayError("Provider triage HTTP failure.") from exc
        except httpx.HTTPError as exc:
            self.last_failure_category = "transport"
            raise LabsTriageGatewayError("Provider triage transport failure.") from exc
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self.last_failure_category = "malformed_provider_payload"
            raise LabsTriageGatewayError("Provider returned malformed triage payload.") from exc

    def diagnostics(self) -> dict:
        return {
            "gateway": self.__class__.__name__,
            "mode": "provider",
            "provider": "openai",
            "provider_configured": True,
            "model_name": self.model_name,
            "prompt_version": self.prompt_builder.prompt_version,
            "last_provider_failure_category": self.last_failure_category,
        }


def _extract_json(payload: dict[str, Any]) -> dict:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("missing choices")
    content = choices[0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("missing assistant content")
    structured = json.loads(content)
    if not isinstance(structured, dict):
        raise ValueError("provider output must be object")
    return structured
