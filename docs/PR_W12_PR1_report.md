# PR W12 / PR1 report — package/course estimator core

## 1) Как estimator считает потребность на курс

Добавлен отдельный `CourseEstimatorService` как central application service (без размазывания логики по handlers/UI).

Источник truth выбирается явно:
- `estimate_from_preview(preview_id)` — считает по `pulse_plan_preview_entries`;
- `estimate_from_active_protocol(protocol_id)` — считает по `pulse_plan_entries` активного `pulse_plan`.

Алгоритм расчета потребности:
1. берутся фактические plan entries (а не weekly approximation);
2. агрегируется по `product_id`:
   - `required_active_mg_total = Σ computed_mg`
   - `required_volume_ml_total = Σ volume_ml`
3. формируется first-class structured result `CourseEstimate` + `CourseEstimateLine`.

## 2) Как происходит conversion в package semantics

На основе catalog packaging metadata (`package_kind`, `volume_per_package_ml`, `units_per_package`, `unit_strength_mg`) реализована package-aware конверсия:

- Injectable (`vial`, `ampoule`):
  - используется `required_volume_ml_total`;
  - `package_count_required = required_volume_ml_total / volume_per_package_ml`.

- Tablet/Capsule (`tablet`, `capsule`):
  - `required_unit_count_total = required_active_mg_total / unit_strength_mg`;
  - `package_count_required = required_unit_count_total / units_per_package`.

Во всех случаях:
- `package_count_required` хранит fractional/internal значение;
- `package_count_required_rounded = ceil(package_count_required)` для честного количества упаковок без скрытого округления.

## 3) Как устроен inventory comparison

Estimator не зависит от обязательного инвентаря и всегда работает.

Если inventory constraints присутствуют:
- выполняется сравнение `available_package_count` vs `package_count_required_rounded`;
- выставляется `inventory_sufficiency_status`:
  - `sufficient`
  - `insufficient`
  - `unknown` (например, когда package estimate не удалось построить)
  - `not_applicable` (если inventory не передан)
- считаются derived поля:
  - `shortfall_package_count`
  - `shortfall_active_mg` (когда возможно вычислить available active mg).

## 4) Packaging ограничения MVP

Estimator сознательно не делает fake precision и возвращает явные предупреждения/статусы при неполной metadata:
- `packaging_metadata_missing`
- `units_per_package_missing`
- `volume_per_package_missing`
- `package_estimation_not_supported`
- `product_metadata_missing`

В таких случаях line получает `estimation_status=unsupported` и comparison может быть `unknown`.

## 5) Что сознательно НЕ делалось в этом PR

- не делался shopping list;
- не делался procurement/checkout UI;
- не добавлялась логика «докупить в один клик»;
- estimator не смешивался с planner-поведением `inventory_constrained` (только честный расчет/сравнение);
- не добавлялась тяжелая persistence snapshot-модель для estimator (on-demand structured result).

## 6) Exact local verification commands

```bash
pytest -q tests/test_course_estimator.py tests/test_protocol_activation.py
```

Покрыты таргетные кейсы:
1. injectable package estimation;
2. tablet/capsule package estimation;
3. rounded package count;
4. inventory sufficient;
5. inventory insufficient;
6. missing packaging metadata warning;
7. preview source estimation;
8. active protocol source estimation.

## 7) Как updated canonical baseline migration in place

В этом PR schema change не потребовался, поэтому canonical baseline migration **не изменялся**.

- новых Alembic migration файлов не создавалось;
- в проекте остается один baseline migration: `alembic/versions/20260411_0012_baseline_consolidated.py`.
