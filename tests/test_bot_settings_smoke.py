from datetime import time

from app.bots.handlers.settings import (
    _render_protocol_status,
    build_settings_actions,
    _parse_time,
    _render_settings,
)
from app.application.reminders.schemas import (
    ProtocolAdherenceSummaryView,
    ProtocolStatusView,
    ReminderSettingsView,
)
from uuid import uuid4
from datetime import datetime, timezone


def test_settings_actions_toggle_variants() -> None:
    on_markup = build_settings_actions(reminders_enabled=True)
    off_markup = build_settings_actions(reminders_enabled=False)

    assert on_markup.inline_keyboard[0][0].callback_data == "settings:reminders:off"
    assert off_markup.inline_keyboard[0][0].callback_data == "settings:reminders:on"
    assert on_markup.inline_keyboard[2][0].callback_data == "settings:protocol:status"


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
    assert "Напоминания: ❌ выключены" in text
    assert "07:00" in text


def test_render_protocol_status_smoke() -> None:
    summary = ProtocolAdherenceSummaryView(
        protocol_id=uuid4(),
        pulse_plan_id=uuid4(),
        user_id="tg:1",
        completed_count=5,
        skipped_count=1,
        snoozed_count=2,
        expired_count=1,
        total_actionable_count=7,
        completion_rate=5 / 7,
        skip_rate=1 / 7,
        expiry_rate=1 / 7,
        last_action_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
        integrity_state="watch",
        integrity_reason_code="recent_misses",
        broken_reason_code=None,
        integrity_detail_json={},
        updated_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
    )
    status = ProtocolStatusView(
        has_active_protocol=True,
        integrity_state="watch",
        explanation="demo",
        summary=summary,
    )
    rendered = _render_protocol_status(status)
    assert "Целостность: Watch" in rendered
    assert "Выполнение:" in rendered
