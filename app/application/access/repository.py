from datetime import datetime
from uuid import UUID

from app.application.access.schemas import EntitlementGrantCreate, EntitlementGrantView


class AccessRepository:
    async def get_active_grant(self, *, user_id: str, entitlement_code: str) -> EntitlementGrantView | None:
        raise NotImplementedError

    async def expire_grant(self, *, grant_id: UUID, now_utc: datetime) -> None:
        raise NotImplementedError

    async def create_grant(self, request: EntitlementGrantCreate, *, now_utc: datetime) -> EntitlementGrantView:
        raise NotImplementedError

    async def revoke_active_grants(
        self,
        *,
        user_id: str,
        entitlement_code: str,
        revoked_by_source: str,
        now_utc: datetime,
        reason: str | None,
        source_ref: str | None,
    ) -> int:
        raise NotImplementedError

    async def list_user_grants(self, *, user_id: str, only_active: bool = False) -> list[EntitlementGrantView]:
        raise NotImplementedError

    async def enqueue_event(self, *, event_type: str, aggregate_type: str, aggregate_id: UUID, payload: dict) -> None:
        raise NotImplementedError
