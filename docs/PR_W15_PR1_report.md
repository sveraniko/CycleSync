# PR W15 / PR1 — PK V2 default engine switch

## 1) Where default switched to v2

Default engine behavior is now V2 in all standard runtime entry points:

- `Settings.pulse_engine_version` default changed from `"v1"` to `"v2"` in `app/core/config.py`.
- `resolve_pulse_engine_version(settings)` now falls back to `"v2"` when unset/blank/invalid.
- `PulseCalculationEngine(...)` constructor default changed to `pulse_engine_version="v2"` so direct instantiation also aligns with live default.

This removes silent v1 defaults on the live path while preserving explicit override support.

## 2) Rollback seam design (v1 retained, non-product mode)

V1 remains available **only** through explicit operational override:

- Environment/config override: set `pulse_engine_version=v1`.
- Selector still accepts `{v1, v2}` and wires requested version to live engine.
- Added test coverage that explicit v1 override still resolves and builds v1 engine.

No user-facing engine switch UI or admin product-mode exposure was introduced in this PR.

## 3) Flows audited for hidden v1 assumptions

Reviewed and verified these flows under v2-default:

- live engine selection / runtime wiring
- preview generation and preview persistence
- activation path consuming latest preview
- input-mode execution (`auto_pulse`, `total_target`, `stack_smoothing`, `inventory_constrained`) under v2
- validation/comparison tooling (`scripts/validate_medical_v2_catalog.py`) with v2 as primary and v1 as rollback comparison

No hidden hard dependency on v1 heuristic semantics was found in these paths after default flip.

## 4) Engine traceability preservation

Engine traceability remains preserved in summary payloads:

- `pulse_engine_version_used`
- `evaluation_source`

Both fields continue to be populated from the calculation result summary and are asserted through preview persistence + activation-linked tests.

## 5) Validation/regression tooling posture update

Validation tooling now treats v2 as the primary engine:

- Scenario execution order is now v2-first.
- Payload includes:
  - `primary_engine_version: "v2"`
  - `rollback_engine_version: "v1"`
- CLI description updated to reflect v2-default with v1 rollback comparison.

V1-vs-V2 comparison output remains intact.

## 6) Exact local verification commands

Executed locally:

```bash
pytest -q tests/test_pk_v2_foundation.py tests/test_pulse_engine.py tests/test_pulse_preview_persistence.py tests/test_protocol_activation.py tests/test_medical_v2_validation_pack.py
PYTHONPATH=. python scripts/validate_medical_v2_catalog.py --out /tmp/medical_v2_validation_report.w15pr1.json --summary /tmp/medical_v2_validation_summary.w15pr1.md
```

## 7) Baseline migration policy statement

No schema changes were required for this PR.

Therefore, the canonical baseline migration was **not modified**, and no new migration chain was created.
