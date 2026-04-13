# PR_W14_PR1_report

## 1) PK V2 runtime/domain entities introduced

Implemented ingredient-aware PK V2 foundation in runtime/domain:

- `compound_catalog.compound_products`
  - added `product_key` (canonical workbook join key).
- `compound_catalog.compound_ingredients`
  - added `parent_substance`, `ester_name`, `amount_per_ml_mg`, `amount_per_unit_mg`, `active_fraction`, `tmax_hours`, `release_model`, `pk_notes`;
  - retained existing guidance and pulse-driver fields;
  - ingredient identity upgraded to include ester dimension.
- new PK V2 runtime seam models in `app/application/protocols/pk_v2.py`:
  - `IngredientPKProfile`
  - `ProductPKProfile`
  - `ProtocolPKInput`
  - `IngredientDose`
  - `PKCurveResult`
  - `SubstanceCurveResult`
  - `PKEngineV2` protocol interface.

## 2) V2 workbook ingredient ingest path

Added `app/application/catalog/v2_ingest.py`:

- reads V2 sheets (`Products`, `Ingredients`, `Sources`, `Media`, `Aliases`) from `docs/medical_v2.xlsx`;
- maps ingredient rows into first-class `IngredientInput` with PK-critical fields;
- enforces hard validation for PK-critical constraints:
  - `product_key` linkage,
  - valid `basis` (`per_ml` / `per_unit`),
  - required `half_life_days`,
  - required `active_fraction`,
  - required dose amount matching basis,
  - product must have at least one ingredient row,
  - orphan ingredient detection;
- builds product payloads with alias/media references;
- `CatalogIngestService` was extended with `run_from_products(...)` to support pre-composed V2 product aggregates.

Notes for this foundation PR:
- focus is PK-critical ingredient ingest and deterministic validation;
- `Sources` sheet parsing is wired at workbook-read level, with full source-layer persistence reserved for follow-up PRs.

## 3) Decomposition layer

Introduced deterministic decomposition utilities in `app/application/protocols/pk_v2.py`:

- `decompose_product_dose(...)`
  - injectable: `event_volume_ml * amount_per_ml_mg`
  - unit-based: `event_unit_count * amount_per_unit_mg`
- one product event can produce multiple ingredient contributions (mixed products supported).

## 4) Parent-substance grouping seam

Added `group_doses_by_parent_substance(...)` in `pk_v2.py`:

- aggregates ingredient-level doses by `parent_substance`;
- prepares the seam for PR2 to aggregate per-ingredient curves into parent-substance curves.

## 5) Keeping current engine as default

Added explicit config seam:

- `Settings.pulse_engine_version` (`v1` default)
- `app/application/protocols/engine_selector.py`
  - `resolve_pulse_engine_version(...)`
  - `build_live_pulse_engine(...)`

Current live engine remains v1 (`PulseCalculationEngine`).
No behavior flip to incomplete V2 simulation was done.

## 6) Exact local verification commands

Executed locally:

```bash
pytest -q tests/test_catalog_v2_ingest_foundation.py tests/test_pk_v2_foundation.py tests/test_catalog_ingest_idempotent.py tests/test_catalog_mapping.py
```

## 7) Canonical baseline migration update in place

Per baseline policy, no new Alembic chain was created.
Updated existing canonical baseline migration in place:

- `alembic/versions/20260411_0012_baseline_consolidated.py`
  - added PK V2 foundation columns (`product_key`, ingredient PK fields) directly in baseline schema definition.

