# PR W13 / PR4 — Calculation Wizard Single-Panel Migration

## 1) Migrated wizard steps
W13/PR4 migrated calculation setup to one stable panel (single container message) for these steps:

- mode selection
- weekly target (`total_target`)
- duration
- preset selection
- max volume
- max injections
- stack target input
- inventory count input
- readiness summary

All step transitions now go through `safe_edit_or_send(...)` via `_render_wizard_panel(...)` and `_goto_wizard_step(...)`, so callbacks update one panel instead of creating message chains.

## 2) Back / Cancel navigation
Implemented wizard navigation callbacks:

- `draft:wizard:back` → returns to previous logical step from history
- `draft:wizard:cancel` → exits wizard and returns to Draft panel

Navigation is wired across all meaningful text/callback steps including `total_target`, `auto_pulse`, `stack_smoothing`, and `inventory_constrained` (including entitlement gate and branch-specific steps).

## 3) User input cleanup
For text-entered steps, raw user input messages are deleted after successful processing using `delete_user_input_message(...)`:

- weekly target
- duration
- max volume
- max injections
- stack target values
- inventory counts

This keeps chat clean while preserving a single edited wizard panel.

## 4) Mode-specific routing
Routing is explicit and mode-driven via `_first_step_for_mode(...)` + `_goto_wizard_step(...)`:

- `auto_pulse`: duration → preset → max volume → max injections → readiness
- `total_target`: weekly target → duration → preset → max volume → max injections → readiness
- `stack_smoothing`: stack target(s) → duration → preset → max volume → max injections → readiness
- `inventory_constrained`: entitlement gate → inventory count(s) → duration → preset → max volume → max injections → readiness

No hidden fallback path is used between modes.

## 5) Readiness panel
Readiness is now rendered inside the same wizard panel and remains compact:

- current mode
- current preset
- key constraints
- summary status
- missing/issue list (if any)
- CTA: calculate preview

## 6) Verify commands (local)
Exact local commands used:

1. `python -m py_compile app/bots/handlers/draft.py`
2. `pytest -q tests/test_bot_draft_smoke.py -q`
3. `pytest -q tests/test_bot_search_smoke.py -q`

## 7) Canonical baseline migration status
No schema change was needed for PR W13/PR4.

Therefore, canonical baseline migration was **not modified** and no new migration chain was created.
