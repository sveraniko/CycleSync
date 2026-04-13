# PR W13 / PR4-FIX — Calculation Wizard Single-Panel Completion

## 1) Exact wizard paths that were still spamming
In `app/bots/handlers/draft.py`, the wizard still had chat-spam behavior in these paths:

1. **Stack input flow fallback error path** (`on_stack_target_input`) used `message.answer(...)` when state lost `stack_current_product_id`.
2. **Inventory input flow fallback error path** (`on_inventory_count_input`) used `message.answer(...)` when state lost `inventory_current_product_id`.
3. **Text-entry validation failures** left raw user messages in chat (weekly target, duration, max volume, max injections, stack target, inventory count), which still produced clutter while the panel updated.
4. **Back in multi-item stack/inventory loops** did not navigate to previous item; it jumped by generic history, effectively breaking step-local back behavior.

## 2) What was fixed
- Replaced stack/inventory fallback error `message.answer(...)` paths with wizard cancel flow returning to Draft panel in the same container lifecycle.
- Added cleanup (`delete_user_input_message`) for invalid text input, not only successful input, across all text-entered wizard steps.
- Implemented step-local back navigation for:
  - `stack_target` (using `stack_completed_product_ids` + pending/current rebalance)
  - `inventory_count` (using `inventory_completed_product_ids` + pending/current rebalance)
- Kept all rendering through `safe_edit_or_send(...)` via wizard panel transitions.

## 3) How back/cancel works now
- **`◀️ Назад`**:
  - For regular steps: uses wizard history stack (`calc_wizard_history`).
  - For stack/inventory per-product entry: moves to the **previous product input** inside the same step before falling back to generic history.
- **`✖️ Отмена`**:
  - Clears wizard state and per-flow cursor state.
  - Returns to Draft panel in the same container message lifecycle.

## 4) How user-input cleanup works now
For all text-entered steps, the incoming user message is deleted regardless of valid/invalid parse outcome:
- weekly target (`total_target`)
- duration (`auto_pulse` and post-branch)
- max volume
- max injections
- stack target value
- inventory count value

After deletion, the same wizard panel is edited with next-step prompt or validation hint.

## 5) Exact local verification commands
1. `python -m py_compile app/bots/handlers/draft.py tests/test_bot_draft_smoke.py`
2. `pytest -q tests/test_bot_draft_smoke.py`
