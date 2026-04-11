from datetime import time

from app.bots.handlers.settings import (
    build_settings_actions,
    _parse_time,
    _render_settings,
)
from app.application.reminders.schemas import ReminderSettingsView


def test_settings_actions_toggle_variants() -> None:
    on_markup = build_settings_actions(reminders_enabled=True)
    off_markup = build_settings_actions(reminders_enabled=False)

    assert on_markup.inline_keyboard[0][0].callback_data == "settings:reminders:off"
    assert off_markup.inline_keyboard[0][0].callback_data == "settings:reminders:on"


def test_parse_time_and_render_settings_smoke() -> None:
    assert _parse_time("09:45") == time(9, 45)
    assert _parse_time("25:10") is None

    view = ReminderSettingsView(
        user_id="tg:1",
        reminders_enabled=False,
        preferred_reminder_time_local=time(7, 0),
        timezone_name="UTC",
    )
    text = _render_settings(view)
    assert "reminders_enabled: off" in text
    assert "07:00" in text
