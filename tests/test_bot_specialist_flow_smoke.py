from app.bots.handlers.labs import build_case_actions, build_labs_root_actions, build_operator_actions


def test_specialist_operator_entrypoint_role_gated() -> None:
    keyboard = build_labs_root_actions(can_access_operator=False)
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:ops:menu" not in callbacks
    assert "labs:case:list" in callbacks


def test_specialist_operator_case_actions_smoke() -> None:
    keyboard = build_operator_actions("sample-case")
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:ops:take:sample-case" in callbacks
    assert "labs:ops:answer:sample-case" in callbacks


def test_case_actions_include_latest() -> None:
    keyboard = build_case_actions()
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:case:latest" in callbacks
