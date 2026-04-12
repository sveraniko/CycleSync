# PR W11 / PR2 Report — stack_smoothing working mode

## 1) Как теперь задается stack composition

В `stack_smoothing` появился отдельный persistence-layer для расчётного input truth:
- таблица `protocols.protocol_input_targets`;
- на каждый выбранный в draft продукт сохраняется `desired_weekly_mg`;
- данные привязаны к `draft_id + product_id + protocol_input_mode`.

Это не checkout/cart слой, а именно расчетная truth для pulse engine.

## 2) Чем `stack_smoothing` отличается от `total_target`

- `total_target`: пользователь задаёт только общий weekly target, а engine перераспределяет по продуктам.
- `stack_smoothing`: пользователь задаёт weekly mg по каждому продукту; engine **не перераспределяет** состав, а использует его как фиксированный mix.

Derived total weekly mg в `stack_smoothing` вычисляется как сумма введённых per-product значений и показывается в summary.

## 3) Чем `stack_smoothing` отличается от `auto_pulse`

- `auto_pulse` синтезирует per-product weekly mg автоматически из guidance/fallback логики.
- `stack_smoothing` вообще не синтезирует состав, а принимает его напрямую от пользователя.

Итог: в `stack_smoothing` состав пользовательский, в `auto_pulse` — алгоритмический.

## 4) Telegram flow

Минимальный Telegram-native flow:
1. `Draft` -> `К расчету` -> выбор `Stack Smoothing`.
2. Бот показывает текущий stack composition и просит `desired_weekly_mg` для каждого выбранного продукта.
3. После ввода stack composition бот продолжает обычный pipeline:
   - `duration_weeks`
   - preset (`unified_rhythm` / `layered_pulse` / `golden_pulse`)
   - `max_injection_volume_ml`
   - `max_injections_per_week`
4. Readiness screen + кнопка перерасчёта preview.
5. Preview показывает mode, per-product weekly mg, derived total weekly mg и предупреждения.

Добавлена кнопка `Редактировать stack composition` на readiness-экране.

## 5) Какие данные теперь сохраняются в draft / preview / protocol

### Draft
- `protocol_draft_settings.protocol_input_mode = stack_smoothing`;
- `protocol_input_targets` хранит per-product `desired_weekly_mg`.

### Preview
- `settings_snapshot_json` теперь включает `stack_input_targets_mg`;
- summary содержит per-product weekly mg и derived total.

### Active protocol promotion
- mode продолжает переноситься как `protocol_input_mode` через существующий lifecycle;
- snapshot остаётся в protocol/pulse-plan truth.

## 6) Validation и engine behavior

### Validation (mode-aware)
Для `stack_smoothing` обязательно:
- есть selected products;
- для каждого selected product есть `desired_weekly_mg > 0`;
- заполнены duration/max volume/max injections/preset.

Нет silent fallback в `total_target`/`auto_pulse`.

### Engine path
Для `stack_smoothing`:
- engine читает `protocol_input_targets`;
- формирует `allocation_mode = stack_input_fixed`;
- берёт per-product weekly mg **ровно как введено пользователем**;
- применяет выбранный preset только для pulse layout/smoothing.

## 7) События

Сохранена компактная event-модель:
- `protocol_input_mode_selected`;
- `stack_input_updated`;
- `protocol_calculation_requested`.

Preview events остаются существующими, в контекст включен `protocol_input_mode`.

## 8) Canonical baseline migration обновлен in place

Согласно baseline policy:
- новая migration chain **не создавалась**;
- обновлён текущий canonical baseline migration `alembic/versions/20260411_0012_baseline_consolidated.py` in place;
- добавлена таблица `protocols.protocol_input_targets` и индекс `ix_protocol_input_targets_draft_mode`.

В проекте остаётся один baseline migration.

## 9) Exact local verification commands

```bash
pytest -q tests/test_pulse_engine.py tests/test_protocol_readiness.py tests/test_draft_service.py tests/test_pulse_preview_persistence.py tests/test_protocol_activation.py tests/test_bot_draft_smoke.py tests/test_db_baseline.py
```

