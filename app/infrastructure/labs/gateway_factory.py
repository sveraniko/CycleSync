from app.core.config import Settings
from app.infrastructure.labs.heuristic_triage_gateway import HeuristicLabsTriageGateway
from app.infrastructure.labs.openai_triage_gateway import OpenAILabsTriageGateway
from app.infrastructure.labs.provider_triage_prompt import LabsTriagePromptBuilder
from app.infrastructure.labs.triage_gateway_selector import GatewayModeLabsTriageGateway


def build_labs_triage_gateway(settings: Settings) -> GatewayModeLabsTriageGateway:
    heuristic_gateway = HeuristicLabsTriageGateway()
    provider_gateway = None

    if settings.labs_ai_provider == "openai" and settings.labs_ai_openai_api_key:
        provider_gateway = OpenAILabsTriageGateway(
            api_key=settings.labs_ai_openai_api_key,
            model_name=settings.labs_ai_model,
            prompt_builder=LabsTriagePromptBuilder(prompt_version=settings.labs_ai_prompt_version),
            timeout_seconds=settings.labs_ai_timeout_seconds,
            base_url=settings.labs_ai_base_url,
        )

    return GatewayModeLabsTriageGateway(
        mode=settings.labs_triage_gateway_mode,
        heuristic_gateway=heuristic_gateway,
        provider_gateway=provider_gateway,
    )
