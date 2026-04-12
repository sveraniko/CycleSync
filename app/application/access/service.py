from datetime import datetime, timezone
from datetime import timedelta
from uuid import UUID

from app.application.access.repository import AccessRepository
from app.application.access.schemas import (
    ACCESS_KEY_STATUSES,
    AccessKeyCreate,
    AccessKeyRedemptionResult,
    AccessKeyView,
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


class AccessKeyService:
    def __init__(self, repository: AccessRepository, evaluator: AccessEvaluationService) -> None:
        self.repository = repository
        self.evaluator = evaluator

    async def create_key(self, request: AccessKeyCreate, *, now_utc: datetime | None = None) -> AccessKeyView:
        if request.max_redemptions < 1:
            raise EntitlementError("access_key_max_redemptions_must_be_positive")
        for template in request.entitlements:
            AccessEvaluationService._validate_entitlement_code(template.entitlement_code)
        now = now_utc or datetime.now(timezone.utc)
        if request.expires_at is not None and request.expires_at <= now:
            raise EntitlementError("access_key_expiry_must_be_in_future")
        created = await self.repository.create_access_key(request, now_utc=now)
        await self.repository.enqueue_event(
            event_type="access_key_created",
            aggregate_type="access_key",
            aggregate_id=created.key_id,
            payload={
                "key_id": str(created.key_id),
                "status": created.status,
                "max_redemptions": created.max_redemptions,
                "expires_at": created.expires_at.isoformat() if created.expires_at else None,
                "entitlements": [item.entitlement_code for item in created.entitlements],
            },
        )
        return created

    async def inspect_key(self, *, key_code: str) -> AccessKeyView | None:
        return await self.repository.get_access_key_by_code(key_code=key_code)

    async def disable_key(self, *, key_code: str, now_utc: datetime | None = None) -> AccessKeyView:
        now = now_utc or datetime.now(timezone.utc)
        key = await self.repository.get_access_key_by_code(key_code=key_code)
        if key is None:
            raise EntitlementError("access_key_not_found")
        updated = await self.repository.update_access_key_status(key_id=key.key_id, status="disabled", now_utc=now)
        if updated is None:
            raise EntitlementError("access_key_not_found")
        await self.repository.enqueue_event(
            event_type="access_key_disabled",
            aggregate_type="access_key",
            aggregate_id=updated.key_id,
            payload={"key_id": str(updated.key_id), "disabled_at": now.isoformat()},
        )
        return updated

    async def redeem_key(self, *, user_id: str, key_code: str, now_utc: datetime | None = None) -> AccessKeyRedemptionResult:
        now = now_utc or datetime.now(timezone.utc)
        key = await self.repository.get_access_key_by_code(key_code=key_code)
        if key is None:
            return await self._failed_redemption(
                key_id=None,
                user_id=user_id,
                reason_code="access_key_invalid",
                key_status="missing",
                now_utc=now,
            )

        if key.status not in ACCESS_KEY_STATUSES:
            return await self._failed_redemption(
                key_id=key.key_id,
                user_id=user_id,
                reason_code="access_key_invalid_status",
                key_status=key.status,
                now_utc=now,
            )
        if key.status == "disabled":
            return await self._failed_redemption(key_id=key.key_id, user_id=user_id, reason_code="access_key_disabled", key_status=key.status, now_utc=now)
        if key.status == "expired" or (key.expires_at and key.expires_at <= now):
            await self.repository.update_access_key_status(key_id=key.key_id, status="expired", now_utc=now)
            return await self._failed_redemption(key_id=key.key_id, user_id=user_id, reason_code="access_key_expired", key_status="expired", now_utc=now)
        if key.redeemed_count >= key.max_redemptions or key.status == "exhausted":
            await self.repository.update_access_key_status(key_id=key.key_id, status="exhausted", now_utc=now)
            return await self._failed_redemption(key_id=key.key_id, user_id=user_id, reason_code="access_key_exhausted", key_status="exhausted", now_utc=now)

        existing = await self.repository.find_successful_redemption(key_id=key.key_id, user_id=user_id)
        if existing is not None:
            return await self._failed_redemption(
                key_id=key.key_id,
                user_id=user_id,
                reason_code="access_key_already_redeemed_by_user",
                key_status=key.status,
                now_utc=now,
            )

        granted: list[EntitlementGrantView] = []
        for template in key.entitlements:
            expires_at = now + timedelta(days=template.grant_duration_days) if template.grant_duration_days else None
            grant = await self.evaluator.grant(
                EntitlementGrantCreate(
                    user_id=user_id,
                    entitlement_code=template.entitlement_code,
                    granted_by_source="access_key",
                    source_ref=key.key_code,
                    expires_at=expires_at,
                    notes=f"access_key_id={key.key_id}",
                ),
                now_utc=now,
            )
            granted.append(grant)
        updated_key = await self.repository.increment_access_key_redemption_count(key_id=key.key_id, now_utc=now)
        if updated_key and updated_key.redeemed_count >= updated_key.max_redemptions:
            await self.repository.update_access_key_status(key_id=key.key_id, status="exhausted", now_utc=now)

        redemption = await self.repository.create_access_key_redemption(
            key_id=key.key_id,
            user_id=user_id,
            redeemed_at=now,
            result_status="succeeded",
            result_reason_code="access_key_redeemed",
            created_grant_ids=tuple(item.grant_id for item in granted),
        )
        await self.repository.enqueue_event(
            event_type="access_key_redeemed",
            aggregate_type="access_key",
            aggregate_id=key.key_id,
            payload={
                "key_id": str(key.key_id),
                "user_id": user_id,
                "redemption_id": str(redemption.redemption_id),
                "granted_entitlements": [row.entitlement_code for row in granted],
            },
        )
        return AccessKeyRedemptionResult(
            ok=True,
            reason_code="access_key_redeemed",
            key_status="exhausted" if updated_key and updated_key.redeemed_count >= updated_key.max_redemptions else key.status,
            granted_entitlements=tuple(granted),
        )

    async def list_redemptions(self, *, key_code: str) -> list:
        key = await self.repository.get_access_key_by_code(key_code=key_code)
        if key is None:
            return []
        return await self.repository.list_access_key_redemptions(key_id=key.key_id)

    async def _failed_redemption(
        self,
        *,
        key_id: UUID | None,
        user_id: str,
        reason_code: str,
        key_status: str,
        now_utc: datetime,
    ) -> AccessKeyRedemptionResult:
        if key_id is not None:
            await self.repository.create_access_key_redemption(
                key_id=key_id,
                user_id=user_id,
                redeemed_at=now_utc,
                result_status="failed",
                result_reason_code=reason_code,
                created_grant_ids=(),
            )
            await self.repository.enqueue_event(
                event_type="access_key_redemption_failed",
                aggregate_type="access_key",
                aggregate_id=key_id,
                payload={
                    "key_id": str(key_id),
                    "user_id": user_id,
                    "reason_code": reason_code,
                },
            )
        return AccessKeyRedemptionResult(
            ok=False,
            reason_code=reason_code,
            key_status=key_status,
            granted_entitlements=(),
        )
