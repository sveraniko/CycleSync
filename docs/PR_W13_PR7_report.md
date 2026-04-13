# PR W13 / PR7 — Checkout & Access UX Launch-Readiness

## 1) Checkout panel architecture (single-panel)

- Checkout UI is now rendered as a compact panel card (`🧾 Checkout`) with:
  - offer title
  - human-readable status
  - amount/discount/total line
  - settlement mode
  - provider attempt summary
  - fulfillment/access result summary
- Entry and lifecycle refreshes use panel updates (`safe_edit_or_send`) instead of spawning noisy extra messages.
- Provider init/confirm/fail and status refresh update the same panel with short notices.

## 2) Debug/admin actions hidden or gated

- Debug actions are no longer part of the default checkout keyboard.
- Debug actions are added only when `show_debug_actions=True`.
- Visibility is gated via the central permissions seam (`can_view_debug(...)`) using injected `admin_ids` + `debug_enabled`.
- Non-admin users do not see or execute debug callbacks (`free`, `gift`, provider fail simulation).

## 3) Coupon input flow (panel-native)

- Removed command-instruction UX for coupons.
- Added panel button **Apply coupon** → sets FSM state `CheckoutState.waiting_coupon_code`.
- User enters coupon code as a normal message.
- Input message is cleaned up (`delete_user_input_message`).
- Checkout panel updates with:
  - success notice with discount and new total, or
  - rejection notice with reason and unchanged total.

## 4) Access key UX changes

- Activation entry now opens a compact product-style panel prompt.
- Success/failure responses are cleaner and user-facing (non-technical wording).
- User key input message is cleaned up after processing.
- Access grants are rendered with readable labels.

## 5) Exact local verification commands

```bash
pytest -q tests/test_bot_checkout_smoke.py tests/test_bot_access_key_smoke.py tests/test_commerce_checkout.py
```

## 6) Canonical baseline migration policy

- No schema/domain storage change was required for this PR.
- Canonical baseline migration was **not modified**.
