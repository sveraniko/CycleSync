import asyncio
from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.bots.handlers.labs import (
    _format_triage_result,
    _render_history_panel,
    _render_specialist_case_list_panel,
    _show_labs_root,
    build_labs_root_actions,
    build_panel_marker_actions,
    build_report_entry_actions,
    build_report_panel_actions,
)


class FakeFSMContext:
    def __init__(self, data: dict | None = None) -> None:
        self.data = data or {}
        self.state_name = None

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)

    async def set_data(self, data):
        self.data = dict(data)

    async def clear(self):
        self.data = {}

    async def set_state(self, state):
        self.state_name = str(state) if state else None

    async def get_state(self):
        return self.state_name


class FakeBot:
    def __init__(self) -> None:
        self.edits = []

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)
        return SimpleNamespace(message_id=kwargs["message_id"])


class FakeMessage:
    def __init__(self, *, bot: FakeBot | None = None, message_id: int = 10) -> None:
        self.bot = bot or FakeBot()
        self.chat = SimpleNamespace(id=42)
        self.from_user = SimpleNamespace(id=100)
        self.message_id = message_id
        self.answers = []

    async def answer(self, text, reply_markup=None, parse_mode=None):
        sent_id = 1000 + len(self.answers)
        sent = FakeMessage(bot=self.bot, message_id=sent_id)
        self.answers.append({"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode, "sent": sent})
        return sent


def test_labs_root_panel_smoke_single_container_actions() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        message = FakeMessage()
        await _show_labs_root(source_message=message, state=state)
        await _show_labs_root(source_message=message, state=state, notice="updated")
        assert len(message.answers) == 1
        assert len(message.bot.edits) == 1

    asyncio.run(runner())


def test_labs_root_role_gated_operator_visibility() -> None:
    without_ops = build_labs_root_actions(False)
    with_ops = build_labs_root_actions(True)
    without_callbacks = [b.callback_data for row in without_ops.inline_keyboard for b in row]
    with_callbacks = [b.callback_data for row in with_ops.inline_keyboard for b in row]

    assert "labs:ops:menu" not in without_callbacks
    assert "labs:ops:menu" in with_callbacks


def test_report_entry_hierarchy_actions_smoke() -> None:
    root = build_report_entry_actions()
    callbacks = [b.callback_data for row in root.inline_keyboard for b in row]
    assert callbacks[:3] == ["labs:entry:panels", "labs:entry:ai", "labs:entry:actions"]

    panels = build_report_panel_actions()
    panel_callbacks = [b.callback_data for row in panels.inline_keyboard for b in row]
    for code in ["male_hormones", "hematology", "lipids", "liver", "metabolic", "gh_related"]:
        assert f"labs:panel:{code}" in panel_callbacks


def test_panel_actions_contains_skip_and_finish() -> None:
    keyboard = build_panel_marker_actions()
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:panel:skip" in callbacks
    assert "labs:panel:finish" in callbacks


def test_history_rendering_smoke_hides_raw_uuid_dump() -> None:
    report_id = uuid4()
    protocol_id = uuid4()
    report = SimpleNamespace(
        report_id=report_id,
        report_date=date(2026, 4, 12),
        source_lab_name="Helix",
        protocol_id=protocol_id,
    )
    rendered = _render_history_panel([(report, 6)])
    assert str(report_id) not in rendered
    assert "2026-04-12" in rendered
    assert "6 марк." in rendered


def test_triage_rendering_smoke_card_like() -> None:
    triage = SimpleNamespace(
        run=SimpleNamespace(triage_status="completed", urgent_flag=True, summary_text="Есть отклонения"),
        flags=[
            SimpleNamespace(severity="warning", title="ALT elevated"),
            SimpleNamespace(severity="watch", title="HDL low"),
        ],
    )
    rendered = _format_triage_result(triage)
    assert "AI pre-triage" in rendered
    assert "🔴 срочно" in rendered
    assert "🟠" in rendered


def test_specialist_case_rendering_smoke() -> None:
    item = SimpleNamespace(
        case_id=uuid4(),
        case_status="awaiting_specialist",
        lab_report_date=date(2026, 4, 11),
        latest_response_summary="Подготовлен ответ",
        opened_at=datetime(2026, 4, 11, 9, 0),
    )
    rendered = _render_specialist_case_list_panel([item])
    assert "awaiting" in rendered.lower()
    assert str(item.case_id) not in rendered
