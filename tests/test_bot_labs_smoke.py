from app.bots.handlers.labs import (
    build_labs_root_actions,
    build_panel_marker_actions,
    build_report_entry_actions,
)


def test_labs_root_actions_contains_new_and_history() -> None:
    keyboard = build_labs_root_actions()
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:new" in callbacks
    assert "labs:history" in callbacks


def test_panel_actions_contains_skip_and_finish() -> None:
    keyboard = build_panel_marker_actions()
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:panel:skip" in callbacks
    assert "labs:panel:finish" in callbacks


def test_report_entry_actions_contains_required_panels() -> None:
    keyboard = build_report_entry_actions()
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    for code in ["male_hormones", "hematology", "lipids", "liver", "metabolic", "gh_related"]:
        assert f"labs:panel:{code}" in callbacks
