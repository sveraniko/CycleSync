# PR W3 / PR2 — Pulse Engine Math Precision Upgrade

## 1) Effective half-life calculation update

`_effective_half_life(product)` now resolves product half-life via **weighted composition math** instead of naive mean.

### New resolution logic
1. Use only ingredients with positive `half_life_days`.
2. Use `amount_mg` as base weight when `amount_mg > 0`.
3. Apply pulse-driver multiplier (`1.15x`) when `is_pulse_driver=True`.
4. Compute weighted mean from usable rows.
5. Fallback path:
   - if weighted inputs unavailable but positive half-lives exist -> arithmetic mean fallback;
   - if no usable half-life -> deterministic default `3.0` days.

### Persisted diagnostics
For every preview, we now persist:
- per-product effective half-life value;
- per-product half-life resolution mode (`amount_weighted` / `arithmetic_fallback` / `default_fallback`);
- aggregate `effective_half_life_mode` and `half_life_resolution_quality`.

---

## 2) Guidance boundary evaluation after allocation

Allocation still computes `per_product_mg`, but now a second deterministic boundary pass evaluates each product against expected guidance bands.

### Per-product boundary fields
- `allocated_mg_week`
- `expected_min_mg_week`
- `expected_max_mg_week`
- status: `in_range` / `below_range` / `above_range` / `no_guidance`

### Aggregate diagnostics
- `guidance_band_fit_score` (share of evaluated products in-range)
- `boundary_summary`:
  - evaluated products
  - in-range count
  - below-range count
  - above-range count

### New quality flags
- `allocation_below_guidance_for_some_products`
- `allocation_above_guidance_for_some_products`
- `allocation_outside_guidance_band`

No aggressive auto-correction is introduced in this PR; diagnostics are explicit and deterministic.

---

## 3) `golden_pulse` optimization strengthening

`golden_pulse` now runs a **deterministic bounded local optimization** over phase offsets:

- objective: maximize flatness score (lower variance proxy);
- method: greedy local search over candidate phase offsets per product;
- deterministic constraints:
  - fixed pass cap (3);
  - no randomness;
  - no stochastic methods;
- safety rule: if no improvement, revert to original phases.

### Optimization outputs
- `optimization_applied` (true only on meaningful gain)
- `optimization_gain`
- `optimization_flatness_before`
- `optimization_flatness_after`

No fake claims are emitted when gain is absent.

---

## 4) New math diagnostics in preview summary/persistence

Added/expanded summary diagnostics:
- `guidance_band_fit_score`
- `effective_half_life_mode`
- `half_life_resolution_quality`
- `optimization_applied`
- `optimization_gain`

Expanded allocation details for audit/debug:
- per-product allocated mg/week
- per-product guidance band result
- per-product effective half-life + resolution mode
- allocation mode and weights
- boundary summary

---

## 5) Current model limitations

Still intentionally out of scope in this PR:
- reminders execution/runtime;
- adherence state changes;
- lab/expert/commercial layers;
- black-box global optimization;
- user-manual low-level per-product mg editing.

The optimizer is local and bounded (MVP deterministic realism), not a full combinatorial solver.

---

## 6) Closed in this PR vs deferred

### Closed now
- Weighted mixed-product half-life math with explicit fallback modes.
- Post-allocation boundary validation and scoring.
- Stronger deterministic `golden_pulse` optimization step with no-regression behavior.
- Rich preview diagnostics for trust/audit/debug.
- Event semantics remain clean (`generated`/`regenerated`/`failed`).

### Deferred to next PR(s)
- Execution/reminder orchestration.
- Runtime adaptive correction loops.
- Advanced optimization regimes beyond deterministic local search.
