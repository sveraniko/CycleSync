from app.application.labs.schemas import LabTriageInputPayload


class LabsTriageGatewayError(ValueError):
    """Raised when triage gateway invocation fails before structured parsing."""


class LabsTriageGateway:
    async def run_triage(self, payload: LabTriageInputPayload) -> dict:
        raise NotImplementedError

    def diagnostics(self) -> dict:
        return {
            "gateway": self.__class__.__name__,
            "mode": "unknown",
            "provider_configured": False,
        }
