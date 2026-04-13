import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.bots.handlers.draft import (
    INPUT_MODE_LABELS,
    PRESET_LABELS,
    build_draft_actions,
    build_draft_shortcut,
    build_input_mode_actions,
    build_preset_actions,
    build_preview_actions,
    build_readiness_actions,
    _render_active_protocol_summary,
    _render_draft_summary,
    _render_stack_composition,
    _render_inventory_composition,
    _parse_inventory_input,
    _render_course_estimate,
    _render_pre_start_estimate_snapshot,
    _render_preview_summary,
    _render_readiness_summary,
    draft_entrypoint,
    on_continue_to_calculation,
    on_duration_input,
    on_max_injections_input,
    on_mode_selected,
    on_inventory_count_input,
    on_stack_target_input,
    on_weekly_target_input,
    on_wizard_back,
    on_wizard_cancel,
    on_clear_confirm,
    on_clear_yes,
    on_open_draft,
    on_remove_item,
)
from app.application.protocols.schemas import (
    ActiveProtocolView,
    CourseEstimate,
    CourseEstimateLine,
    DraftItemView,
    DraftSettingsView,
    DraftView,
    PulsePlanEntry,
    PulsePlanPreviewView,
)


class FakeFSMContext:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}
        self.current_state = None

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)

    async def set_state(self, value):
        self.current_state = value

    async def clear(self):
        self.data = {}
        self.current_state = None


class FakeBot:
    def __init__(self) -> None:
        self.edits: list[dict[str, object]] = []

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)
        return SimpleNamespace(message_id=kwargs["message_id"])


