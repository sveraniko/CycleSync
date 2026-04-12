import structlog

from app.application.labs.schemas import LabTriageInputPayload
from app.application.labs.triage_gateway import LabsTriageGateway, LabsTriageGatewayError

logger = structlog.get_logger("cyclesync.labs.triage_gateway")


class GatewayModeLabsTriageGateway(LabsTriageGateway):
    def __init__(
        self,
        *,
        mode: str,
        heuristic_gateway: LabsTriageGateway,
        provider_gateway: LabsTriageGateway | None,
    ) -> None:
        self.mode = mode
        self.heuristic_gateway = heuristic_gateway
        self.provider_gateway = provider_gateway

    async def run_triage(self, payload: LabTriageInputPayload) -> dict:
        logger.info(
            "labs_triage_mode_selected",
            mode=self.mode,
            provider_configured=self.provider_gateway is not None,
        )
        if self.mode == "heuristic":
            return await self.heuristic_gateway.run_triage(payload)

        if self.mode == "provider":
            if self.provider_gateway is None:
                raise LabsTriageGatewayError("Provider mode selected but provider is not configured.")
            return await self.provider_gateway.run_triage(payload)

        if self.mode == "provider_with_heuristic_fallback":
            if self.provider_gateway is None:
                logger.warning("labs_triage_fallback", reason="provider_not_configured")
                return await self.heuristic_gateway.run_triage(payload)
            try:
                return await self.provider_gateway.run_triage(payload)
            except LabsTriageGatewayError as exc:
                logger.warning("labs_triage_fallback", reason="provider_failure", error=str(exc))
                return await self.heuristic_gateway.run_triage(payload)

        raise LabsTriageGatewayError(f"Unsupported labs triage gateway mode: {self.mode}")

    def diagnostics(self) -> dict:
        provider_diag = self.provider_gateway.diagnostics() if self.provider_gateway else None
        return {
            "gateway": self.__class__.__name__,
            "mode": self.mode,
            "provider_configured": self.provider_gateway is not None,
            "provider": provider_diag,
            "heuristic": self.heuristic_gateway.diagnostics(),
        }
