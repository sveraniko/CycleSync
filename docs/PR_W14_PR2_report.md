# PR W14 / PR2 — PK V2 simulator core

## 1) PK event input model
Implemented explicit typed runtime input in `app/application/protocols/pk_v2.py`:

- `PKDoseEvent`: product-level schedule event (`day_offset`, `product_id`, `product_key`, `event_volume_ml`/`event_unit_count`, `event_time_hour`).
- `PKSimulationInput`: deterministic simulator input (`product_profiles`, `dose_events`, horizon/resolution, degradation flags).
- `IngredientCurvePoint` and `SubstanceCurvePoint`: explicit simulated concentration points.
- `ProtocolPKInput` is aliased to `PKSimulationInput` for compatibility with the PR1 seam.

## 2) Per-ingredient simulation
Implemented `FirstOrderPKEngineV2` with first-order accumulation/decay:

- Decomposes each product-level event into ingredient doses via `decompose_product_dose`.
- Converts doses to active payload (`dose_mg * active_fraction`).
- Simulates contribution per ingredient across the horizon with hourly (or configurable) resolution.
- Uses `half_life_days` as decay driver (`k = ln(2)/half_life_days`).
- Applies simple rise shaping when `tmax_hours` is present, otherwise immediate-release fallback.
- Sums repeated-event contributions into final ingredient curves.

## 3) Parent-substance aggregation
Implemented true aggregation by `parent_substance`:

- Ingredient curves are summed into `substance_curves`.
- Mixed products (e.g. multiple testosterone esters) now produce real parent-level concentration series.
- Overall protocol curve is also exposed as aggregated total series.

## 4) Flatness/stability on V2 side
Added simulator-derived metrics (`PKEvaluationMetrics`):

- `peak_concentration`
- `trough_concentration`
- `peak_trough_spread_pct`
- `variability_cv_pct`
- `flatness_stability_score`

`flatness_stability_score` is now computed from the simulated series (`overall_curve`), not from weighted half-life-only approximation.

## 5) Warning flags implemented
MVP warning semantics added:

- `mixed_ester_short_component_spikes`
- `constraint_forced_longer_interval`
- `peak_trough_spread_high`
- `insufficient_resolution_fallback`
- `inventory_forced_degradation`

## 6) Live default remains v1
No behavior flip performed:

- `engine_selector.build_live_pulse_engine()` still returns v1 `PulseCalculationEngine`.
- `resolve_pulse_engine_version()` seam remains explicit and defaults to `v1`.
- Test coverage includes default-to-v1 check.

## 7) Adapter bridge for PR3
Added adapter function:

- `build_simulation_input_from_pulse_plan(...)`
- Converts existing `PulsePlanEntry` schedule lines into typed `PKDoseEvent` list for V2 simulation.
- Keeps planning flow intact while providing clean bridge for PR3 integration.

## 8) Verification commands (local)
Used:

```bash
pytest tests/test_pk_v2_foundation.py
```

## 9) Baseline migration policy
No schema change was required for this PR.

- Canonical baseline migration was **not modified**.
- No new Alembic migration chain added.
