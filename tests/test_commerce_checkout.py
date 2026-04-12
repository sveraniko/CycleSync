from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncio
import pytest

from app.application.access import AccessEvaluationService
from app.application.commerce.fulfillment import CheckoutFulfillmentService
from app.application.commerce.providers import FreePaymentProvider, PaymentProviderRegistry, StarsPaymentProvider
from app.application.commerce.schemas import CheckoutCreate, CheckoutItemCreate, CouponCreate
from app.application.commerce.service import CheckoutService, CommerceError


class FakeAccessRepository:
    def __init__(self) -> None:
        self.grants = []
        self.events = []

    async def get_active_grant(self, *, user_id, entitlement_code):
        for row in reversed(self.grants):
            if row.user_id == user_id and row.entitlement_code == entitlement_code and row.grant_status == "active":
                return row
        return None

    async def expire_grant(self, *, grant_id, now_utc):
        return None

    async def create_grant(self, request, *, now_utc):
        for row in self.grants:
            if row.user_id == request.user_id and row.entitlement_code == request.entitlement_code and row.granted_by_source == request.granted_by_source and row.source_ref == request.source_ref and row.grant_status == "active":
                return row
        row = type("Grant", (), {
            "grant_id": uuid4(),
            "user_id": request.user_id,
            "entitlement_code": request.entitlement_code,
            "grant_status": "active",
            "granted_at": now_utc,
            "expires_at": request.expires_at,
            "granted_by_source": request.granted_by_source,
            "source_ref": request.source_ref,
            "revoked_at": None,
            "notes": request.notes,
        })
        self.grants.append(row)
        return row

    async def revoke_active_grants(self, **kwargs):
        return 0

    async def list_user_grants(self, *, user_id, only_active=False):
        return [g for g in self.grants if g.user_id == user_id]

    async def enqueue_event(self, *, event_type, aggregate_type, aggregate_id, payload):
        self.events.append(event_type)


