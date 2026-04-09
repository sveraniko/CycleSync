from app.bots.handlers.draft import PRESET_LABELS, build_draft_actions, build_draft_shortcut, build_preset_actions
from app.application.protocols.schemas import DraftItemView, DraftView
from datetime import datetime, timezone
from uuid import uuid4


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
