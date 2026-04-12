from datetime import datetime
from uuid import UUID

from app.application.access.schemas import (
    AccessKeyCreate,
    AccessKeyEntitlementTemplate,
    AccessKeyRedemptionView,
    AccessKeyView,
    EntitlementGrantCreate,
    EntitlementGrantView,
)


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

    async def create_access_key(self, request: AccessKeyCreate, *, now_utc: datetime) -> AccessKeyView:
        raise NotImplementedError

    async def get_access_key_by_code(self, *, key_code: str) -> AccessKeyView | None:
        raise NotImplementedError

    async def update_access_key_status(self, *, key_id: UUID, status: str, now_utc: datetime) -> AccessKeyView | None:
        raise NotImplementedError

    async def increment_access_key_redemption_count(self, *, key_id: UUID, now_utc: datetime) -> AccessKeyView | None:
        raise NotImplementedError

    async def list_key_entitlements(self, *, key_id: UUID) -> tuple[AccessKeyEntitlementTemplate, ...]:
        raise NotImplementedError

    async def find_successful_redemption(self, *, key_id: UUID, user_id: str) -> AccessKeyRedemptionView | None:
        raise NotImplementedError

    async def create_access_key_redemption(
        self,
        *,
        key_id: UUID,
        user_id: str,
        redeemed_at: datetime,
        result_status: str,
        result_reason_code: str | None,
        created_grant_ids: tuple[UUID, ...],
    ) -> AccessKeyRedemptionView:
        raise NotImplementedError

    async def list_access_key_redemptions(self, *, key_id: UUID) -> list[AccessKeyRedemptionView]:
        raise NotImplementedError
