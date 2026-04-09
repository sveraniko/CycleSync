from app.bots.handlers.search import build_result_actions


def test_build_result_actions_contains_open_and_draft() -> None:
    keyboard = build_result_actions("abc")
    buttons = keyboard.inline_keyboard[0]
    assert buttons[0].text == "Open"
    assert buttons[0].callback_data == "search:open:abc"
    assert buttons[1].text == "+Draft"
    assert buttons[1].callback_data == "search:draft:abc"
