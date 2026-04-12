# PR W9 / PR3 report — checkout fulfillment / offer mapping / entitlement delivery

## 1) Offer / fulfillment entities introduced

В canonical billing-модели добавлены first-class сущности:

- `billing.sellable_offers`
  - `id`, `offer_code`, `title`, `status`, `currency`, `default_amount`, `description`, `created_at`, `updated_at`
- `billing.offer_entitlements`
  - `id`, `offer_id`, `entitlement_code`, `grant_duration_days`, `qty`, timestamps
- `billing.checkout_fulfillments`
  - `id`, `checkout_id`, `fulfillment_status`, `fulfilled_at`, `result_payload_json`, `error_code`, `error_message`, timestamps

Также `billing.checkout_items` теперь хранит структурную ссылку на оффер:
- `offer_id`
- `offer_code`

## 2) Как checkout теперь связан с real purchased access

Checkout item больше не является «только текстовой строкой». При создании checkout:

1. `CheckoutItemCreate` принимает `offer_code`;
2. offer резолвится через `sellable_offers`;
3. в item сохраняются `offer_id/offer_code` и snapshot цены/названия;
4. grant-логика берёт entitlement mapping из `offer_entitlements`.

Итог: коммерческий flow привязан к структурной product-семантике, а не к `title`.

## 3) Fulfillment trigger

Триггер реализован в точке завершения settlement:

- после успешного free-settlement (`settle_free_checkout`) вызывается единый `CheckoutFulfillmentService.fulfill_checkout(...)`;
- источники settlement (dev free / gift coupon zero-total / future paid) разделены, но fulfillment path общий.

Provider-specific слой не содержит дублирующей логики entitlement grant.

## 4) Idempotency strategy

Идемпотентность реализована двумя уровнями:

1. fulfillment-level:
   - `billing.checkout_fulfillments` имеет unique `checkout_id`;
   - при повторном вызове, если статус уже `succeeded`, возврат existing result без повторных grant.

2. grant-level:
   - `SqlAlchemyAccessRepository.create_grant(...)` проверяет existing active grant по
     `user_id + entitlement_code + granted_by_source + source_ref`;
   - при совпадении возвращается существующий grant (вместо повторной вставки).

Это исключает двойную выдачу entitlements для одного checkout.

## 5) Free / gift / completed checkout через один fulfillment path

Оба сценария идут одинаково:

- normal free settlement (`reason_code=dev_mode`)
- gift-coupon zero-total settlement (`reason_code=gift_coupon`)

В обоих случаях:
- checkout -> `completed`
- затем тот же `CheckoutFulfillmentService`
- одинаковый audit trail в `checkout_fulfillments` + outbox events.

## 6) Entitlements from checkout (existing access layer)

Fulfillment не обходит access домен:

- выдача делается через `AccessEvaluationService.grant(...)`;
- `granted_by_source = "checkout"`;
- `source_ref` стабилен и включает checkout + offer + entitlement;
- `expires_at` вычисляется из `offer_entitlements.grant_duration_days`.

## 7) Events added

Добавлены/используются события:

- `checkout_fulfillment_started`
- `checkout_fulfillment_succeeded`
- `checkout_fulfillment_failed`
- `offer_entitlement_granted`
- existing `entitlement_granted` остаётся в access grant path.

## 8) User-facing confirmation / audit read path

Bot checkout status теперь показывает fulfillment блок:

- fulfillment status
- fulfilled timestamp
- список unlocked entitlements
- expiry (если есть)

Также добавлена команда `/offers` для минимального read path активных офферов.

## 9) Exact local verification commands

```bash
pytest -q tests/test_commerce_checkout.py tests/test_bot_checkout_smoke.py tests/test_db_baseline.py
```

## 10) Canonical baseline migration updated in place

Политика baseline-rewrite соблюдена:

- изменён **только** текущий canonical baseline:
  - `alembic/versions/20260411_0012_baseline_consolidated.py`
- добавлены offer/fulfillment таблицы, новые поля checkout_items и seed офферов/маппинга;
- новая migration chain **не создавалась**.
