# PR_W1_PR3 — Draft Entry Foundation (Wave 1 / PR3)

## Что сделано

Реализован foundation для `Calculation Draft` между search и будущим pulse calculation:

- persistence `protocols.protocol_drafts` + `protocols.protocol_draft_items`;
- жизненный цикл draft item (`add/remove/list/clear`);
- рабочий переход `search result -> +Draft -> persisted draft`;
- отдельный entrypoint `Draft` в боте + summary view;
- seam для `continue to calculation` (stub Wave 2);
- event hooks в outbox (`draft_created`, `draft_item_added`, `draft_item_removed`, `draft_cleared`, `draft_opened`, `draft_ready_for_calculation`).

Pulse engine math в этом PR не реализуется.

## Draft model

### Таблицы

1. `protocols.protocol_drafts`
   - `id` UUID PK
   - `user_id` VARCHAR(64)
   - `status` VARCHAR(32), default `active`
   - `created_at`, `updated_at`
   - partial unique index `uq_protocol_drafts_user_active` (`user_id`) where `status='active'`

2. `protocols.protocol_draft_items`
   - `id` UUID PK
   - `draft_id` FK -> `protocols.protocol_drafts.id`
   - `product_id` FK -> `compound_catalog.compound_products.id`
   - `selected_brand` snapshot
   - `selected_product_name` snapshot
   - `notes` optional
   - `created_at`, `updated_at`
   - unique constraint `uq_protocol_draft_item_product` (`draft_id`, `product_id`)

## Duplicate policy

Выбрана **idempotent policy**: в одном активном draft один `product_id` может быть только один раз.

- повторный `+Draft` для того же продукта не создает дубль;
- пользователю возвращается сообщение, что позиция уже есть в draft;
- это закреплено уникальным constraint и логикой приложения.

## Bot UX delivered

### Search -> Draft

- Поиск показывает `Open` + `+Draft`.
- `+Draft` теперь вызывает реальный write path в `protocols`.

### Draft entrypoint

- Сообщение `Draft` открывает current draft summary.
- Summary показывает позиции и действия:
  - удалить конкретную позицию;
  - очистить весь draft (через confirm);
  - `К расчету` (stub Wave 2).

### Continue-to-calculation stub

- Кнопка `К расчету` сохраняет lifecycle seam через событие `draft_ready_for_calculation`.
- Ответ пользователю: шаг расчета будет в Wave 2.

## Что остается на Wave 2 pulse engine

- перевод draft в protocol input contract;
- валидация readiness (weekly target, duration, preset, constraints);
- запуск pulse calculation;
- preview pulse plan + confirm path;
- promotion draft -> protocol + pulse plan truth.

## Local verification commands

```bash
pytest tests/test_draft_service.py tests/test_bot_draft_smoke.py tests/test_bot_search_smoke.py tests/test_db_baseline.py
pytest
```

## Ограничения, соблюденные в PR

- не реализован pulse engine math;
- нет reminders/adherence/labs/expert/commercial;
- draft не превращается в confirmed protocol;
- dosing/frequency math не добавлялся в draft layer.
