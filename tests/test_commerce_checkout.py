from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncio
import pytest

from app.application.commerce.providers import FreePaymentProvider, PaymentProviderRegistry
from app.application.commerce.schemas import CheckoutCreate, CheckoutItemCreate, CouponCreate
from app.application.commerce.service import CheckoutService, CommerceError


class FakeCommerceRepository:
    def __init__(self) -> None:
        self.checkouts = {}
        self.items = {}
        self.attempts = {}
        self.coupons = {}
        self.redemptions = []
        self.events = []

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

    async def add_checkout_items(self, *, checkout_id, items, now_utc):
        data = []
        subtotal = 0
        for item in items:
            line_total = item.qty * item.unit_amount
            subtotal += line_total
            data.append(type("Item", (), {"checkout_item_id": uuid4(), "checkout_id": checkout_id, "item_code": item.item_code, "title": item.title, "qty": item.qty, "unit_amount": item.unit_amount, "line_total": line_total}))
        self.items[checkout_id] = data
        self.checkouts[checkout_id].subtotal_amount = subtotal
        self.checkouts[checkout_id].total_amount = subtotal
        return tuple(data)

    async def get_checkout(self, *, checkout_id):
        c = self.checkouts.get(checkout_id)
        if not c:
            return None
        return type("State", (), {"checkout": c, "items": tuple(self.items[checkout_id]), "attempts": tuple(self.attempts[checkout_id])})

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

    async def get_diagnostics(self, *, commerce_mode, provider_summary):
        completed = sum(1 for c in self.checkouts.values() if c.checkout_status == "completed")
        failed = sum(1 for c in self.checkouts.values() if c.checkout_status == "failed")
        pending = sum(1 for c in self.checkouts.values() if c.checkout_status in {"created", "awaiting_payment"})
        free_settlements = sum(1 for rows in self.attempts.values() for row in rows if row.provider_code == "free" and row.attempt_status == "succeeded")
        active_coupons = sum(1 for c in self.coupons.values() if c.status == "active")
        exhausted_coupons = sum(1 for c in self.coupons.values() if c.status == "exhausted")
        coupon_redemptions = sum(1 for r in self.redemptions if r.result_status == "applied")
        coupon_free_settlements = 0
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
        })

    async def enqueue_event(self, *, event_type, aggregate_type, aggregate_id, payload):
        self.events.append(event_type)


def _service(repo: FakeCommerceRepository, mode: str = "test") -> CheckoutService:
    return CheckoutService(repo, PaymentProviderRegistry({"free": FreePaymentProvider()}, ("manual_card", "free")), mode)


