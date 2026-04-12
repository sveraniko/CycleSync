from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.application.access import AccessEvaluationService, AccessKeyCreate, AccessKeyEntitlementTemplate, AccessKeyService
from app.application.access.schemas import AccessKeyRedemptionView, AccessKeyView, EntitlementGrantCreate, EntitlementGrantView


@dataclass
class FakeAccessRepo:
    keys: dict[str, AccessKeyView] = field(default_factory=dict)
    grants: list[EntitlementGrantView] = field(default_factory=list)
    redemptions: list[AccessKeyRedemptionView] = field(default_factory=list)
    events: list[str] = field(default_factory=list)

    async def get_active_grant(self, *, user_id: str, entitlement_code: str):
        rows = [
            g
            for g in self.grants
            if g.user_id == user_id and g.entitlement_code == entitlement_code and g.grant_status == "active"
        ]
        rows.sort(key=lambda x: x.granted_at, reverse=True)
        return rows[0] if rows else None

    async def expire_grant(self, *, grant_id, now_utc):
        for idx, row in enumerate(self.grants):
            if row.grant_id == grant_id:
                self.grants[idx] = EntitlementGrantView(
                    grant_id=row.grant_id,
                    user_id=row.user_id,
                    entitlement_code=row.entitlement_code,
                    grant_status="expired",
                    granted_at=row.granted_at,
                    expires_at=row.expires_at,
                    granted_by_source=row.granted_by_source,
                    source_ref=row.source_ref,
                    revoked_at=now_utc,
                    notes=row.notes,
                )

    async def create_grant(self, request: EntitlementGrantCreate, *, now_utc):
        row = EntitlementGrantView(
            grant_id=uuid4(),
            user_id=request.user_id,
            entitlement_code=request.entitlement_code,
            grant_status="active",
            granted_at=now_utc,
            expires_at=request.expires_at,
            granted_by_source=request.granted_by_source,
            source_ref=request.source_ref,
            revoked_at=None,
            notes=request.notes,
        )
        self.grants.append(row)
        return row

    async def revoke_active_grants(self, *, user_id, entitlement_code, revoked_by_source, now_utc, reason, source_ref):
        _ = revoked_by_source, reason, source_ref
        count = 0
        for idx, row in enumerate(self.grants):
            if row.user_id == user_id and row.entitlement_code == entitlement_code and row.grant_status == "active":
                self.grants[idx] = EntitlementGrantView(
                    grant_id=row.grant_id,
                    user_id=row.user_id,
                    entitlement_code=row.entitlement_code,
                    grant_status="revoked",
                    granted_at=row.granted_at,
                    expires_at=row.expires_at,
                    granted_by_source=row.granted_by_source,
                    source_ref=row.source_ref,
                    revoked_at=now_utc,
                    notes=row.notes,
                )
                count += 1
        return count

    async def list_user_grants(self, *, user_id: str, only_active: bool = False):
        rows = [row for row in self.grants if row.user_id == user_id]
        if only_active:
            rows = [row for row in rows if row.grant_status == "active"]
        return rows

    async def enqueue_event(self, *, event_type: str, aggregate_type, aggregate_id, payload):
        _ = aggregate_type, aggregate_id, payload
        self.events.append(event_type)

    async def create_access_key(self, request, *, now_utc):
        row = AccessKeyView(
            key_id=uuid4(),
            key_code=request.key_code,
            status="active",
            max_redemptions=request.max_redemptions,
            redeemed_count=0,
            expires_at=request.expires_at,
            created_by_source=request.created_by_source,
            notes=request.notes,
            created_at=now_utc,
            updated_at=now_utc,
            entitlements=request.entitlements,
        )
        self.keys[row.key_code] = row
        return row

    async def get_access_key_by_code(self, *, key_code):
        return self.keys.get(key_code)

    async def update_access_key_status(self, *, key_id, status, now_utc):
        for code, row in self.keys.items():
            if row.key_id == key_id:
                updated = AccessKeyView(
                    key_id=row.key_id,
                    key_code=row.key_code,
                    status=status,
                    max_redemptions=row.max_redemptions,
                    redeemed_count=row.redeemed_count,
                    expires_at=row.expires_at,
                    created_by_source=row.created_by_source,
                    notes=row.notes,
                    created_at=row.created_at,
                    updated_at=now_utc,
                    entitlements=row.entitlements,
                )
                self.keys[code] = updated
                return updated
        return None

    async def increment_access_key_redemption_count(self, *, key_id, now_utc):
        for code, row in self.keys.items():
            if row.key_id == key_id:
                updated = AccessKeyView(
                    key_id=row.key_id,
                    key_code=row.key_code,
                    status=row.status,
                    max_redemptions=row.max_redemptions,
                    redeemed_count=row.redeemed_count + 1,
                    expires_at=row.expires_at,
                    created_by_source=row.created_by_source,
                    notes=row.notes,
                    created_at=row.created_at,
                    updated_at=now_utc,
                    entitlements=row.entitlements,
                )
                self.keys[code] = updated
                return updated
        return None

    async def list_key_entitlements(self, *, key_id):
        for row in self.keys.values():
            if row.key_id == key_id:
                return row.entitlements
        return ()

    async def find_successful_redemption(self, *, key_id, user_id):
        for row in self.redemptions:
            if row.access_key_id == key_id and row.user_id == user_id and row.result_status == "succeeded":
                return row
        return None

    async def create_access_key_redemption(self, *, key_id, user_id, redeemed_at, result_status, result_reason_code, created_grant_ids):
        row = AccessKeyRedemptionView(
            redemption_id=uuid4(),
            access_key_id=key_id,
            user_id=user_id,
            redeemed_at=redeemed_at,
            result_status=result_status,
            result_reason_code=result_reason_code,
            created_grant_ids=created_grant_ids,
        )
        self.redemptions.append(row)
        return row

    async def list_access_key_redemptions(self, *, key_id):
        return [row for row in self.redemptions if row.access_key_id == key_id]


