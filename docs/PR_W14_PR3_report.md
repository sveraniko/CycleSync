# PR W14 / PR3 — PK V2 integration into real preview calculation flow

## Scope delivered
This PR integrates PK V2 into the actual preview evaluation path while preserving controlled rollout and explicit version switching.

Implemented outcomes:
- schedule proposal generation remains in existing planner flow (no giant rewrite);
- evaluation/metrics/warnings switch to PK V2 simulation only when `pulse_engine_version == "v2"`;
- default remains `v1`;
- preview summary and persisted payload now contain engine-version traceability;
- all current input modes continue to run through the same planner stage and then can be evaluated by V2.

## 1) How V2 is integrated into pulse calculation flow
Integration is done inside `PulseCalculationEngine.calculate(...)`:
1. existing validation/allocation/planning logic builds plan and entries as before;
2. when engine instance is configured with `pulse_engine_version="v2"`, it:
   - adapts `PulseProductProfile` to PK V2 `ProductPKProfile`/`IngredientPKProfile`;
   - adapts generated plan entries to `PKSimulationInput` via `build_simulation_input_from_pulse_plan`;
   - runs `FirstOrderPKEngineV2.calculate(...)`;
   - replaces evaluation metrics/warnings with simulated outputs.

This keeps proposal logic stable while making evaluation honest under v2.

## 2) Where engine selection happens
Engine selection is explicit in `app/application/protocols/engine_selector.py`:
- `resolve_pulse_engine_version(settings)` validates configured value against `{v1, v2}`;
- `build_live_pulse_engine(settings)` now constructs `PulseCalculationEngine(pulse_engine_version=<resolved>)`.

No silent global flip: if config is absent/invalid, resolved value remains `v1`.

## 3) Metrics now sourced from V2 when enabled
When `pulse_engine_version == "v2"`:
- `flatness_stability_score` comes from simulated `overall_curve` PK metrics;
- summary includes simulated metrics:
  - `peak_concentration`
  - `trough_concentration`
  - `peak_trough_spread_pct`
  - `variability_cv_pct`
- warning flags are merged with V2 warning semantics (`peak_trough_spread_high`, `mixed_ester_short_component_spikes`, etc.) and existing planner flags.

When `v1` is used, legacy heuristic flatness path remains active.

## 4) Warning merge behavior
Warning merge behavior remains deterministic and deduplicated:
- planner/allocation flags are collected first;
- PK V2 warnings are appended when v2 path is active;
- final result uses sorted unique warning list.

This prevents duplicate spam and keeps readability.

## 5) Engine-version traceability storage
Traceability added into preview summary payload (`summary_metrics`):
- `pulse_engine_version_used` (`v1` or `v2`)
- `evaluation_source` (`v1_heuristic` or `pk_v2_simulated`)

Additionally, v2 evaluation details are stored in allocation details under `allocation_details.pk_v2_evaluation` with compact internal diagnostics (metrics + warning flags + ingredient/substance keys).

## 6) Input modes compatibility
All modes continue to work with unchanged planner input contract:
- `auto_pulse`
- `total_target`
- `stack_smoothing`
- `inventory_constrained`

V2 evaluation runs after plan entries are produced, so mode behavior is preserved while resulting metrics become simulation-based under v2.

## 7) Local verification commands
Executed locally:
- `pytest tests/test_pk_v2_foundation.py tests/test_pulse_engine.py tests/test_pulse_preview_persistence.py`

Targeted checks include:
- v1 preview still works and remains default;
- v2 preview path works;
- v2 flatness source differs from v1 heuristic;
- mixed product under v2 emits PK-specific warning semantics;
- all four input modes produce valid v2 previews;
- preview persistence stores engine version traceability and v2-derived metrics.

## 8) Baseline migration policy
No schema change was required for this PR.

Reason:
- new traceability and v2 diagnostics are persisted through existing JSON payload fields (`summary_metrics` / `allocation_details`), so no migration update is necessary.

Therefore, canonical baseline migration was **not changed**.
