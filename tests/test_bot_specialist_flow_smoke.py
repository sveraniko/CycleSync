from app.bots.handlers.labs import build_labs_root_actions, build_operator_actions


def test_specialist_operator_entrypoint_available() -> None:
    keyboard = build_labs_root_actions()
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:ops:menu" in callbacks
    assert "labs:case:list" in callbacks


def test_specialist_operator_case_actions_smoke() -> None:
    keyboard = build_operator_actions("sample-case")
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "labs:ops:take:sample-case" in callbacks
    assert "labs:ops:answer:sample-case" in callbacks