class FakeCommerceRepository:
    def __init__(self) -> None:
        self.checkouts = {}
        self.items = {}
        self.attempts = {}
        self.coupons = {}
        self.redemptions = []
        self.events = []
        self.fulfillments = {}
        now = datetime.now(timezone.utc)
        self.offers = {
            "expert_case_access": type("Offer", (), {"offer_id": uuid4(), "offer_code": "expert_case_access", "title": "Specialist consult access", "status": "active", "currency": "USD", "default_amount": 1500, "description": None, "created_at": now, "updated_at": now}),
            "triage_access": type("Offer", (), {"offer_id": uuid4(), "offer_code": "triage_access", "title": "Triage", "status": "active", "currency": "USD", "default_amount": 100, "description": None, "created_at": now, "updated_at": now}),
            "broken_offer": type("Offer", (), {"offer_id": uuid4(), "offer_code": "broken_offer", "title": "Broken", "status": "active", "currency": "USD", "default_amount": 50, "description": None, "created_at": now, "updated_at": now}),
        }
        self.offer_entitlements = {
            self.offers["expert_case_access"].offer_id: [type("OE", (), {"offer_id": self.offers["expert_case_access"].offer_id, "entitlement_code": "expert_case_access", "grant_duration_days": None, "qty": 1})],
            self.offers["triage_access"].offer_id: [type("OE", (), {"offer_id": self.offers["triage_access"].offer_id, "entitlement_code": "ai_triage_access", "grant_duration_days": 30, "qty": 1})],
        }

    async def create_checkout(self, request: CheckoutCreate, *, now_utc: datetime):
        cid = uuid4()
        row = type("Checkout", (), {
            "checkout_id": cid,
            "user_id": request.user_id,
            "checkout_status": "created",
            "currency": request.currency,
            "subtotal_amount": 0,
            "discount_amount": 0,
            "total_amount": 0,
            "settlement_mode": request.settlement_mode,
            "source_context": request.source_context,
            "created_at": now_utc,
            "updated_at": now_utc,
            "completed_at": None,
        })
        self.checkouts[cid] = row
        self.items[cid] = []
        self.attempts[cid] = []
        return row

    async def get_sellable_offer_by_code(self, *, offer_code):
        return self.offers.get(offer_code)

    async def list_sellable_offers(self, *, only_active=True):
        values = list(self.offers.values())
        if only_active:
            values = [o for o in values if o.status == "active"]
        return tuple(values)

    async def list_offer_entitlements(self, *, offer_ids):
        rows = []
        for oid in offer_ids:
            rows.extend(self.offer_entitlements.get(oid, []))
        return tuple(rows)

    async def add_checkout_items(self, *, checkout_id, items, now_utc):
        data = []
        subtotal = 0
        for item in items:
            offer = self.offers.get(item.offer_code)
            if offer is None:
                raise ValueError(f"offer_not_found_or_inactive:{item.offer_code}")
            line_total = item.qty * offer.default_amount
            subtotal += line_total
            data.append(type("Item", (), {"checkout_item_id": uuid4(), "checkout_id": checkout_id, "offer_id": offer.offer_id, "offer_code": offer.offer_code, "item_code": offer.offer_code, "title": offer.title, "qty": item.qty, "unit_amount": offer.default_amount, "line_total": line_total}))
        self.items[checkout_id] = data
        self.checkouts[checkout_id].subtotal_amount = subtotal
        self.checkouts[checkout_id].total_amount = subtotal
        return tuple(data)

    async def get_checkout(self, *, checkout_id):
        c = self.checkouts.get(checkout_id)
        if not c:
            return None
        return type("State", (), {"checkout": c, "items": tuple(self.items[checkout_id]), "attempts": tuple(self.attempts[checkout_id]), "fulfillment": self.fulfillments.get(checkout_id)})

    async def mark_checkout_status(self, *, checkout_id, checkout_status, now_utc, completed_at=None):
        c = self.checkouts[checkout_id]
        c.checkout_status = checkout_status
        c.updated_at = now_utc
        c.completed_at = completed_at
        return c

    async def update_checkout_amounts(self, *, checkout_id, discount_amount, total_amount, now_utc):
        c = self.checkouts[checkout_id]
        c.discount_amount = discount_amount
        c.total_amount = total_amount
        c.updated_at = now_utc
        return c

    async def create_coupon(self, request, *, now_utc):
        coupon_id = uuid4()
        coupon = type("Coupon", (), {
            "coupon_id": coupon_id,
            "code": request.code,
            "status": "active",
            "discount_type": request.discount_type,
            "discount_value": request.discount_value,
            "currency": request.currency,
            "valid_from": request.valid_from,
            "valid_to": request.valid_to,
            "max_redemptions_total": request.max_redemptions_total,
            "max_redemptions_per_user": request.max_redemptions_per_user,
            "redeemed_count": 0,
            "notes": request.notes,
            "created_at": now_utc,
            "updated_at": now_utc,
        })
        self.coupons[request.code] = coupon
        return coupon

    async def get_coupon_by_code(self, *, code):
        return self.coupons.get(code)

    async def get_coupon(self, *, coupon_id):
        for coupon in self.coupons.values():
            if coupon.coupon_id == coupon_id:
                return coupon
        return None

    async def disable_coupon(self, *, coupon_id, now_utc):
        coupon = await self.get_coupon(coupon_id=coupon_id)
        if coupon is None:
            return None
        coupon.status = "disabled"
        coupon.updated_at = now_utc
        return coupon

    async def list_coupon_redemptions(self, *, coupon_id):
        rows = [row for row in self.redemptions if row.coupon_id == coupon_id]
        return tuple(rows)

    async def count_coupon_success_redemptions(self, *, coupon_id, user_id=None):
        rows = [row for row in self.redemptions if row.coupon_id == coupon_id and row.result_status == "applied"]
        if user_id is not None:
            rows = [row for row in rows if row.user_id == user_id]
        return len(rows)

    async def get_applied_coupon_redemption(self, *, checkout_id, coupon_id):
        for row in self.redemptions:
            if row.checkout_id == checkout_id and row.coupon_id == coupon_id and row.result_status == "applied":
                return row
        return None

    async def create_coupon_redemption(self, *, coupon_id, checkout_id, user_id, redeemed_at, result_status, result_reason_code, discount_amount, final_total_after_discount):
        row = type("Redemption", (), {
            "redemption_id": uuid4(),
            "coupon_id": coupon_id,
            "checkout_id": checkout_id,
            "user_id": user_id,
            "redeemed_at": redeemed_at,
            "result_status": result_status,
            "result_reason_code": result_reason_code,
            "discount_amount": discount_amount,
            "final_total_after_discount": final_total_after_discount,
        })
        self.redemptions.append(row)
        return row

    async def increment_coupon_redemption_count(self, *, coupon_id, now_utc):
        coupon = await self.get_coupon(coupon_id=coupon_id)
        if coupon is None:
            return None
        coupon.redeemed_count += 1
        coupon.updated_at = now_utc
        if coupon.max_redemptions_total is not None and coupon.redeemed_count >= coupon.max_redemptions_total:
            coupon.status = "exhausted"
        return coupon

    async def create_payment_attempt(self, *, checkout_id, provider_code, requested_amount, attempt_status, now_utc, provider_reference=None, error_code=None, error_message=None):
        row = type("Attempt", (), {"attempt_id": uuid4(), "checkout_id": checkout_id, "provider_code": provider_code, "attempt_status": attempt_status, "requested_amount": requested_amount, "provider_reference": provider_reference, "error_code": error_code, "error_message": error_message, "created_at": now_utc, "updated_at": now_utc})
        self.attempts[checkout_id].append(row)
        return row

    async def update_payment_attempt(self, *, attempt_id, attempt_status, now_utc, provider_reference=None, error_code=None, error_message=None):
        for rows in self.attempts.values():
            for row in rows:
                if row.attempt_id == attempt_id:
                    row.attempt_status = attempt_status
                    row.provider_reference = provider_reference
                    row.error_code = error_code
                    row.error_message = error_message
                    row.updated_at = now_utc
                    return row
        return None

    async def create_provider_session(self, *, checkout_id, provider_code, session_status, session_payload, now_utc):
        return type("Session", (), {"provider_session_id": uuid4(), "checkout_id": checkout_id, "provider_code": provider_code, "session_status": session_status, "session_payload": session_payload})

    async def get_checkout_fulfillment(self, *, checkout_id):
        return self.fulfillments.get(checkout_id)

    async def upsert_checkout_fulfillment(self, *, checkout_id, fulfillment_status, now_utc, fulfilled_at=None, result_payload=None, error_code=None, error_message=None):
        current = self.fulfillments.get(checkout_id)
        fid = current.fulfillment_id if current else uuid4()
        row = type("Fulfillment", (), {
            "fulfillment_id": fid,
            "checkout_id": checkout_id,
            "fulfillment_status": fulfillment_status,
            "fulfilled_at": fulfilled_at,
            "result_payload": result_payload,
            "error_code": error_code,
            "error_message": error_message,
            "created_at": now_utc,
            "updated_at": now_utc,
        })
        self.fulfillments[checkout_id] = row
        return row

    async def get_diagnostics(self, *, commerce_mode, provider_summary):
        completed = sum(1 for c in self.checkouts.values() if c.checkout_status == "completed")
        failed = sum(1 for c in self.checkouts.values() if c.checkout_status == "failed")
        pending = sum(1 for c in self.checkouts.values() if c.checkout_status in {"created", "awaiting_payment"})
        free_settlements = sum(1 for rows in self.attempts.values() for row in rows if row.provider_code == "free" and row.attempt_status == "succeeded")
        active_coupons = sum(1 for c in self.coupons.values() if c.status == "active")
        exhausted_coupons = sum(1 for c in self.coupons.values() if c.status == "exhausted")
        coupon_redemptions = sum(1 for r in self.redemptions if r.result_status == "applied")
        coupon_free_settlements = 0
        provider_attempts = {}
        provider_succeeded = {}
        provider_failed = {}
        for rows in self.attempts.values():
            for row in rows:
                provider_attempts[row.provider_code] = provider_attempts.get(row.provider_code, 0) + 1
                if row.attempt_status == "succeeded":
                    provider_succeeded[row.provider_code] = provider_succeeded.get(row.provider_code, 0) + 1
                if row.attempt_status in {"failed", "cancelled", "expired"}:
                    provider_failed[row.provider_code] = provider_failed.get(row.provider_code, 0) + 1
        return type("Diagnostics", (), {
            "commerce_mode": commerce_mode,
            "provider_summary": provider_summary,
            "pending_checkouts": pending,
            "completed_checkouts": completed,
            "failed_checkouts": failed,
            "free_settlements": free_settlements,
            "active_coupons": active_coupons,
            "exhausted_coupons": exhausted_coupons,
            "coupon_redemptions": coupon_redemptions,
            "coupon_free_settlements": coupon_free_settlements,
            "provider_attempts": provider_attempts,
            "provider_succeeded": provider_succeeded,
            "provider_failed": provider_failed,
        })

    async def enqueue_event(self, *, event_type, aggregate_type, aggregate_id, payload):
        self.events.append(event_type)


