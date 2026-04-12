from datetime import datetime, timezone

from app.application.access.repository import AccessRepository
from app.application.access.schemas import (
    ENTITLEMENT_CODES,
    EntitlementDecision,
    EntitlementGrantCreate,
    EntitlementGrantView,
)


class EntitlementError(ValueError):
    pass


class AccessEvaluationService:
    def __init__(self, repository: AccessRepository) -> None:
        self.repository = repository

    async def evaluate(self, *, user_id: str, entitlement_code: str, now_utc: datetime | None = None) -> EntitlementDecision:
        self._validate_entitlement_code(entitlement_code)
        now = now_utc or datetime.now(timezone.utc)
        active = await self.repository.get_active_grant(user_id=user_id, entitlement_code=entitlement_code)
        if active is None:
            return EntitlementDecision(
                allowed=False,
                reason_code="entitlement_absent",
                entitlement_code=entitlement_code,
                grant_source=None,
                expires_at=None,
                grant_id=None,
            )
        if active.expires_at is not None and active.expires_at <= now:
            await self.repository.expire_grant(grant_id=active.grant_id, now_utc=now)
            await self.repository.enqueue_event(
                event_type="entitlement_expired",
                aggregate_type="entitlement_grant",
                aggregate_id=active.grant_id,
                payload={
                    "user_id": user_id,
                    "entitlement_code": entitlement_code,
                    "expired_at": now.isoformat(),
                },
            )
            return EntitlementDecision(
                allowed=False,
                reason_code="entitlement_expired",
                entitlement_code=entitlement_code,
                grant_source=active.granted_by_source,
                expires_at=active.expires_at,
                grant_id=active.grant_id,
            )
        return EntitlementDecision(
            allowed=True,
            reason_code="entitlement_active",
            entitlement_code=entitlement_code,
            grant_source=active.granted_by_source,
            expires_at=active.expires_at,
            grant_id=active.grant_id,
        )

    async def grant(self, request: EntitlementGrantCreate, *, now_utc: datetime | None = None) -> EntitlementGrantView:
        self._validate_entitlement_code(request.entitlement_code)
        now = now_utc or datetime.now(timezone.utc)
        grant = await self.repository.create_grant(request, now_utc=now)
        await self.repository.enqueue_event(
            event_type="entitlement_granted",
            aggregate_type="entitlement_grant",
            aggregate_id=grant.grant_id,
            payload={
                "user_id": grant.user_id,
                "entitlement_code": grant.entitlement_code,
                "granted_by_source": grant.granted_by_source,
                "source_ref": grant.source_ref,
                "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
            },
        )
        return grant

    async def revoke(
        self,
        *,
        user_id: str,
        entitlement_code: str,
        revoked_by_source: str,
        reason: str | None = None,
        source_ref: str | None = None,
        now_utc: datetime | None = None,
    ) -> int:
        self._validate_entitlement_code(entitlement_code)
        now = now_utc or datetime.now(timezone.utc)
        count = await self.repository.revoke_active_grants(
            user_id=user_id,
            entitlement_code=entitlement_code,
            revoked_by_source=revoked_by_source,
            now_utc=now,
            reason=reason,
            source_ref=source_ref,
        )
        if count > 0:
            await self.repository.enqueue_event(
                event_type="entitlement_revoked",
                aggregate_type="entitlement",
                aggregate_id=_stable_access_aggregate_id(user_id=user_id, entitlement_code=entitlement_code),
                payload={
                    "user_id": user_id,
                    "entitlement_code": entitlement_code,
                    "revoked_count": count,
                    "revoked_by_source": revoked_by_source,
                    "reason": reason,
                    "source_ref": source_ref,
                    "revoked_at": now.isoformat(),
                },
            )
        return count

    async def list_user_grants(self, *, user_id: str, only_active: bool = False) -> list[EntitlementGrantView]:
        return await self.repository.list_user_grants(user_id=user_id, only_active=only_active)

    @staticmethod
    def _validate_entitlement_code(entitlement_code: str) -> None:
        if entitlement_code not in ENTITLEMENT_CODES:
            raise EntitlementError(f"unsupported_entitlement_code:{entitlement_code}")


def _stable_access_aggregate_id(*, user_id: str, entitlement_code: str):
    import uuid

    return uuid.uuid5(uuid.NAMESPACE_URL, f"cyclesync:access:{user_id}:{entitlement_code}")
