# PR W16 / PR5 — Runtime & Commerce Clarity Surface

## 1) Added/clarified runtime/admin surfaces

Implemented a product-readable admin runtime panel in `admin:panel` with explicit blocks:
- **Runtime status** (`commerce_enabled`, `debug_enabled`, `pulse_engine_version`, `launch_mode`, catalog sync last status).
- **Commerce controls** with explanation of visible product impact.
- **Debug controls** with explanation of what debug mode unlocks and for whom.
- **Navigation map** to runtime/catalog/media/source/commercial entrypoints.

Also added a dedicated **debug toggle** (`admin:debug:toggle`) next to commerce toggle.

## 2) How `commerce_enabled` now affects visible behavior

When `commerce_enabled=OFF`:
- `/checkout_demo` returns explicit “disabled” message.
- `checkout:demo:start` callback is blocked with alert.
- Settings keyboard does **not** show checkout demo entrypoint.

When `commerce_enabled=ON`:
- Checkout demo entrypoint appears in Settings.
- Demo checkout flow can be started and used.

Admin panel now explicitly states this effect in human wording (not raw flag dump).

## 3) How `debug_enabled` now affects visible behavior

`debug_enabled` is now runtime-mutable via admin panel and immediately reused by checkout handlers.

When `debug_enabled=OFF`:
- debug checkout actions are hidden/inaccessible.

When `debug_enabled=ON`:
- debug checkout actions become available **only** for admin users (existing role seam preserved).

Admin panel explains that debug actions are admin-only and test/demo paths depend on debug mode.

## 4) Discoverable entrypoints now visible

Added coherent entrypoints in Settings:
- `🔐 Activate key` (`access:activate:start`) — always visible.
- `🧾 Checkout demo` (`checkout:demo:start`) — visible only when commerce is enabled.

This makes access/commercial actions discoverable in UI instead of hidden command knowledge.

## 5) Exact local verification commands

Executed locally:

```bash
pytest -q tests/test_bot_checkout_smoke.py tests/test_bot_admin_runtime_smoke.py
pytest -q tests/test_bot_checkout_smoke.py tests/test_bot_admin_runtime_smoke.py tests/test_bot_search_smoke.py -q
python -m py_compile app/bots/handlers/admin.py app/bots/handlers/checkout.py app/bots/handlers/settings.py app/bots/handlers/access_keys.py app/run_bot.py
```

## 6) Baseline migration policy

No schema changes were required for this PR.

- Canonical baseline migration was **not modified**.
- No new Alembic migration chain was created.

