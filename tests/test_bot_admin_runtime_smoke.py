import asyncio
from types import SimpleNamespace

from app.bots.core.admin_config import AdminRuntimeConfig
from app.bots.handlers.admin import (
    _build_admin_keyboard,
    _render_admin_panel,
    _render_runtime_status_block,
    on_admin_panel,
    on_commerce_toggle,
    on_debug_toggle,
)
from app.bots.handlers.checkout import _can_view_debug_user
from app.bots.handlers.settings import build_settings_actions


class FakeFSMContext:
    def __init__(self) -> None:
        self.data = {"ui_container_message_id": 77}

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)

    async def set_data(self, data):
        self.data = dict(data)


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
        self.message_id = 12

    async def answer(self, text, reply_markup=None, parse_mode=None):
        return SimpleNamespace(message_id=999, text=text, reply_markup=reply_markup, parse_mode=parse_mode)


class FakeCallback:
    def __init__(self, user_id: int, data: str):
        self.message = FakeMessage()
        self.from_user = SimpleNamespace(id=user_id)
        self.data = data
        self.answer_calls = []

    async def answer(self, text=None, show_alert=False):
        self.answer_calls.append({"text": text, "show_alert": show_alert})


def test_admin_runtime_panel_rendering_smoke() -> None:
    config = AdminRuntimeConfig(
        commerce_enabled=True,
        debug_enabled=False,
        pulse_engine_version="v2",
        app_env="pilot",
    )
    text = _render_admin_panel(config, debug_enabled=config.debug_enabled, admin_ids=(11,))
    assert "📡 Состояние рантайма" in text
    assert "Коммерческий режим: <b>ВКЛ</b>" in text
    assert "Отладка: <b>ВЫКЛ</b>" in text
    assert "Версия Pulse Engine: <code>v2</code>" in text


def test_non_admin_cannot_access_runtime_controls() -> None:
    async def runner() -> None:
        callback = FakeCallback(user_id=22, data="admin:panel")
        await on_admin_panel(
            callback=callback,
            state=FakeFSMContext(),
            admin_ids=(11,),
            admin_config=AdminRuntimeConfig(),
            debug_enabled=False,
        )
        assert callback.answer_calls
        assert callback.answer_calls[-1]["show_alert"] is True
        assert callback.answer_calls[-1]["text"] == "Нет доступа"

    asyncio.run(runner())


def test_commerce_toggle_updates_panel_and_entrypoints() -> None:
    async def runner() -> None:
        config = AdminRuntimeConfig(commerce_enabled=False, debug_enabled=False)
        callback = FakeCallback(user_id=11, data="admin:commerce:toggle")
        await on_commerce_toggle(
            callback=callback,
            state=FakeFSMContext(),
            admin_ids=(11,),
            admin_config=config,
            debug_enabled=False,
        )
        assert config.commerce_enabled is True
        settings_keyboard = build_settings_actions(reminders_enabled=True, commerce_enabled=config.commerce_enabled)
        callbacks = [b.callback_data for row in settings_keyboard.inline_keyboard for b in row]
        assert "checkout:demo:start" in callbacks

    asyncio.run(runner())


def test_debug_toggle_updates_panel_and_debug_actions() -> None:
    async def runner() -> None:
        config = AdminRuntimeConfig(commerce_enabled=True, debug_enabled=False)
        callback = FakeCallback(user_id=11, data="admin:debug:toggle")
        await on_debug_toggle(
            callback=callback,
            state=FakeFSMContext(),
            admin_ids=(11,),
            admin_config=config,
            debug_enabled=False,
        )
        assert config.debug_enabled is True
        assert _can_view_debug_user(11, admin_ids=(11,), debug_enabled=config.debug_enabled) is True
        assert _can_view_debug_user(99, admin_ids=(11,), debug_enabled=config.debug_enabled) is False

    asyncio.run(runner())


def test_runtime_status_block_rendering() -> None:
    config = AdminRuntimeConfig(
        commerce_enabled=True,
        debug_enabled=True,
        pulse_engine_version="v2",
        app_env="pre-mvp",
        last_catalog_operation={"status": "ok", "timestamp": "2026-04-14T12:00:00Z", "source_type": "xlsx"},
    )
    text = _render_runtime_status_block(config, debug_enabled=True)
    assert "Контур запуска: <code>pre-mvp</code>" in text
    assert "Синхронизация каталога: <b>ok</b> (xlsx, 2026-04-14T12:00:00Z)" in text


def test_access_and_commercial_surfaces_visibility_smoke() -> None:
    keyboard_off = build_settings_actions(reminders_enabled=True, commerce_enabled=False)
    callbacks_off = [b.callback_data for row in keyboard_off.inline_keyboard for b in row]
    assert "access:activate:start" in callbacks_off
    assert "checkout:demo:start" not in callbacks_off

    keyboard_on = build_settings_actions(reminders_enabled=True, commerce_enabled=True)
    callbacks_on = [b.callback_data for row in keyboard_on.inline_keyboard for b in row]
    assert "access:activate:start" in callbacks_on
    assert "checkout:demo:start" in callbacks_on

    admin_keyboard = _build_admin_keyboard(AdminRuntimeConfig(commerce_enabled=True, debug_enabled=True))
    admin_callbacks = [b.callback_data for row in admin_keyboard.inline_keyboard for b in row]
    assert "admin:commerce:toggle" in admin_callbacks
    assert "admin:debug:toggle" in admin_callbacks