def _build_service() -> tuple[FakeAccessRepo, AccessKeyService, AccessEvaluationService]:
    repo = FakeAccessRepo()
    evaluator = AccessEvaluationService(repo)
    return repo, AccessKeyService(repository=repo, evaluator=evaluator), evaluator


def test_key_creation_and_redemption_success() -> None:
    repo, service, _ = _build_service()
    now = datetime(2026, 4, 12, tzinfo=timezone.utc)

    import asyncio

    key = asyncio.run(
        service.create_key(
            AccessKeyCreate(
                key_code="W8-PR2-KEY-001",
                max_redemptions=2,
                expires_at=now + timedelta(days=2),
                created_by_source="ops",
                entitlements=(AccessKeyEntitlementTemplate(entitlement_code="reminders_access", grant_duration_days=30),),
            ),
            now_utc=now,
        )
    )
    result = asyncio.run(service.redeem_key(user_id="tg:100", key_code=key.key_code, now_utc=now))

    assert result.ok is True
    assert result.granted_entitlements[0].entitlement_code == "reminders_access"
    assert repo.keys[key.key_code].redeemed_count == 1
    assert "access_key_created" in repo.events
    assert "access_key_redeemed" in repo.events


def test_redemption_creates_entitlement_grants_and_is_visible_to_evaluator() -> None:
    _, service, evaluator = _build_service()
    now = datetime(2026, 4, 12, tzinfo=timezone.utc)

    import asyncio

    asyncio.run(
        service.create_key(
            AccessKeyCreate(
                key_code="W8-PR2-KEY-002",
                max_redemptions=1,
                expires_at=now + timedelta(days=1),
                created_by_source="ops",
                entitlements=(AccessKeyEntitlementTemplate(entitlement_code="ai_triage_access"),),
            ),
            now_utc=now,
        )
    )
    asyncio.run(service.redeem_key(user_id="tg:101", key_code="W8-PR2-KEY-002", now_utc=now))
    decision = asyncio.run(evaluator.evaluate(user_id="tg:101", entitlement_code="ai_triage_access", now_utc=now))

    assert decision.allowed is True
    assert decision.reason_code == "entitlement_active"


def test_expired_key_denial() -> None:
    _, service, _ = _build_service()
    now = datetime(2026, 4, 12, tzinfo=timezone.utc)

    import asyncio

    asyncio.run(
        service.create_key(
            AccessKeyCreate(
                key_code="W8-PR2-KEY-003",
                max_redemptions=1,
                expires_at=now + timedelta(hours=1),
                created_by_source="ops",
                entitlements=(AccessKeyEntitlementTemplate(entitlement_code="bot_access"),),
            ),
            now_utc=now,
        )
    )
    denied = asyncio.run(service.redeem_key(user_id="tg:102", key_code="W8-PR2-KEY-003", now_utc=now + timedelta(days=1)))
    assert denied.ok is False
    assert denied.reason_code == "access_key_expired"


def test_exhausted_key_denial() -> None:
    _, service, _ = _build_service()
    now = datetime(2026, 4, 12, tzinfo=timezone.utc)

    import asyncio

    asyncio.run(
        service.create_key(
            AccessKeyCreate(
                key_code="W8-PR2-KEY-004",
                max_redemptions=1,
                expires_at=None,
                created_by_source="ops",
                entitlements=(AccessKeyEntitlementTemplate(entitlement_code="bot_access"),),
            ),
            now_utc=now,
        )
    )
    first = asyncio.run(service.redeem_key(user_id="tg:103", key_code="W8-PR2-KEY-004", now_utc=now))
    second = asyncio.run(service.redeem_key(user_id="tg:104", key_code="W8-PR2-KEY-004", now_utc=now))
    assert first.ok is True
    assert second.ok is False
    assert second.reason_code == "access_key_exhausted"


def test_duplicate_redemption_policy_denial() -> None:
    _, service, _ = _build_service()
    now = datetime(2026, 4, 12, tzinfo=timezone.utc)

    import asyncio

    asyncio.run(
        service.create_key(
            AccessKeyCreate(
                key_code="W8-PR2-KEY-005",
                max_redemptions=2,
                expires_at=None,
                created_by_source="ops",
                entitlements=(AccessKeyEntitlementTemplate(entitlement_code="bot_access"),),
            ),
            now_utc=now,
        )
    )
    first = asyncio.run(service.redeem_key(user_id="tg:105", key_code="W8-PR2-KEY-005", now_utc=now))
    second = asyncio.run(service.redeem_key(user_id="tg:105", key_code="W8-PR2-KEY-005", now_utc=now))
    assert first.ok is True
    assert second.ok is False
    assert second.reason_code == "access_key_already_redeemed_by_user"