def _service(repo: FakeCommerceRepository, mode: str = "test") -> tuple[CheckoutService, FakeAccessRepository]:
    access_repo = FakeAccessRepository()
    access_service = AccessEvaluationService(access_repo)
    fulfillment_service = CheckoutFulfillmentService(repository=repo, access_service=access_service)
    checkout_service = CheckoutService(repo, PaymentProviderRegistry({"free": FreePaymentProvider()}, ("manual_card", "free")), mode, fulfillment_service=fulfillment_service)
    return checkout_service, access_repo


def _service_with_stars(repo: FakeCommerceRepository, mode: str = "live") -> tuple[CheckoutService, FakeAccessRepository]:
    access_repo = FakeAccessRepository()
    access_service = AccessEvaluationService(access_repo)
    fulfillment_service = CheckoutFulfillmentService(repository=repo, access_service=access_service)
    registry = PaymentProviderRegistry(
        {"free": FreePaymentProvider(), "stars": StarsPaymentProvider(bot_username="cyclesync_bot")},
        ("stars", "free"),
    )
    checkout_service = CheckoutService(repo, registry, mode, fulfillment_service=fulfillment_service)
    return checkout_service, access_repo


def _create_checkout(repo: FakeCommerceRepository, service: CheckoutService, *, user_id: str = "tg:1", offer_code: str = "triage_access") -> object:
    return asyncio.run(service.create_checkout(
        user_id=user_id,
        currency="USD",
        settlement_mode="internal",
        items=(CheckoutItemCreate(offer_code=offer_code, qty=1),),
    ))


