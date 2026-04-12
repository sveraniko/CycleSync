# PR W11 / PR1 — Protocol Input Modes Foundation

## 1) Input modes introduced
Введен явный `protocol_input_mode` как отдельный слой от `calculation_preset`.

Список mode-кодов:
- `auto_pulse`
- `stack_smoothing`
- `total_target`
- `inventory_constrained`

Режимы оформлены как first-class routing layer в приложении, а не как скрытая внутренняя ветка.

## 2) Что реально работает в этом PR
Рабочие режимы расчета:
- `total_target` (текущий production-path, теперь explicit)
- `auto_pulse` (реально рабочий без обязательного `weekly_target_total_mg`)

Пока placeholder/gated:
- `stack_smoothing` (clean not-yet-available seam)
- `inventory_constrained` (clean advanced seam)

## 3) `auto_pulse` vs `total_target`
### `total_target`
Пользователь задает total weekly target mg.
Engine валидирует обязательность `weekly_target_total_mg`.
Аллокация строится от пользовательского total target.

### `auto_pulse`
Пользователь НЕ задает общий weekly target.
Engine строит per-product weekly allocation из catalog guidance (typical / guidance ranges).
Если guidance частично отсутствует — используется прозрачный fallback с quality flag.

## 4) Как mode selection встроен в bot flow
В Telegram draft-flow добавлен отдельный шаг выбора `protocol_input_mode` перед вводом параметров расчета.

Поток:
1. User нажимает «К расчету».
2. Bot показывает выбор mode:
   - Auto Pulse
   - Total Target
   - Stack Smoothing
   - Inventory Constrained
3. Для `total_target` продолжается текущий путь с вводом weekly target.
4. Для `auto_pulse` weekly target не спрашивается, flow идет сразу к duration/constraints/preset.
5. Для `stack_smoothing` и `inventory_constrained` возвращается clean coming-next сообщение (без хаотичных workaround).

## 5) Что сознательно НЕ реализовано
- Full-math реализация `stack_smoothing`.
- Full-math реализация `inventory_constrained`.
- Дополнительный hardening по providers/labs/specialist, не относящийся к scope PR.

## 6) Exact local verification commands
```bash
pytest -q tests/test_protocol_readiness.py tests/test_pulse_engine.py tests/test_bot_draft_smoke.py tests/test_pulse_preview_persistence.py tests/test_protocol_activation.py tests/test_draft_service.py
pytest -q tests/test_db_baseline.py
```

## 7) Canonical baseline migration update (in place)
Схема обновлена **in place** в существующей canonical baseline migration:
- `alembic/versions/20260411_0012_baseline_consolidated.py`

Добавлены поля `protocol_input_mode` в baseline-секции таблиц:
- `protocols.protocol_draft_settings`
- `pulse_engine.pulse_calculation_runs`
- `pulse_engine.pulse_plan_previews`
- `protocols.protocols`
- `pulse_engine.pulse_plans`

Новая цепочка миграций не создавалась; в проекте по-прежнему один baseline migration.
