from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.application.access.schemas import EntitlementGrantCreate, EntitlementGrantView
from app.application.access.service import AccessEvaluationService


@dataclass
class FakeAccessRepo:
    grants: list[EntitlementGrantView] = field(default_factory=list)
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
        for idx, g in enumerate(self.grants):
            if g.grant_id == grant_id:
                self.grants[idx] = EntitlementGrantView(
                    grant_id=g.grant_id,
                    user_id=g.user_id,
                    entitlement_code=g.entitlement_code,
                    grant_status="expired",
                    granted_at=g.granted_at,
                    expires_at=g.expires_at,
                    granted_by_source=g.granted_by_source,
                    source_ref=g.source_ref,
                    revoked_at=now_utc,
                    notes=g.notes,
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
        out = []
        for g in self.grants:
            if g.user_id == user_id and g.entitlement_code == entitlement_code and g.grant_status == "active":
                out.append(
                    EntitlementGrantView(
                        grant_id=g.grant_id,
                        user_id=g.user_id,
                        entitlement_code=g.entitlement_code,
                        grant_status="revoked",
                        granted_at=g.granted_at,
                        expires_at=g.expires_at,
                        granted_by_source=g.granted_by_source,
                        source_ref=g.source_ref,
                        revoked_at=now_utc,
                        notes=g.notes,
                    )
                )
                count += 1
            else:
                out.append(g)
        self.grants = out
        return count

    async def list_user_grants(self, *, user_id: str, only_active: bool = False):
        rows = [g for g in self.grants if g.user_id == user_id]
        if only_active:
            rows = [g for g in rows if g.grant_status == "active"]
        return rows

    async def enqueue_event(self, *, event_type: str, aggregate_type, aggregate_id, payload):
        _ = aggregate_type, aggregate_id, payload
        self.events.append(event_type)


def test_grant_creation_and_list() -> None:
    repo = FakeAccessRepo()
    service = AccessEvaluationService(repo)
    now = datetime(2026, 4, 12, tzinfo=timezone.utc)

    import asyncio

    asyncio.run(
        service.grant(
            EntitlementGrantCreate(
                user_id="tg:1",
                entitlement_code="ai_triage_access",
                granted_by_source="manual",
            ),
            now_utc=now,
        )
    )
    grants = asyncio.run(service.list_user_grants(user_id="tg:1", only_active=True))
    assert len(grants) == 1
    assert "entitlement_granted" in repo.events


def test_grant_expiration_changes_decision() -> None:
    repo = FakeAccessRepo()
    service = AccessEvaluationService(repo)
    now = datetime(2026, 4, 12, tzinfo=timezone.utc)

    import asyncio

    asyncio.run(
        service.grant(
            EntitlementGrantCreate(
                user_id="tg:1",
                entitlement_code="ai_triage_access",
                granted_by_source="manual",
                expires_at=now - timedelta(minutes=1),
            ),
            now_utc=now - timedelta(hours=1),
        )
    )
    decision = asyncio.run(service.evaluate(user_id="tg:1", entitlement_code="ai_triage_access", now_utc=now))
    assert decision.allowed is False
    assert decision.reason_code == "entitlement_expired"
    assert "entitlement_expired" in repo.events


def test_revoke_changes_decision_to_denied() -> None:
    repo = FakeAccessRepo()
    service = AccessEvaluationService(repo)

    import asyncio

    asyncio.run(
        service.grant(
            EntitlementGrantCreate(
                user_id="tg:1",
                entitlement_code="expert_case_access",
                granted_by_source="manual",
            )
        )
    )
    revoked = asyncio.run(
        service.revoke(
            user_id="tg:1",
            entitlement_code="expert_case_access",
            revoked_by_source="manual",
            reason="ops_request",
        )
    )
    decision = asyncio.run(service.evaluate(user_id="tg:1", entitlement_code="expert_case_access"))
    assert revoked == 1
    assert decision.allowed is False
    assert decision.reason_code == "entitlement_absent"
    assert "entitlement_revoked" in repo.events


def test_evaluation_allowed_and_denied_paths() -> None:
    repo = FakeAccessRepo()
    service = AccessEvaluationService(repo)

    import asyncio

    denied = asyncio.run(service.evaluate(user_id="tg:2", entitlement_code="reminders_access"))
    assert denied.allowed is False

    asyncio.run(
        service.grant(
            EntitlementGrantCreate(
                user_id="tg:2",
                entitlement_code="reminders_access",
                granted_by_source="dev_seed",
            )
        )
    )
    allowed = asyncio.run(service.evaluate(user_id="tg:2", entitlement_code="reminders_access"))
    assert allowed.allowed is True