class FakeMessage:
    def __init__(self, *, bot: FakeBot | None = None) -> None:
        self.bot = bot or FakeBot()
        self.chat = SimpleNamespace(id=42)
        self.from_user = SimpleNamespace(id=7)
        self.message_id = 501
        self.answers: list[dict[str, object]] = []
        self.deleted = False

    async def answer(self, text, reply_markup=None, parse_mode=None):
        sent = FakeMessage(bot=self.bot)
        sent.message_id = 1000 + len(self.answers)
        self.answers.append({"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode, "sent": sent})
        return sent

    async def delete(self):
        self.deleted = True


class FakeCallback:
    def __init__(self, message: FakeMessage, data: str) -> None:
        self.message = message
        self.data = data
        self.from_user = SimpleNamespace(id=7)
        self.answers: list[dict[str, object]] = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append({"text": text, "show_alert": show_alert})


class FakeDraftService:
    def __init__(self, draft: DraftView) -> None:
        self.draft = draft
        self.stack_targets: dict[str, object] = {}
        self.inventory_constraints: dict[str, object] = {}

    async def list_draft(self, user_id: str) -> DraftView:
        return self.draft

    async def remove_item_from_draft(self, user_id: str, item_id):
        self.draft = DraftView(
            draft_id=self.draft.draft_id,
            user_id=self.draft.user_id,
            status=self.draft.status,
            created_at=self.draft.created_at,
            updated_at=self.draft.updated_at,
            settings=self.draft.settings,
            items=[],
        )
        return self.draft

    async def clear_draft(self, user_id: str):
        self.draft = DraftView(
            draft_id=self.draft.draft_id,
            user_id=self.draft.user_id,
            status=self.draft.status,
            created_at=self.draft.created_at,
            updated_at=self.draft.updated_at,
            settings=self.draft.settings,
            items=[],
        )
        return self.draft

    async def get_draft_settings(self, user_id: str):
        return self.draft.settings

    async def save_draft_settings(self, user_id: str, payload):
        now = datetime.now(timezone.utc)
        self.draft = DraftView(
            draft_id=self.draft.draft_id,
            user_id=self.draft.user_id,
            status=self.draft.status,
            created_at=self.draft.created_at,
            updated_at=now,
            settings=DraftSettingsView(
                draft_id=self.draft.draft_id,
                protocol_input_mode=payload.protocol_input_mode,
                weekly_target_total_mg=payload.weekly_target_total_mg,
                duration_weeks=payload.duration_weeks,
                preset_code=payload.preset_code,
                max_injection_volume_ml=payload.max_injection_volume_ml,
                max_injections_per_week=payload.max_injections_per_week,
                planned_start_date=payload.planned_start_date,
                updated_at=now,
            ),
            items=self.draft.items,
        )
        return self.draft.settings

    async def get_stack_input_targets(self, user_id: str, protocol_input_mode: str):
        return list(self.stack_targets.values())

    async def save_stack_input_targets(self, user_id: str, payload):
        for item in payload:
            self.stack_targets[str(item.product_id)] = item
        return payload

    async def get_inventory_constraints(self, user_id: str, protocol_input_mode: str):
        return list(self.inventory_constraints.values())

    async def save_inventory_constraints(self, user_id: str, payload):
        for item in payload:
            self.inventory_constraints[str(item.product_id)] = item
        return payload

    async def get_draft_readiness(self, user_id: str):
        return SimpleNamespace(summary="ready", issues=[])


class FakeAccessService:
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed

    async def evaluate(self, user_id: str, entitlement_code: str):
        return SimpleNamespace(allowed=self.allowed)


def _draft_with_item() -> DraftView:
    now = datetime.now(timezone.utc)
    draft_id = uuid4()
    return DraftView(
        draft_id=draft_id,
        user_id="u1",
        status="active",
        created_at=now,
        updated_at=now,
        items=[
            DraftItemView(
                item_id=uuid4(),
                draft_id=draft_id,
                product_id=uuid4(),
                selected_brand="Pharmacom",
                selected_product_name="Sustanon 250",
                notes=None,
                created_at=now,
            )
        ],
    )


def _draft_with_items(count: int) -> DraftView:
    now = datetime.now(timezone.utc)
    draft_id = uuid4()
    return DraftView(
        draft_id=draft_id,
        user_id="u1",
        status="active",
        created_at=now,
        updated_at=now,
        items=[
            DraftItemView(
                item_id=uuid4(),
                draft_id=draft_id,
                product_id=uuid4(),
                selected_brand="Brand",
                selected_product_name=f"Product {idx}",
                notes=None,
                created_at=now,
            )
            for idx in range(1, count + 1)
        ],
    )


def _draft_with_item_and_settings() -> DraftView:
    draft = _draft_with_item()
    now = datetime.now(timezone.utc)
    return DraftView(
        draft_id=draft.draft_id,
        user_id=draft.user_id,
        status=draft.status,
        created_at=now,
        updated_at=now,
        items=draft.items,
        settings=DraftSettingsView(
            draft_id=draft.draft_id,
            protocol_input_mode="total_target",
            weekly_target_total_mg=Decimal("350.0"),
            duration_weeks=12,
            preset_code="layered_pulse",
            max_injection_volume_ml=Decimal("2.0"),
            max_injections_per_week=3,
            planned_start_date=None,
            updated_at=now,
        ),
    )


def test_build_draft_shortcut_button() -> None:
    keyboard = build_draft_shortcut()
    assert keyboard.inline_keyboard[0][0].text == "Draft"
    assert keyboard.inline_keyboard[0][0].callback_data == "draft:open"


def test_build_draft_actions_contains_remove_clear_and_calculation() -> None:
    keyboard = build_draft_actions(_draft_with_item())
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert "Обновить Draft" in labels
    assert any(label.startswith("🗑 Удалить #") for label in labels)
    assert "Очистить Draft" in labels
    assert "К расчету" in labels
    assert "draft:clear:confirm" in callbacks
    assert "draft:calculate" in callbacks
    assert "search:back" in callbacks


def test_build_preset_actions_contains_all_presets() -> None:
    keyboard = build_preset_actions()
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    labels = [button.text for row in keyboard.inline_keyboard for button in row]

    assert len(callbacks) == 3
    assert "draft:calc:preset:unified_rhythm" in callbacks
    assert "draft:calc:preset:layered_pulse" in callbacks
    assert "draft:calc:preset:golden_pulse" in callbacks
    assert set(labels) == set(PRESET_LABELS.values())


def test_build_readiness_and_preview_actions() -> None:
    readiness = build_readiness_actions()
    preview = build_preview_actions(uuid4())

    readiness_callbacks = [b.callback_data for row in readiness.inline_keyboard for b in row]
    preview_callbacks = [b.callback_data for row in preview.inline_keyboard for b in row]
    assert "draft:calculate:run" in readiness_callbacks
    assert "draft:wizard:back" in readiness_callbacks
    assert "draft:calculate:run" in preview_callbacks
    assert any(callback.startswith("draft:activate:prepare:") for callback in preview_callbacks)
    assert any(callback.startswith("draft:estimate:preview:") for callback in preview_callbacks)


def test_render_preview_summary_smoke() -> None:
    preview = PulsePlanPreviewView(
        preview_id=uuid4(),
        draft_id=uuid4(),
        protocol_input_mode="auto_pulse",
        preset_requested="golden_pulse",
        preset_applied="layered_pulse",
        status="degraded_fallback",
        degraded_fallback=True,
        summary_metrics={
            "flatness_stability_score": 88.2,
            "estimated_injections_per_week": 4,
            "max_volume_per_event_ml": 1.1,
            "allocation_mode": "guidance_weighted",
            "guidance_coverage_score": 92.0,
            "allocation_warning_flags": [],
        },
        warning_flags=["golden_pulse_fallback_to_layered"],
        allocation_mode="guidance_weighted",
        guidance_coverage_score=Decimal("92.0"),
        calculation_quality_flags=[],
        entries=[
            PulsePlanEntry(
                day_offset=0,
                scheduled_day=None,
                product_id=uuid4(),
                ingredient_context="Test",
                volume_ml=Decimal("1.0"),
                computed_mg=Decimal("100"),
                injection_event_key="evt_d0",
                sequence_no=0,
            )
        ],
    )
    text = _render_preview_summary(preview)
    assert "degraded_fallback" in text
    assert "Warnings:" in text
    assert "allocation mode" in text


def test_render_active_protocol_summary_smoke() -> None:
    active = ActiveProtocolView(
        protocol_id=uuid4(),
        draft_id=uuid4(),
        source_preview_id=uuid4(),
        pulse_plan_id=uuid4(),
        status="active",
        settings_snapshot={"preset_code": "layered_pulse", "duration_weeks": 8, "weekly_target_total_mg": "250"},
        protocol_input_mode="total_target",
        summary_metrics={"flatness_stability_score": 88.2},
        warning_flags=[],
    )
    text = _render_active_protocol_summary(active)
    assert "Protocol activated" in text
    assert "Protocol is active" in text


def test_build_input_mode_actions_smoke() -> None:
    keyboard = build_input_mode_actions()
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "draft:calc:mode:auto_pulse" in callbacks
    assert "draft:calc:mode:total_target" in callbacks
    assert "draft:calc:mode:stack_smoothing" in callbacks
    assert "draft:calc:mode:inventory_constrained" in callbacks
    assert set(INPUT_MODE_LABELS.values()).issubset(set(labels))


def test_render_stack_composition_smoke() -> None:
    pid = str(uuid4())
    text = _render_stack_composition({pid: Decimal("150")}, {pid: "Sustanon"})
    assert "Sustanon" in text
    assert "Derived total weekly mg: 150" in text


def test_inventory_input_parser_and_render_smoke() -> None:
    parsed = _parse_inventory_input("20 vial")
    assert parsed == (Decimal("20"), "vial")
    assert _parse_inventory_input("oops") is None
    pid = str(uuid4())
    item = type("Constraint", (), {"available_count": Decimal("20"), "count_unit": "vial"})()
    text = _render_inventory_composition({pid: item}, {pid: "Sustanon"})
    assert "Sustanon" in text
    assert "20 vial" in text


def test_pre_start_estimate_visibility_with_insufficiency_warning() -> None:
    estimate = CourseEstimate(
        source_type="preview",
        protocol_id=None,
        preview_id=uuid4(),
        draft_id=uuid4(),
        protocol_input_mode="inventory_constrained",
        duration_weeks=10,
        total_products_count=1,
        has_inventory_comparison=True,
        generated_at=datetime.now(timezone.utc),
        lines=[
            CourseEstimateLine(
                product_id=uuid4(),
                product_name="Test Vial",
                required_active_mg_total=Decimal("300.0000"),
                required_volume_ml_total=Decimal("3.0000"),
                required_unit_count_total=None,
                package_kind="vial",
                package_count_required=Decimal("3.0000"),
                package_count_required_rounded=3,
                available_active_mg=Decimal("100.0000"),
                available_package_count=Decimal("1.0000"),
                inventory_sufficiency_status="insufficient",
                shortfall_active_mg=Decimal("200.0000"),
                shortfall_package_count=Decimal("2.0000"),
                estimation_status="ok",
                estimation_warnings=[],
            )
        ],
    )
    text = _render_pre_start_estimate_snapshot(estimate)
    assert "Pre-start course estimate snapshot" in text
    assert "insufficient for full duration" in text


def test_course_estimate_rendering_insufficiency_and_unsupported_semantics() -> None:
    estimate = CourseEstimate(
        source_type="preview",
        protocol_id=None,
        preview_id=uuid4(),
        draft_id=uuid4(),
        protocol_input_mode="inventory_constrained",
        duration_weeks=12,
        total_products_count=2,
        has_inventory_comparison=True,
        generated_at=datetime.now(timezone.utc),
        lines=[
            CourseEstimateLine(
                product_id=uuid4(),
                product_name="Injectable A",
                required_active_mg_total=Decimal("500.0000"),
                required_volume_ml_total=Decimal("5.0000"),
                required_unit_count_total=None,
                package_kind="vial",
                package_count_required=Decimal("5.0000"),
                package_count_required_rounded=5,
                available_active_mg=Decimal("200.0000"),
                available_package_count=Decimal("2.0000"),
                inventory_sufficiency_status="insufficient",
                shortfall_active_mg=Decimal("300.0000"),
                shortfall_package_count=Decimal("3.0000"),
                estimation_status="ok",
                estimation_warnings=[],
            ),
            CourseEstimateLine(
                product_id=uuid4(),
                product_name="Tablet B",
                required_active_mg_total=Decimal("150.0000"),
                required_volume_ml_total=None,
                required_unit_count_total=None,
                package_kind="tablet",
                package_count_required=None,
                package_count_required_rounded=None,
                available_active_mg=None,
                available_package_count=Decimal("10.0000"),
                inventory_sufficiency_status="unknown",
                shortfall_active_mg=None,
                shortfall_package_count=None,
                estimation_status="unsupported",
                estimation_warnings=["package_estimation_not_supported"],
            ),
        ],
    )
    text = _render_course_estimate(estimate)
    assert "insufficient for full duration" in text
    assert "estimation unavailable" in text
    assert "source: preview-based" in text


def test_course_estimate_source_distinction_preview_vs_active_protocol() -> None:
    base_line = CourseEstimateLine(
        product_id=uuid4(),
        product_name="Product X",
        required_active_mg_total=Decimal("100.0000"),
        required_volume_ml_total=Decimal("1.0000"),
        required_unit_count_total=None,
        package_kind="vial",
        package_count_required=Decimal("1.0000"),
        package_count_required_rounded=1,
        available_active_mg=None,
        available_package_count=None,
        inventory_sufficiency_status="not_applicable",
        shortfall_active_mg=None,
        shortfall_package_count=None,
        estimation_status="ok",
        estimation_warnings=[],
    )
    preview_text = _render_course_estimate(
        CourseEstimate(
            source_type="preview",
            protocol_id=None,
            preview_id=uuid4(),
            draft_id=uuid4(),
            protocol_input_mode="total_target",
            duration_weeks=8,
            total_products_count=1,
            has_inventory_comparison=False,
            generated_at=datetime.now(timezone.utc),
            lines=[base_line],
        )
    )
    active_text = _render_course_estimate(
        CourseEstimate(
            source_type="active_protocol",
            protocol_id=uuid4(),
            preview_id=None,
            draft_id=uuid4(),
            protocol_input_mode="total_target",
            duration_weeks=8,
            total_products_count=1,
            has_inventory_comparison=False,
            generated_at=datetime.now(timezone.utc),
            lines=[base_line],
        )
    )
    assert "source: preview-based" in preview_text
    assert "source: active-protocol-based" in active_text


def test_draft_open_uses_single_panel_container_semantics() -> None:
    async def runner() -> None:
        draft = _draft_with_item()
        service = FakeDraftService(draft)
        state = FakeFSMContext()
        message = FakeMessage()

        await draft_entrypoint(message=message, state=state, draft_service=service)
        assert len(message.answers) == 1
        sent = message.answers[0]["sent"]

        await on_open_draft(callback=FakeCallback(message, "draft:open"), state=state, draft_service=service)
        assert message.bot.edits[-1]["message_id"] == sent.message_id

    asyncio.run(runner())


def test_remove_item_updates_existing_draft_panel() -> None:
    async def runner() -> None:
        draft = _draft_with_item()
        service = FakeDraftService(draft)
        state = FakeFSMContext()
        message = FakeMessage()
        await draft_entrypoint(message=message, state=state, draft_service=service)
        panel_id = message.answers[0]["sent"].message_id

        await on_remove_item(
            callback=FakeCallback(message, f"draft:remove:{draft.items[0].item_id}"),
            state=state,
            draft_service=service,
        )
        assert message.bot.edits[-1]["message_id"] == panel_id
        assert "Позиции: <b>0</b>" in message.bot.edits[-1]["text"]

    asyncio.run(runner())


def test_clear_draft_confirmation_and_apply_work_in_same_panel() -> None:
    async def runner() -> None:
        draft = _draft_with_item()
        service = FakeDraftService(draft)
        state = FakeFSMContext()
        message = FakeMessage()
        await draft_entrypoint(message=message, state=state, draft_service=service)
        panel_id = message.answers[0]["sent"].message_id

        await on_clear_confirm(
            callback=FakeCallback(message, "draft:clear:confirm"),
            state=state,
            draft_service=service,
        )
        assert message.bot.edits[-1]["message_id"] == panel_id
        buttons = [b.text for row in message.bot.edits[-1]["reply_markup"].inline_keyboard for b in row]
        assert "✅ Да, очистить" in buttons

        await on_clear_yes(
            callback=FakeCallback(message, "draft:clear:yes"),
            state=state,
            draft_service=service,
        )
        assert message.bot.edits[-1]["message_id"] == panel_id
        assert "Позиции: <b>0</b>" in message.bot.edits[-1]["text"]

    asyncio.run(runner())


def test_draft_summary_uses_human_readable_labels() -> None:
    text = _render_draft_summary(_draft_with_item_and_settings())
    assert "Режим ввода" in text
    assert "Цель, мг/нед" in text
    assert "protocol_input_mode" not in text
    assert "weekly_target_total_mg" not in text


def test_wizard_mode_selection_updates_single_panel() -> None:
    async def runner() -> None:
        service = FakeDraftService(_draft_with_item())
        state = FakeFSMContext()
        message = FakeMessage()
        await draft_entrypoint(message=message, state=state, draft_service=service)
        callback = FakeCallback(message, "draft:calculate")
        await on_continue_to_calculation(callback=callback, state=state, draft_service=service)
        assert "protocol input mode" in message.bot.edits[-1]["text"]
    asyncio.run(runner())


def test_wizard_back_navigation_returns_previous_step() -> None:
    async def runner() -> None:
        service = FakeDraftService(_draft_with_item())
        state = FakeFSMContext()
        message = FakeMessage()
        await on_continue_to_calculation(FakeCallback(message, "draft:calculate"), state, service)
        await on_mode_selected(FakeCallback(message, "draft:calc:mode:total_target"), state, service, FakeAccessService())
        await on_wizard_back(FakeCallback(message, "draft:wizard:back"), state, service, FakeAccessService())
        assert "protocol input mode" in message.bot.edits[-1]["text"]
    asyncio.run(runner())


def test_wizard_cancel_returns_to_draft_panel() -> None:
    async def runner() -> None:
        draft = _draft_with_item()
        service = FakeDraftService(draft)
        state = FakeFSMContext()
        message = FakeMessage()
        await on_continue_to_calculation(FakeCallback(message, "draft:calculate"), state, service)
        await on_wizard_cancel(FakeCallback(message, "draft:wizard:cancel"), state, service)
        assert "Draft • Рабочая панель" in message.bot.edits[-1]["text"]
    asyncio.run(runner())


def test_weekly_target_input_cleans_user_message() -> None:
    async def runner() -> None:
        service = FakeDraftService(_draft_with_item())
        state = FakeFSMContext()
        message = FakeMessage()
        message.text = "350"
        await on_continue_to_calculation(FakeCallback(message, "draft:calculate"), state, service)
        await on_mode_selected(FakeCallback(message, "draft:calc:mode:total_target"), state, service, FakeAccessService())
        answers_before = len(message.answers)
        await on_weekly_target_input(message=message, state=state, draft_service=service)
        assert message.deleted is True
        assert len(message.answers) == answers_before
    asyncio.run(runner())


def test_auto_pulse_flow_smoke() -> None:
    async def runner() -> None:
        service = FakeDraftService(_draft_with_item())
        state = FakeFSMContext()
        message = FakeMessage()
        await on_continue_to_calculation(FakeCallback(message, "draft:calculate"), state, service)
        await on_mode_selected(FakeCallback(message, "draft:calc:mode:auto_pulse"), state, service, FakeAccessService())
        assert "длительность" in message.bot.edits[-1]["text"].lower()
    asyncio.run(runner())


def test_total_target_flow_smoke() -> None:
    async def runner() -> None:
        service = FakeDraftService(_draft_with_item())
        state = FakeFSMContext()
        message = FakeMessage()
        await on_continue_to_calculation(FakeCallback(message, "draft:calculate"), state, service)
        await on_mode_selected(FakeCallback(message, "draft:calc:mode:total_target"), state, service, FakeAccessService())
        assert "weekly target" in message.bot.edits[-1]["text"].lower()
    asyncio.run(runner())


def test_stack_smoothing_flow_smoke() -> None:
    async def runner() -> None:
        service = FakeDraftService(_draft_with_item())
        state = FakeFSMContext()
        message = FakeMessage()
        await on_continue_to_calculation(FakeCallback(message, "draft:calculate"), state, service)
        await on_mode_selected(FakeCallback(message, "draft:calc:mode:stack_smoothing"), state, service, FakeAccessService())
        assert "stack smoothing" in message.bot.edits[-1]["text"].lower()
    asyncio.run(runner())


def test_inventory_constrained_flow_smoke() -> None:
    async def runner() -> None:
        service = FakeDraftService(_draft_with_item())
        state = FakeFSMContext()
        message = FakeMessage()
        await on_continue_to_calculation(FakeCallback(message, "draft:calculate"), state, service)
        await on_mode_selected(FakeCallback(message, "draft:calc:mode:inventory_constrained"), state, service, FakeAccessService())
        assert "inventory constrained" in message.bot.edits[-1]["text"].lower()
    asyncio.run(runner())


def test_readiness_panel_rendering_smoke() -> None:
    text = _render_readiness_summary(SimpleNamespace(summary="ok", issues=[]), settings=_draft_with_item_and_settings().settings)
    assert "Readiness" in text
    assert "Режим" in text


def test_stack_input_back_navigates_to_previous_product_in_same_panel() -> None:
    async def runner() -> None:
        service = FakeDraftService(_draft_with_items(2))
        state = FakeFSMContext()
        message = FakeMessage()

        await on_continue_to_calculation(FakeCallback(message, "draft:calculate"), state, service)
        await on_mode_selected(FakeCallback(message, "draft:calc:mode:stack_smoothing"), state, service, FakeAccessService())
        first_prompt = message.bot.edits[-1]["text"]
        message.text = "120"
        await on_stack_target_input(message=message, state=state, draft_service=service)
        second_prompt = message.bot.edits[-1]["text"]
        assert first_prompt != second_prompt

        answers_before = len(message.answers)
        await on_wizard_back(FakeCallback(message, "draft:wizard:back"), state, service, FakeAccessService())
        assert "Product 1" in message.bot.edits[-1]["text"]
        assert "Calculation setup" not in message.bot.edits[-1]["text"]
        assert len(message.answers) == answers_before

    asyncio.run(runner())


def test_inventory_input_back_navigates_to_previous_product_in_same_panel() -> None:
    async def runner() -> None:
        service = FakeDraftService(_draft_with_items(2))
        state = FakeFSMContext()
        message = FakeMessage()

        await on_continue_to_calculation(FakeCallback(message, "draft:calculate"), state, service)
        await on_mode_selected(FakeCallback(message, "draft:calc:mode:inventory_constrained"), state, service, FakeAccessService())
        first_prompt = message.bot.edits[-1]["text"]
        message.text = "20 vial"
        await on_inventory_count_input(message=message, state=state, draft_service=service)
        second_prompt = message.bot.edits[-1]["text"]
        assert first_prompt != second_prompt

        answers_before = len(message.answers)
        await on_wizard_back(FakeCallback(message, "draft:wizard:back"), state, service, FakeAccessService())
        assert "Product 1" in message.bot.edits[-1]["text"]
        assert "Calculation setup" not in message.bot.edits[-1]["text"]
        assert len(message.answers) == answers_before

    asyncio.run(runner())
