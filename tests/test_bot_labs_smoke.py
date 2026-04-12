from app.bots.handlers.labs import (
    build_operator_actions,
    build_labs_root_actions,
    build_panel_marker_actions,
    build_report_entry_actions,
    build_case_actions,
)


def test_labs_root_actions_contains_new_and_history() -> None:
    keyboard = build_labs_root_actions()
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:new" in callbacks
    assert "labs:history" in callbacks
    assert "labs:ops:menu" in callbacks


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
    assert "labs:triage:run" in callbacks
    assert "labs:triage:latest" in callbacks
    assert "labs:triage:regenerate" in callbacks


def test_report_entry_actions_contains_consult_specialist() -> None:
    keyboard = build_report_entry_actions()
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:case:consult" in callbacks


def test_case_actions_contains_latest_case() -> None:
    keyboard = build_case_actions()
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:case:latest" in callbacks


def test_operator_actions_contains_take_answer_close() -> None:
    keyboard = build_operator_actions("case-1")
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:ops:take:case-1" in callbacks
    assert "labs:ops:answer:case-1" in callbacks
    assert "labs:ops:close:case-1" in callbacks
