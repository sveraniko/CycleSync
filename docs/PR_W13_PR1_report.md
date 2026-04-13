# PR W13 / PR1 — UI foundation for single-panel Telegram interaction

## 1) New foundation files added

- `app/bots/core/flow.py`
  - `send_or_edit(...)`
  - `safe_edit_or_send(...)`
  - `remember_container(...)`
  - `get_container_message_id(...)`
  - `reset_container(...)`
  - `delete_user_input_message(...)`
- `app/bots/core/formatting.py`
  - `format_decimal_human(...)`
  - `compact_status_label(...)`
  - `mask_human_id(...)`
  - `escape_html_text(...)`
- `app/bots/core/permissions.py`
  - `is_admin_user(...)`
  - `can_view_debug(...)`
  - `has_role(...)`
- `app/bots/core/__init__.py` exports the reusable foundation helpers.

## 2) Container pattern behavior

`send_or_edit(...)` and `safe_edit_or_send(...)` now implement a reusable single-panel strategy:

1. Read `container_message_id` from FSM state.
2. If it exists: edit that message in-place.
3. If it does not exist (or edit fails in safe mode): send a new message and persist its id.

This removes callback-driven message spam and gives a stable interaction panel per flow.

## 3) Where `container_message_id` is stored

- Key: `ui_container_message_id`
- Storage: `FSMContext` data dictionary (per user/chat/session in aiogram FSM storage)
- Lifecycle helpers:
  - `remember_container(...)` updates id
  - `get_container_message_id(...)` reads id
  - `reset_container(...)` removes id

For the migrated proof flow (`settings`), state is cleared after time input completion (`state.clear()`), so container id is reset naturally at flow end.

## 4) Migrated proof flow

Migrated a compact representative flow: **Settings** (`app/bots/handlers/settings.py`)

What changed:

- Entry and callbacks use `safe_edit_or_send(...)` instead of `message.answer(...)` chains.
- Settings panel is updated in-place (single container message).
- Reminder-time input path deletes raw user input message (`delete_user_input_message(...)`) to reduce chat noise.
- Existing business logic (toggle reminders, set time, show protocol status) remains intact.

## 5) Exact local verification commands

```bash
pytest tests/test_bot_ui_foundation.py tests/test_bot_settings_smoke.py
```

These tests cover:

1. `send_or_edit` creates a new message when no container exists.
2. `send_or_edit` edits existing message when container exists.
3. container id persistence helpers.
4. formatting helpers.
5. smoke proof for the migrated settings flow (single-panel behavior).