def _create_coupon(service: CheckoutService, *, code: str, discount_type: str, discount_value: int, **kwargs):
    return asyncio.run(service.create_coupon(CouponCreate(
        code=code,
        discount_type=discount_type,
        discount_value=discount_value,
        currency=kwargs.get("currency"),
        valid_from=kwargs.get("valid_from"),
        valid_to=kwargs.get("valid_to"),
        max_redemptions_total=kwargs.get("max_redemptions_total"),
        max_redemptions_per_user=kwargs.get("max_redemptions_per_user"),
        notes=kwargs.get("notes"),
    )))


def test_completed_checkout_triggers_fulfillment_success() -> None:
    repo = FakeCommerceRepository()
    service, _ = _service(repo)
    checkout = _create_checkout(repo, service)
    settled = asyncio.run(service.settle_free_checkout(checkout_id=checkout.checkout.checkout_id, reason_code="dev_mode"))
    assert settled.checkout.checkout_status == "completed"
    assert settled.fulfillment is not None
    assert settled.fulfillment.fulfillment_status == "succeeded"


def test_fulfillment_grants_entitlements() -> None:
    repo = FakeCommerceRepository()
    service, access_repo = _service(repo)
    checkout = _create_checkout(repo, service)
    asyncio.run(service.settle_free_checkout(checkout_id=checkout.checkout.checkout_id, reason_code="dev_mode"))
    assert any(g.entitlement_code == "ai_triage_access" for g in access_repo.grants)


def test_fulfillment_is_idempotent() -> None:
    repo = FakeCommerceRepository()
    service, access_repo = _service(repo)
    checkout = _create_checkout(repo, service)
    asyncio.run(service.settle_free_checkout(checkout_id=checkout.checkout.checkout_id, reason_code="dev_mode"))
    first = len(access_repo.grants)
    asyncio.run(service.fulfillment_service.fulfill_checkout(checkout_id=checkout.checkout.checkout_id))
    assert len(access_repo.grants) == first


def test_free_settlement_and_gift_settlement_use_same_fulfillment_path() -> None:
    repo = FakeCommerceRepository()
    service, _ = _service(repo)
    free_checkout = _create_checkout(repo, service, user_id="tg:free")
    asyncio.run(service.settle_free_checkout(checkout_id=free_checkout.checkout.checkout_id, reason_code="dev_mode"))

    gift_checkout = _create_checkout(repo, service, user_id="tg:gift")
    _create_coupon(service, code="GIFT100", discount_type="percent", discount_value=100)
    asyncio.run(service.apply_coupon_to_checkout(checkout_id=gift_checkout.checkout.checkout_id, user_id="tg:gift", coupon_code="GIFT100"))
    gift_state = asyncio.run(service.settle_free_checkout(checkout_id=gift_checkout.checkout.checkout_id, reason_code="gift_coupon"))

    assert gift_state.fulfillment is not None
    assert "checkout_fulfillment_succeeded" in repo.events


