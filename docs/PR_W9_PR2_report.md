# PR W9 / PR2 report — coupons / discounts / gift flow

## 1) Coupon entities introduced

В `billing` домене добавлены canonical-сущности:

- `billing.coupons`
  - `id`, `code`, `status`, `discount_type`, `discount_value`, `currency`
  - `valid_from`, `valid_to`
  - `max_redemptions_total`, `max_redemptions_per_user`
  - `redeemed_count`, `notes`, `grants_free_checkout`
  - `created_at`, `updated_at`
- `billing.coupon_redemptions`
  - `id`, `coupon_id`, `checkout_id`, `user_id`, `redeemed_at`
  - `result_status`, `result_reason_code`
  - `discount_amount`, `final_total_after_discount`
  - `created_at`, `updated_at`

Это превращает coupons в first-class commercial objects с аудируемыми redemption-записями.

## 2) Validation + application flow

Реализован единый `CheckoutService.apply_coupon_to_checkout(...)` с централизованными правилами:

1. Нормализация кода (`strip + upper`).
2. Загрузка checkout + coupon.
3. Явная проверка статусов/окон/лимитов.
4. Явный denial с reason code (без silent ignore).
5. Расчёт discount (`percent` или `fixed`) с floor в 0.
6. Обновление checkout totals.
7. Сохранение `coupon_redemption` (applied/denied).
8. Инкремент счётчика coupon (`redeemed_count`) и auto-`exhausted` на total-limit.
9. Outbox events: `coupon_applied`, `coupon_application_failed`, `coupon_redeemed`.

Дополнительно реализованы `create_coupon`, `disable_coupon`, `inspect_coupon`, `list_coupon_redemptions`.

## 3) Activation limits policy

Выбранная policy:

- `max_redemptions_total`: ограничивает общее число successful (`result_status=applied`) применений.
- `max_redemptions_per_user`: ограничивает successful-применения на пользователя.
- Лимиты считаются по `coupon_redemptions` (источник правды для аудита).
- При достижении общего лимита coupon переводится в `exhausted`.

## 4) 100% gift flow

Ключевой путь реализован без bypass:

- Coupon application выставляет `checkout.total_amount = 0`.
- Для zero-total не допускается обычный paid-init (`zero_total_requires_free_settlement`).
- Завершение идёт через реальный internal free pipeline: `settle_free_checkout(..., reason_code="gift_coupon")`.
- Для `gift_coupon` добавлена строгая проверка `total_amount == 0`.
- Сохраняются обычные коммерческие факты: payment attempt, checkout completion, `checkout_completed_free`.

## 5) Bot UX for coupons

Минимальный Telegram-native UX добавлен в checkout flow:

- Кнопка `Apply coupon`.
- Подсказка-команда: `/apply_coupon <checkout_id> <coupon_code>`.
- Ответ:
  - success: discount + new total;
  - denial: explicit reason code.
- Добавлена кнопка `Complete gift checkout` (free settlement с `gift_coupon`).

## 6) Minimal admin/dev management path

Добавлен скрипт `scripts/manage_coupons.py`:

- `create`
- `disable`
- `inspect`
- `list-redemptions`

## 7) Events added

В outbox добавлены события:

- `coupon_created`
- `coupon_applied`
- `coupon_application_failed`
- `coupon_redeemed`
- `coupon_disabled`

Событие `checkout_completed_free` продолжает использоваться на 100% gift path.

## 8) Diagnostics / visibility

Commerce diagnostics расширены полями:

- `active_coupons`
- `exhausted_coupons`
- `coupon_redemptions`
- `coupon_free_settlements`

## 9) Exact local verification commands

```bash
pytest -q tests/test_commerce_checkout.py tests/test_bot_checkout_smoke.py tests/test_db_baseline.py
```

## 10) Canonical baseline migration update (in place)

Схема обновлена **in place** в текущей canonical baseline migration:

- файл: `alembic/versions/20260411_0012_baseline_consolidated.py`
- добавлены таблицы `billing.coupons` и `billing.coupon_redemptions` + индексы/constraints
- новая migration chain **не создавалась**

Это соответствует baseline-rewrite policy: один канонический baseline без плодения цепочки миграций.
