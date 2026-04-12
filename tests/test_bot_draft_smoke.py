from datetime import datetime, timezone
from decimal import Decimal
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
    _render_stack_composition,
    _render_inventory_composition,
    _parse_inventory_input,
    _render_course_estimate,
    _render_pre_start_estimate_snapshot,
    _render_preview_summary,
)
from app.application.protocols.schemas import (
    ActiveProtocolView,
    CourseEstimate,
    CourseEstimateLine,
    DraftItemView,
    DraftView,
    PulsePlanEntry,
    PulsePlanPreviewView,
)


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


def test_build_draft_shortcut_button() -> None:
    keyboard = build_draft_shortcut()
    assert keyboard.inline_keyboard[0][0].text == "Draft"
    assert keyboard.inline_keyboard[0][0].callback_data == "draft:open"


def test_build_draft_actions_contains_remove_clear_and_calculation() -> None:
    keyboard = build_draft_actions(_draft_with_item())
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert "Обновить Draft" in labels
    assert any(label.startswith("Удалить:") for label in labels)
    assert "Очистить Draft" in labels
    assert "К расчету" in labels
    assert "draft:clear:confirm" in callbacks
    assert "draft:calculate" in callbacks


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
    assert "draft:stack:edit" in readiness_callbacks
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
    assert "Wave 3" in text


def test_build_input_mode_actions_smoke() -> None:
    keyboard = build_input_mode_actions()
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "draft:calc:mode:auto_pulse" in callbacks
    assert "draft:calc:mode:total_target" in callbacks
    assert "draft:calc:mode:stack_smoothing" in callbacks
    assert "draft:calc:mode:inventory_constrained" in callbacks
    assert set(labels) == set(INPUT_MODE_LABELS.values())


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
