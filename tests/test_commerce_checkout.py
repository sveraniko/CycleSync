from datetime import datetime, timezone
from uuid import uuid4

import asyncio
import pytest

from app.application.commerce.providers import FreePaymentProvider, PaymentProviderRegistry
from app.application.commerce.schemas import CheckoutCreate, CheckoutItemCreate
from app.application.commerce.service import CheckoutService, CommerceError


class FakeCommerceRepository:
    def __init__(self) -> None:
        self.checkouts = {}
        self.items = {}
        self.attempts = {}
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
                    return row
        return None

    async def create_provider_session(self, *, checkout_id, provider_code, session_status, session_payload, now_utc):
        return type("Session", (), {"provider_session_id": uuid4(), "checkout_id": checkout_id, "provider_code": provider_code, "session_status": session_status, "session_payload": session_payload})

    async def get_diagnostics(self, *, commerce_mode, provider_summary):
        completed = sum(1 for c in self.checkouts.values() if c.checkout_status == "completed")
        failed = sum(1 for c in self.checkouts.values() if c.checkout_status == "failed")
        pending = sum(1 for c in self.checkouts.values() if c.checkout_status in {"created", "awaiting_payment"})
        free_settlements = sum(1 for rows in self.attempts.values() for row in rows if row.provider_code == "free" and row.attempt_status == "succeeded")
        return type("Diagnostics", (), {"commerce_mode": commerce_mode, "provider_summary": provider_summary, "pending_checkouts": pending, "completed_checkouts": completed, "failed_checkouts": failed, "free_settlements": free_settlements})

    async def enqueue_event(self, *, event_type, aggregate_type, aggregate_id, payload):
        self.events.append(event_type)


def test_checkout_creation_and_attempt_persistence() -> None:
    repo = FakeCommerceRepository()
    service = CheckoutService(repo, PaymentProviderRegistry({"free": FreePaymentProvider()}, ("free",)), "test")
    created = asyncio.run(service.create_checkout(
        user_id="tg:1",
        currency="USD",
        settlement_mode="internal",
        items=(CheckoutItemCreate(item_code="triage_access", title="Triage", qty=1, unit_amount=100),),
    ))
    assert created.checkout.total_amount == 100
    asyncio.run(service.initiate_payment(checkout_id=created.checkout.checkout_id, provider_code="free"))
    assert len(repo.attempts[created.checkout.checkout_id]) == 1


def test_free_provider_success_completes_checkout() -> None:
    repo = FakeCommerceRepository()
    service = CheckoutService(repo, PaymentProviderRegistry({"free": FreePaymentProvider()}, ("free",)), "test")
    created = asyncio.run(service.create_checkout(
        user_id="tg:2",
        currency="USD",
        settlement_mode="internal",
        items=(CheckoutItemCreate(item_code="expert_case", title="Expert", qty=1, unit_amount=1200),),
    ))
    settled = asyncio.run(service.settle_free_checkout(checkout_id=created.checkout.checkout_id, reason_code="dev_mode"))
    assert settled.checkout.checkout_status == "completed"
    assert "checkout_completed_free" in repo.events


def test_commerce_mode_enforcement() -> None:
    repo = FakeCommerceRepository()
    service = CheckoutService(repo, PaymentProviderRegistry({"free": FreePaymentProvider()}, ("free",)), "disabled")
    created = asyncio.run(service.create_checkout(
        user_id="tg:3",
        currency="USD",
        settlement_mode="internal",
        items=(CheckoutItemCreate(item_code="x", title="X", qty=1, unit_amount=1),),
    ))
    with pytest.raises(CommerceError):
        asyncio.run(service.initiate_payment(checkout_id=created.checkout.checkout_id, provider_code="free"))


def test_checkout_completion_state_and_diagnostics() -> None:
    repo = FakeCommerceRepository()
    registry = PaymentProviderRegistry({"free": FreePaymentProvider()}, ("manual_card", "free"))
    service = CheckoutService(repo, registry, "test")
    created = asyncio.run(service.create_checkout(
        user_id="tg:4",
        currency="USD",
        settlement_mode="internal",
        items=(CheckoutItemCreate(item_code="x", title="X", qty=1, unit_amount=9),),
    ))
    asyncio.run(service.settle_free_checkout(checkout_id=created.checkout.checkout_id, reason_code="ops_test"))
    diag = asyncio.run(service.diagnostics())
    assert diag.commerce_mode == "test"
    assert "free" in diag.provider_summary
    assert diag.completed_checkouts == 1