def test_malformed_offer_mapping_fails_fulfillment() -> None:
    repo = FakeCommerceRepository()
    service, _ = _service(repo)
    checkout = _create_checkout(repo, service, offer_code="broken_offer")
    with pytest.raises(ValueError):
        asyncio.run(service.settle_free_checkout(checkout_id=checkout.checkout.checkout_id, reason_code="dev_mode"))


def test_checkout_creation_requires_known_offer() -> None:
    repo = FakeCommerceRepository()
    service, _ = _service(repo)
    with pytest.raises(CommerceError):
        asyncio.run(service.create_checkout(user_id="tg:1", currency="USD", settlement_mode="internal", items=(CheckoutItemCreate(offer_code="unknown_offer", qty=1),)))


def test_expired_coupon_denial() -> None:
    repo = FakeCommerceRepository()
    service, _ = _service(repo)
    checkout = _create_checkout(repo, service)
    now = datetime.now(timezone.utc)
    _create_coupon(service, code="OLD", discount_type="percent", discount_value=10, valid_to=now - timedelta(days=1))
    result = asyncio.run(service.apply_coupon_to_checkout(checkout_id=checkout.checkout.checkout_id, user_id="tg:1", coupon_code="OLD", now_utc=now))
    assert result.status == "denied"
    assert result.reason_code == "coupon_expired"


def test_stars_provider_init_happy_path_creates_session_and_pending_attempt() -> None:
    repo = FakeCommerceRepository()
    service, _ = _service_with_stars(repo)
    checkout = _create_checkout(repo, service)
    state = asyncio.run(service.initiate_payment(checkout_id=checkout.checkout.checkout_id, provider_code="stars"))
    assert state.checkout.checkout_status == "awaiting_payment"
    assert state.attempts[-1].attempt_status == "pending"
    assert "t.me/cyclesync_bot" in (state.attempts[-1].provider_reference or "")
    assert "payment_provider_session_created" in repo.events


def test_stars_success_flows_to_checkout_completion_and_fulfillment() -> None:
    repo = FakeCommerceRepository()
    service, _ = _service_with_stars(repo)
    checkout = _create_checkout(repo, service, user_id="tg:stars")
    asyncio.run(service.initiate_payment(checkout_id=checkout.checkout.checkout_id, provider_code="stars"))
    completed = asyncio.run(
        service.confirm_provider_payment(checkout_id=checkout.checkout.checkout_id, provider_code="stars", outcome="succeeded")
    )
    assert completed.checkout.checkout_status == "completed"
    assert completed.fulfillment is not None
    assert completed.fulfillment.fulfillment_status == "succeeded"


def test_stars_failure_marks_checkout_failed() -> None:
    repo = FakeCommerceRepository()
    service, _ = _service_with_stars(repo)
    checkout = _create_checkout(repo, service)
    asyncio.run(service.initiate_payment(checkout_id=checkout.checkout.checkout_id, provider_code="stars"))
    failed = asyncio.run(
        service.confirm_provider_payment(
            checkout_id=checkout.checkout.checkout_id,
            provider_code="stars",
            outcome="failed",
            metadata={"error_code": "declined"},
        )
    )
    assert failed.checkout.checkout_status == "failed"
    assert failed.attempts[-1].attempt_status == "failed"


def test_diagnostics_include_provider_counts() -> None:
    repo = FakeCommerceRepository()
    service, _ = _service_with_stars(repo)
    checkout = _create_checkout(repo, service)
    asyncio.run(service.initiate_payment(checkout_id=checkout.checkout.checkout_id, provider_code="stars"))
    asyncio.run(service.confirm_provider_payment(checkout_id=checkout.checkout.checkout_id, provider_code="stars", outcome="failed"))
    diagnostics = asyncio.run(service.diagnostics())
    assert diagnostics.provider_attempts.get("stars") == 1
    assert diagnostics.provider_failed.get("stars") == 1
