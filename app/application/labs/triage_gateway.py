from app.application.labs.schemas import LabTriageInputPayload


class LabsTriageGateway:
    async def run_triage(self, payload: LabTriageInputPayload) -> dict:
        raise NotImplementedError
