# PR W13 / PR5 Report — Post-calculation UX polish

## Scope delivered
This PR finalizes the remaining post-calculation UX debt for the Draft lifecycle:
- preview rendering
- pre-start estimate snapshot
- activation transition
- active protocol summary
- course estimate rendering
- panel-driven callback transitions across this chain

## 1) Post-calculation views polished
Polished views:
1. Preview card (`_render_preview_summary`)
2. Pre-start estimate checkpoint (`_render_pre_start_estimate_snapshot`)
3. Activation target state card (`_render_active_protocol_summary`)
4. Course estimate card (`_render_course_estimate`)

What changed at UX level:
- compact card structure instead of dump-like output
- user-facing wording instead of internal field names
- compact decimal formatting via `format_decimal_human(...)`
- no raw UUID/internal-key noise in rendered user text

## 2) Callback flows now panel-driven
The following callbacks now use panel lifecycle (`safe_edit_or_send`) instead of spawning extra `callback.message.answer(...)` bubbles:
- `draft:calculate:run` (preview render keeps same panel)
- `draft:activate:prepare:*` (preview -> pre-start checkpoint)
- `draft:activate:confirm:*` (pre-start -> active protocol)
- `draft:estimate:preview:*` (estimate from preview, panel update)
- `draft:estimate:active:latest` (estimate from active protocol, panel update)

Result: preview -> pre-start -> activation -> active -> estimate behaves as one coherent journey.

## 3) Preview rendering changes
Preview now includes compact product-grade blocks:
- header with status/mode/preset
- key metrics (flatness, injections/week, max volume)
- compact per-product summary (human aliases)
- compact schedule preview (first events only)
- warnings block in normalized wording

Preview removed dump behavior:
- raw internal keys (e.g. `protocol_input_mode`) are not shown
- raw UUIDs are not shown as product identifiers
- raw high-precision decimals are normalized

## 4) Active protocol rendering changes
Active protocol card now provides:
- compact activation header
- status/mode/preset/duration/weekly target
- concise metrics block
- concise action-oriented next-step copy

Removed technical/developer tone and internal dump semantics.

## 5) Course estimate rendering changes
Course estimate now provides:
- compact top summary (source, mode, duration, counts)
- readable per-product rows
- clear status wording:
  - covers course
  - insufficient for full duration
  - estimation unavailable
- normalized numeric formatting for mg/ml/package counts
- clearer inventory comparison wording

Source distinction preserved and humanized:
- preview-based => "по preview"
- active-protocol-based => "по активному протоколу"

## 6) Exact local verification commands
Commands run locally:
1. `pytest -q tests/test_bot_draft_smoke.py`
2. `pytest -q tests/test_course_estimator.py tests/test_protocol_activation.py`

## 7) Baseline migration policy
No schema/data-model change was required for this PR.

Therefore, canonical baseline migration was **not modified** and no new Alembic migration chain was created.
