import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.bots.handlers.checkout import (
    _can_view_debug_user,
    _render_checkout,
    build_checkout_actions,
    coupon_submit,
    show_status,
)


class FakeFSMContext:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}
        self.state = None

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)

    async def set_data(self, data):
        self.data = dict(data)

    async def clear(self):
        self.data = {}
        self.state = None

    async def set_state(self, value):
        self.state = value


class FakeBot:
    def __init__(self) -> None:
        self.edits = []

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)
        return SimpleNamespace(message_id=kwargs["message_id"])


class FakeMessage:
    def __init__(self) -> None:
        self.bot = FakeBot()
        self.chat = SimpleNamespace(id=42)
        self.from_user = SimpleNamespace(id=100)
        self.message_id = 10
        self.text = ""
        self.answers = []

    async def answer(self, text, reply_markup=None, parse_mode=None):
        sent = FakeMessage()
        sent.message_id = 1000 + len(self.answers)
        self.answers.append(
            {"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode, "sent": sent}
        )
        return sent

    async def delete(self):
        return None


class FakeCallback:
    def __init__(self, checkout_id):
        self.message = FakeMessage()
        self.from_user = SimpleNamespace(id=100)
        self.data = f"checkout:status:{checkout_id}"
        self.answer_calls = []

    async def answer(self, text=None, show_alert=False):
        self.answer_calls.append({"text": text, "show_alert": show_alert})


def _checkout_state(checkout_id=None, status: str = "created", total: int = 1500):
    checkout_id = checkout_id or uuid4()
    state = SimpleNamespace(
        checkout=SimpleNamespace(
            checkout_id=checkout_id,
            checkout_status=status,
            subtotal_amount=1500,
            discount_amount=0,
            total_amount=total,
            currency="USD",
            settlement_mode="internal",
        ),
        items=(SimpleNamespace(title="Specialist consult access", qty=1, unit_amount=1500, line_total=1500),),
        attempts=(),
        fulfillment=None,
    )
    return state


def test_checkout_panel_rendering_smoke() -> None:
    text = _render_checkout(_checkout_state())
    assert "🧾 Checkout" in text
    assert "Товар: Specialist consult access" in text
    assert "Сумма:" in text


def test_debug_buttons_hidden_for_regular_user() -> None:
    keyboard = build_checkout_actions(uuid4(), show_debug_actions=False)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert not any("checkout:free:" in value for value in callbacks)
    assert not any("checkout:gift:" in value for value in callbacks)
    assert not any("checkout:provider:fail:" in value for value in callbacks)


def test_debug_buttons_visible_for_admin_debug_mode() -> None:
    keyboard = build_checkout_actions(uuid4(), show_debug_actions=True)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert any("checkout:free:" in value for value in callbacks)
    assert any("checkout:gift:" in value for value in callbacks)
    assert any("checkout:provider:fail:" in value for value in callbacks)


def test_debug_visibility_is_role_gated() -> None:
    assert _can_view_debug_user(100, admin_ids=(100,), debug_enabled=True) is True
    assert _can_view_debug_user(100, admin_ids=(100,), debug_enabled=False) is False
    assert _can_view_debug_user(200, admin_ids=(100,), debug_enabled=True) is False


def test_coupon_panel_flow_smoke() -> None:
    async def runner() -> None:
        checkout_id = uuid4()
        state = FakeFSMContext()
        await state.update_data(checkout_coupon_checkout_id=str(checkout_id), ui_container_message_id=444)
        message = FakeMessage()
        message.text = "SPRING10"

        service = SimpleNamespace(
            apply_coupon_to_checkout=lambda **kwargs: _resolved_coupon_result(checkout_id, kwargs["coupon_code"])
        )
        await coupon_submit(
            message=message,
            state=state,
            checkout_service=service,
            admin_ids=(100,),
            debug_enabled=True,
        )
        assert message.bot.edits
        assert "Купон SPRING10 принят" in message.bot.edits[0]["text"]

    async def _resolved_coupon_result(checkout_id, coupon_code):
        _ = coupon_code
        checkout = _checkout_state(checkout_id=checkout_id, total=1200)
        checkout.checkout.discount_amount = 300
        return SimpleNamespace(status="applied", checkout=checkout, redemption=None)

    asyncio.run(runner())


def test_checkout_refresh_updates_existing_panel() -> None:
    async def runner() -> None:
        checkout_id = uuid4()
        callback = FakeCallback(checkout_id)
        state = FakeFSMContext()
        await state.update_data(ui_container_message_id=777)
        service = SimpleNamespace(get_checkout=lambda **kwargs: _resolved_state(checkout_id))

        await show_status(
            callback=callback,
            state=state,
            checkout_service=service,
            admin_ids=(),
            debug_enabled=False,
        )
        assert callback.message.bot.edits
        assert callback.message.bot.edits[0]["message_id"] == 777
        assert "Статус обновлен." in callback.message.bot.edits[0]["text"]

    async def _resolved_state(checkout_id):
        return _checkout_state(checkout_id=checkout_id)

    asyncio.run(runner())
