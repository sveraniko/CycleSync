# PR W9 / PR1 — Commerce checkout foundation

## 1) Added checkout/payment entities

Introduced canonical billing entities in the `billing` schema:
- `billing.checkouts`
- `billing.checkout_items`
- `billing.payment_attempts`
- `billing.payment_provider_sessions`

ORM models were added in `app/domain/models/billing.py`, and baseline DDL was updated in-place in `alembic/versions/20260411_0012_baseline_consolidated.py`.

## 2) Commerce mode

Introduced explicit runtime mode `commerce_mode` with values:
- `disabled`
- `test`
- `live`

Behavior:
- `disabled`: checkout can be created/read, payment start is blocked with `checkout_mode_blocked` event.
- `test`: checkout and internal `free` settlement enabled.
- `live`: checkout flow enabled, but internal `free` settlement explicitly blocked.

Diagnostics now show commerce mode and provider registry visibility in `/health/diagnostics`.

## 3) Provider adapter layer

Added provider-agnostic abstraction:
- `PaymentProviderGateway`
- `PaymentProviderRegistry`

Responsibilities:
- initialize checkout session payload
- confirm settlement
- expose provider diagnostics

Provider payload stays within adapter/session storage (`billing.payment_provider_sessions`), while app-level state remains normalized in checkout/payment tables.

## 4) Internal `free` provider

Implemented `FreePaymentProvider` as a first-class settlement path.

Supported reason codes:
- `dev_mode`
- `gift_coupon`
- `manual_free_checkout`
- `ops_test`

`free` settlement uses normal pipeline:
- records `payment_attempt_started`
- updates attempt to succeeded
- marks checkout completed
- emits `payment_attempt_succeeded`, `checkout_completed`, and `checkout_completed_free`

No bypass/hack path is used.

## 5) User-facing checkout flow (Telegram)

Added minimal Telegram-native flow via `/checkout_demo`:
- creates checkout with one purchase item
- shows item/price/status
- allows `Settle free (test)` action
- allows status refresh action

This is intentionally compact and non-storefront.

## 6) What was intentionally NOT done in this PR

- No external payment gateway integrations yet (only internal `free`).
- No coupon/discount logic beyond stored `discount_amount` field.
- No giant billing/admin UI.
- No COD paths.

## 7) Exact local verification commands

- `pytest tests/test_commerce_checkout.py`
- `pytest tests/test_bot_checkout_smoke.py`
- `pytest tests/test_health.py`
- `pytest tests/test_db_baseline.py`

## 8) Canonical baseline migration update

Per baseline policy, schema changes were applied by editing the existing canonical baseline migration **in place**:
- `alembic/versions/20260411_0012_baseline_consolidated.py`

No new Alembic migration chain was created.
