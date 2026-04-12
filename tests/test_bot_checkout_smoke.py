from uuid import uuid4

from app.bots.handlers.checkout import _render_checkout, build_checkout_actions


class _State:
    def __init__(self):
        self.checkout = type(
            "Checkout",
            (),
            {
                "checkout_id": uuid4(),
                "checkout_status": "created",
                "subtotal_amount": 1500,
                "discount_amount": 0,
                "total_amount": 1500,
                "currency": "USD",
                "settlement_mode": "internal",
            },
        )
        self.items = (type("Item", (), {"title": "Specialist consult access", "qty": 1, "unit_amount": 1500, "line_total": 1500}),)


def test_checkout_actions_smoke() -> None:
    cid = uuid4()
    keyboard = build_checkout_actions(cid)
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert f"checkout:coupon:ask:{cid}" in callbacks
    assert f"checkout:gift:{cid}" in callbacks
    assert f"checkout:free:{cid}" in callbacks
    assert f"checkout:status:{cid}" in callbacks


def test_checkout_render_smoke() -> None:
    text = _render_checkout(_State())
    assert "Checkout" in text
    assert "status=created" in text
    assert "discount=0" in text
    assert "Specialist consult access" in text


def test_checkout_render_fulfillment_confirmation_smoke() -> None:
    state = _State()
    state.fulfillment = type(
        "Fulfillment",
        (),
        {
            "fulfillment_status": "succeeded",
            "fulfilled_at": "2026-04-12T00:00:00+00:00",
            "result_payload": {
                "grants": [
                    {"offer_code": "expert_case_access", "entitlement_code": "expert_case_access", "expires_at": None}
                ]
            },
        },
    )
    text = _render_checkout(state)
    assert "Fulfillment" in text
    assert "Unlocked" in text
