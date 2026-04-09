from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.bots.handlers.draft import (
    PRESET_LABELS,
    build_draft_actions,
    build_draft_shortcut,
    build_preset_actions,
    build_preview_actions,
    build_readiness_actions,
    _render_preview_summary,
)
from app.application.protocols.schemas import DraftItemView, DraftView, PulsePlanEntry, PulsePlanPreviewView


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
    preview = build_preview_actions()

    readiness_callbacks = [b.callback_data for row in readiness.inline_keyboard for b in row]
    preview_callbacks = [b.callback_data for row in preview.inline_keyboard for b in row]
    assert "draft:calculate:run" in readiness_callbacks
    assert "draft:calculate:run" in preview_callbacks


def test_render_preview_summary_smoke() -> None:
    preview = PulsePlanPreviewView(
        preview_id=uuid4(),
        draft_id=uuid4(),
        preset_requested="golden_pulse",
        preset_applied="layered_pulse",
        status="degraded_fallback",
        degraded_fallback=True,
        summary_metrics={
            "flatness_stability_score": 88.2,
            "estimated_injections_per_week": 4,
            "max_volume_per_event_ml": 1.1,
        },
        warning_flags=["golden_pulse_fallback_to_layered"],
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