def _create_checkout(repo: FakeCommerceRepository, *, user_id: str = "tg:1", amount: int = 100) -> object:
    service = _service(repo)
    return asyncio.run(service.create_checkout(
        user_id=user_id,
        currency="USD",
        settlement_mode="internal",
        items=(CheckoutItemCreate(item_code="triage_access", title="Triage", qty=1, unit_amount=amount),),
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


def test_percent_coupon_application() -> None:
    repo = FakeCommerceRepository()
    service = _service(repo)
    checkout = _create_checkout(repo, amount=200)
    _create_coupon(service, code="HALF", discount_type="percent", discount_value=50)
    result = asyncio.run(service.apply_coupon_to_checkout(checkout_id=checkout.checkout.checkout_id, user_id="tg:1", coupon_code="half"))
    assert result.status == "applied"
    assert result.checkout.checkout.discount_amount == 100
    assert result.checkout.checkout.total_amount == 100


def test_fixed_coupon_application() -> None:
    repo = FakeCommerceRepository()
    service = _service(repo)
    checkout = _create_checkout(repo, amount=300)
    _create_coupon(service, code="MINUS75", discount_type="fixed", discount_value=75, currency="USD")
    result = asyncio.run(service.apply_coupon_to_checkout(checkout_id=checkout.checkout.checkout_id, user_id="tg:1", coupon_code="MINUS75"))
    assert result.status == "applied"
    assert result.checkout.checkout.total_amount == 225


def test_total_does_not_go_below_zero() -> None:
    repo = FakeCommerceRepository()
    service = _service(repo)
    checkout = _create_checkout(repo, amount=80)
    _create_coupon(service, code="BIG", discount_type="fixed", discount_value=1000, currency="USD")
    result = asyncio.run(service.apply_coupon_to_checkout(checkout_id=checkout.checkout.checkout_id, user_id="tg:1", coupon_code="BIG"))
    assert result.checkout.checkout.discount_amount == 80
    assert result.checkout.checkout.total_amount == 0


def test_expired_coupon_denial() -> None:
    repo = FakeCommerceRepository()
    service = _service(repo)
    checkout = _create_checkout(repo, amount=100)
    now = datetime.now(timezone.utc)
    _create_coupon(service, code="OLD", discount_type="percent", discount_value=10, valid_to=now - timedelta(days=1))
    result = asyncio.run(service.apply_coupon_to_checkout(checkout_id=checkout.checkout.checkout_id, user_id="tg:1", coupon_code="OLD", now_utc=now))
    assert result.status == "denied"
    assert result.reason_code == "coupon_expired"


def test_exhausted_coupon_denial() -> None:
    repo = FakeCommerceRepository()
    service = _service(repo)
    checkout_a = _create_checkout(repo, user_id="tg:1", amount=100)
    checkout_b = _create_checkout(repo, user_id="tg:2", amount=100)
    _create_coupon(service, code="ONCE", discount_type="percent", discount_value=20, max_redemptions_total=1)
    first = asyncio.run(service.apply_coupon_to_checkout(checkout_id=checkout_a.checkout.checkout_id, user_id="tg:1", coupon_code="ONCE"))
    second = asyncio.run(service.apply_coupon_to_checkout(checkout_id=checkout_b.checkout.checkout_id, user_id="tg:2", coupon_code="ONCE"))
    assert first.status == "applied"
    assert second.status == "denied"
    assert second.reason_code == "coupon_exhausted"


def test_per_user_limit_denial() -> None:
    repo = FakeCommerceRepository()
    service = _service(repo)
    checkout_a = _create_checkout(repo, user_id="tg:1", amount=100)
    checkout_b = _create_checkout(repo, user_id="tg:1", amount=100)
    _create_coupon(service, code="USER1", discount_type="fixed", discount_value=10, currency="USD", max_redemptions_per_user=1)
    first = asyncio.run(service.apply_coupon_to_checkout(checkout_id=checkout_a.checkout.checkout_id, user_id="tg:1", coupon_code="USER1"))
    second = asyncio.run(service.apply_coupon_to_checkout(checkout_id=checkout_b.checkout.checkout_id, user_id="tg:1", coupon_code="USER1"))
    assert first.status == "applied"
    assert second.status == "denied"
    assert second.reason_code == "per_user_limit_reached"


def test_100_percent_coupon_to_free_settlement_path() -> None:
    repo = FakeCommerceRepository()
    service = _service(repo)
    checkout = _create_checkout(repo, amount=100)
    _create_coupon(service, code="GIFT100", discount_type="percent", discount_value=100)
    applied = asyncio.run(service.apply_coupon_to_checkout(checkout_id=checkout.checkout.checkout_id, user_id="tg:1", coupon_code="GIFT100"))
    assert applied.checkout.checkout.total_amount == 0
    settled = asyncio.run(service.settle_free_checkout(checkout_id=checkout.checkout.checkout_id, reason_code="gift_coupon"))
    assert settled.checkout.checkout_status == "completed"
    assert "checkout_completed_free" in repo.events


def test_checkout_creation_and_attempt_persistence() -> None:
    repo = FakeCommerceRepository()
    service = _service(repo)
    created = _create_checkout(repo)
    assert created.checkout.total_amount == 100
    asyncio.run(service.initiate_payment(checkout_id=created.checkout.checkout_id, provider_code="free"))
    assert len(repo.attempts[created.checkout.checkout_id]) == 1


def test_free_provider_success_completes_checkout() -> None:
    repo = FakeCommerceRepository()
    service = _service(repo)
    created = _create_checkout(repo, user_id="tg:2", amount=1200)
    settled = asyncio.run(service.settle_free_checkout(checkout_id=created.checkout.checkout_id, reason_code="dev_mode"))
    assert settled.checkout.checkout_status == "completed"
    assert "checkout_completed_free" in repo.events


def test_commerce_mode_enforcement() -> None:
    repo = FakeCommerceRepository()
    service = _service(repo, mode="disabled")
    created = _create_checkout(repo, user_id="tg:3", amount=1)
    with pytest.raises(CommerceError):
        asyncio.run(service.initiate_payment(checkout_id=created.checkout.checkout_id, provider_code="free"))


def test_checkout_completion_state_and_diagnostics() -> None:
    repo = FakeCommerceRepository()
    service = _service(repo)
    created = _create_checkout(repo, user_id="tg:4", amount=9)
    asyncio.run(service.settle_free_checkout(checkout_id=created.checkout.checkout_id, reason_code="ops_test"))
    diag = asyncio.run(service.diagnostics())
    assert diag.commerce_mode == "test"
    assert "free" in diag.provider_summary
    assert diag.completed_checkouts == 1
