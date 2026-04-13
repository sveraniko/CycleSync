import asyncio
from datetime import time
from types import SimpleNamespace

from app.bots.core.flow import (
    get_container_message_id,
    remember_container,
    reset_container,
    send_or_edit,
)
from app.bots.core.formatting import compact_status_label, format_decimal_human, mask_human_id
from app.bots.handlers.settings import settings_entrypoint, on_reminders_on
from app.application.reminders.schemas import ReminderSettingsView


class FakeFSMContext:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)

    async def set_data(self, data):
        self.data = dict(data)

    async def clear(self):
        self.data = {}


class FakeBot:
    def __init__(self) -> None:
        self.edits: list[dict[str, object]] = []

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)
        return SimpleNamespace(message_id=kwargs["message_id"])


class FakeMessage:
    def __init__(self, *, bot: FakeBot | None = None, message_id: int = 10) -> None:
        self.bot = bot or FakeBot()
        self.chat = SimpleNamespace(id=42)
        self.from_user = SimpleNamespace(id=100)
        self.message_id = message_id
        self.answers: list[dict[str, object]] = []

    async def answer(self, text, reply_markup=None, parse_mode=None):
        sent_id = 1000 + len(self.answers)
        sent = FakeMessage(bot=self.bot, message_id=sent_id)
        self.answers.append({"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode, "sent": sent})
        return sent


class FakeCallback:
    def __init__(self, message: FakeMessage) -> None:
        self.message = message
        self.from_user = SimpleNamespace(id=100)
        self.answer_calls: list[dict[str, object]] = []

    async def answer(self, text=None, show_alert=False):
        self.answer_calls.append({"text": text, "show_alert": show_alert})


class FakeReminderService:
    def __init__(self) -> None:
        self.enabled = False

    async def get_reminder_settings(self, user_id: str):
        return ReminderSettingsView(
            user_id=user_id,
            reminders_enabled=self.enabled,
            preferred_reminder_time_local=time(9, 0),
            timezone_name="UTC",
        )

    async def update_reminder_settings(self, **kwargs):
        self.enabled = kwargs["reminders_enabled"]
        return await self.get_reminder_settings(kwargs["user_id"])


def test_send_or_edit_creates_new_message_if_container_missing() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        message = FakeMessage()
        await send_or_edit(state=state, source_message=message, text="hello")
        assert len(message.answers) == 1
        assert await get_container_message_id(state) == 1000

    asyncio.run(runner())


def test_send_or_edit_edits_existing_message_if_container_exists() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        message = FakeMessage()
        await remember_container(state, 777)
        await send_or_edit(state=state, source_message=message, text="edited")
        assert len(message.answers) == 0
        assert message.bot.edits[0]["message_id"] == 777

    asyncio.run(runner())


def test_container_id_persistence_helpers() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        assert await get_container_message_id(state) is None
        await remember_container(state, 123)
        assert await get_container_message_id(state) == 123
        await reset_container(state)
        assert await get_container_message_id(state) is None

    asyncio.run(runner())


def test_formatting_helpers_smoke() -> None:
    assert format_decimal_human("500.0000") == "500"
    assert compact_status_label("degraded_fallback") == "Degraded Fallback"
    assert mask_human_id("1234567890", prefix=3, suffix=2) == "123…90"


def test_settings_flow_smoke_uses_single_panel_container() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        message = FakeMessage()
        service = FakeReminderService()

        await settings_entrypoint(message=message, state=state, reminder_service=service)
        assert len(message.answers) == 1

        callback = FakeCallback(message)
        await on_reminders_on(callback=callback, state=state, reminder_service=service)

        assert len(message.bot.edits) == 1
        assert message.bot.edits[0]["message_id"] == 1000

    asyncio.run(runner())
