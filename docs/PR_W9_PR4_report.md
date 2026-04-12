# PR W9 / PR4 — First live payment provider integration

## 1) Integrated provider
This PR integrates **Telegram Stars** as the first real provider via `StarsPaymentProvider` under the existing provider abstraction.

- Provider code: `stars`
- Internal free provider (`free`) remains available for zero-total and non-live flows.
- Provider-agnostic architecture is preserved through `PaymentProviderGateway` and `PaymentProviderRegistry`.

## 2) Provider init/session flow
Implemented flow:

1. Checkout is created as before.
2. User picks provider (`stars`) in Telegram checkout actions.
3. `CheckoutService.initiate_payment(...)`:
   - creates `payment_attempt` with `initiated` status,
   - emits `payment_attempt_started`,
   - calls `StarsPaymentProvider.initialize_checkout(...)`,
   - persists provider session (`payment_provider_sessions`),
   - marks attempt `pending` with provider reference,
   - emits `payment_provider_session_created`,
   - moves checkout to `awaiting_payment`.

Stars init payload includes Telegram action URL and instruction for compact Telegram UX.

## 3) Provider success -> existing fulfillment path
Implemented `CheckoutService.confirm_provider_payment(...)`.

On provider success:
1. provider confirmation returns `succeeded`,
2. attempt becomes `succeeded`,
3. checkout becomes `completed`,
4. `checkout_completed` and `payment_attempt_succeeded` are emitted,
5. existing `CheckoutFulfillmentService.fulfill_checkout(...)` runs,
6. entitlements are granted through existing access services.

No fulfillment logic is duplicated inside provider adapter.

## 4) Statuses and semantics
Supported attempt outcomes and semantics:

- `initiated` / `pending` for initialized session path,
- `succeeded` for paid completion,
- `failed`, `cancelled`, `expired` for non-success terminal outcomes.

This prevents confusion between session creation and paid settlement.

## 5) User-facing Telegram flow now available
Compact flow in bot checkout handler:

- Start checkout (`/checkout_demo`),
- Apply coupon if needed,
- Press **Pay with Stars** (provider init),
- Receive checkout with provider attempt details,
- Refresh status,
- Confirm/fail provider path using dedicated callback actions for controlled test loop.

## 6) Diagnostics / visibility
Diagnostics now include provider-level counters:

- total attempts by provider,
- succeeded by provider,
- failed/cancelled/expired by provider,
- provider registry visibility includes enabled Stars when configured.

## 7) Exact local verification commands
Run locally:

```bash
pytest -q tests/test_commerce_checkout.py tests/test_bot_checkout_smoke.py tests/test_health.py
```

## 8) Canonical baseline migration policy
No schema change was required for this PR.

- Therefore, **no new Alembic migration was created**.
- Existing canonical baseline migration chain remains single and unchanged.
- This complies with pre-MVP baseline-rewrite policy.
