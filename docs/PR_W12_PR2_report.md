# PR W12 / PR2 — Course Estimator in User-Facing Protocol Flow

## 1) Preview flow integration
Estimator is now directly exposed in preview UX:
- After `pulse plan preview` generation, preview actions include `Course estimate`.
- This action builds estimate from **preview source** (`estimate_from_preview(preview_id)`), not from active protocol.
- Rendering includes compact summary + per-product lines with required active mg, required ml/units, package kind, rounded package count, and inventory sufficiency/shortage when available.

## 2) Pre-start flow integration
Start flow is now two-step with explicit pre-start estimate visibility:
- `Start protocol` now opens a **pre-start course estimate snapshot** (source = preview).
- Snapshot explicitly shows whether inventory covers course duration or is insufficient for full duration.
- Start remains non-blocking (as requested): user can confirm via `Confirm start`.
- No hidden semantics: insufficiency warning is visible before confirmation.

## 3) Active protocol estimate access
Added read-path for active protocol:
- After activation, active protocol message includes `Course estimate` action.
- Bot also supports `draft:estimate:active:latest` flow, loading estimate from **active protocol source** (`estimate_from_active_protocol(protocol_id)`).
- Output clearly labels source as active-protocol-based.

## 4) Rendering for insufficiency / unsupported cases
Telegram-native renderer added for course estimates:
- Compact summary block: source, mode, duration, total products, inventory comparison, insufficiency count, unsupported count, covered/not covered counters.
- Per-product lines include:
  - product name
  - required active total mg
  - required form total (ml or units, or unknown)
  - package kind
  - required package count (with rounded value) or `estimation unavailable`
  - available package count (if inventory exists)
  - status (`covers course` / `insufficient for full duration` / `estimation unavailable`)
  - explicit shortage line for insufficient products
  - warning codes when packaging metadata is unsupported/missing.

## 5) What was intentionally NOT done in this PR
- No shopping list flow.
- No procurement/checkout integration.
- No “buy missing items” actions.
- No hard start-blocking by inventory insufficiency.
- No inventory planner overbuild beyond estimator presentation and transparency.

## 6) Exact local verification commands
- `pytest -q tests/test_bot_draft_smoke.py tests/test_course_estimator.py`

## 7) Canonical baseline migration update policy
- This PR required no DB schema changes.
- Therefore, canonical baseline migration remained unchanged **in place**.
- Project still keeps a single baseline migration chain (`alembic/versions/20260411_0012_baseline_consolidated.py`) with no new migration added.
