# PR W11 / PR3 report — inventory_constrained as paid advanced mode

## 1) Как задается inventory input

В PR добавлен отдельный first-class слой входных данных `protocols.protocol_inventory_constraints`.

- persistence truth: `protocols.protocol_inventory_constraints`
- запись на каждый product в draft в контексте `protocol_input_mode=inventory_constrained`
- поля:
  - `id`
  - `draft_id`
  - `product_id`
  - `protocol_input_mode`
  - `available_count`
  - `count_unit`
  - `created_at`, `updated_at`

Инвентарь сохраняется через новые application/repository контракты `upsert_inventory_constraints` / `list_inventory_constraints` и используется как вычислительная truth, а не как заметка.

## 2) Какая packaging semantics используется (MVP)

Реализована одна четкая MVP-семантика:

- пользователь вводит остаток в native product count: `<count> <unit>`
- injectable MVP:
  - `package_kind in {vial, ampoule}`
  - ожидаемый unit: `vial|ampoule` (с plural-вариантами)
  - required metadata: `concentration_mg_ml` + `volume_per_package_ml`
  - derive: `available_active_mg = available_count * concentration_mg_ml * volume_per_package_ml`
- tablet/capsule MVP:
  - `package_kind in {tablet, capsule}`
  - expected unit: `tablet|capsule` (с plural-вариантами)
  - required metadata: `unit_strength_mg`
  - derive: `available_active_mg = available_count * unit_strength_mg`

Если package-kind/unit/metadata недостаточны — расчет падает в явную validation failure с кодом `inventory_metadata_insufficient:<product_id>`.

## 3) Как inventory влияет на calculation

Для режима `inventory_constrained` в engine добавлен отдельный allocation path:

1. строится ideal baseline через `auto_pulse`-распределение;
2. по каждому продукту считается верхняя граница weekly mg из инвентаря:
   - `max_weekly_mg = available_active_mg / duration_weeks`;
3. фактический target ограничивается hard cap:
   - `allocated_weekly_mg = min(ideal_weekly_mg, max_weekly_mg)`.

Итог:

- режим честно best-effort;
- если есть срезание ideal-целей из-за stock, добавляются constrained флаги;
- preview содержит inventory-derived diagnostics (`entered counts`, `derived active mg`, `duration_fully_covered`, `feasibility_signal`).

## 4) Как mode gated as paid advanced

`inventory_constrained` теперь gated через central access/evaluator path:

- entitlement code: `inventory_constrained_access`
- бот-флоу при выборе режима:
  1. `AccessEvaluationService.evaluate(..., entitlement_code="inventory_constrained_access")`
  2. при deny — clean message и остановка flow
  3. при allow — вход в inventory input flow

Гейтинг сделан не ad-hoc в random handlers, а через существующий access service.

## 5) Какая warning/degradation semantics добавлена

Добавлены и/или задействованы explicit сигналы:

- validation:
  - `inventory_missing_for_some_products`
  - `inventory_metadata_insufficient:<product_id>`
  - `inventory_available_count_invalid:<product_id>`
- runtime constrained warnings:
  - `inventory_mode_best_effort`
  - `inventory_insufficient_for_requested_duration`
  - `inventory_forced_degraded_layout`

Preview summary теперь явно показывает, что это constrained planning, включая feasibility.

## 6) Что сознательно НЕ делалось в этом PR

- не реализован full package purchase estimator;
- не добавлялся checkout/procurement UI;
- не смешивалась логика `inventory_constrained` и `stack_smoothing`;
- не строилась новая цепочка миграций (baseline policy сохранен).

## 7) Exact local verification commands

```bash
pytest -q tests/test_draft_service.py tests/test_pulse_engine.py tests/test_protocol_readiness.py tests/test_access_entitlements.py tests/test_bot_draft_smoke.py tests/test_pulse_preview_persistence.py tests/test_protocol_activation.py
pytest -q tests/test_db_baseline.py
```

## 8) Как обновлен canonical baseline migration in place

Сделаны in-place изменения в `alembic/versions/20260411_0012_baseline_consolidated.py` (без создания новой migration chain):

- добавлен entitlement seed `inventory_constrained_access`;
- расширена таблица `compound_catalog.compound_products` packaging-полями:
  - `package_kind`
  - `units_per_package`
  - `volume_per_package_ml`
  - `unit_strength_mg`
- добавлена таблица `protocols.protocol_inventory_constraints` + уникальный ключ + индекс.

В проекте по-прежнему остается единый canonical baseline migration.
