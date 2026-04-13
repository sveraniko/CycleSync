# PR W13 / PR3 — Draft panel edit-in-place

## 1) Draft panel lifecycle now

Draft now behaves as a **single stable workspace panel** (one container message) instead of a stream of new chat messages.

- `draft_entrypoint` (`Draft` text command) renders via container helper.
- `draft:open` refreshes the same panel in-place.
- `draft:remove:*` updates the same panel in-place.
- `draft:clear:confirm` switches the same panel into confirmation mode.
- `draft:clear:yes` applies clear and re-renders the same panel.

Implementation uses `safe_edit_or_send(...)` with FSM container state, so first render sends once and subsequent actions edit the same message.

## 2) Actions that now work edit-in-place

The following Draft actions are now container/edit-in-place:

- Open Draft (`draft:open`)
- Remove item (`draft:remove:<item_id>`)
- Clear confirmation (`draft:clear:confirm`)
- Clear apply (`draft:clear:yes`)
- Refresh Draft (`Обновить Draft` -> `draft:open`)

No more `"confirmation + fresh panel"` double-message pattern for remove/clear.

## 3) Draft summary rendering changes

Draft summary was redesigned into a compact Telegram-native workspace card:

- Header: `Draft • Рабочая панель`
- Selected products count
- Clean product list with optional brand second line
- Compact settings block (human-readable RU labels)
- Explicit next step CTA (`К расчету`)

Raw internal keys like `protocol_input_mode` / `weekly_target_total_mg` are no longer shown in Draft panel text.

## 4) Remove/Clear behavior without chat spam

- **Remove:** now directly re-renders updated Draft in the same container panel.
- **Clear:** now asks confirmation **in-place** (same panel keyboard state) and applies clear **in-place**.
- No extra standalone confirmation bubbles are sent for these actions.

## 5) Draft action layout

Keyboard was regrouped for readability:

- Primary row: `К расчету` + `Обновить Draft`
- Per-item remove rows: `🗑 Удалить #N`
- Clear action row (`Очистить Draft`) or inline confirm row (`✅ Да, очистить` + `↩️ Отмена`)
- Navigation row: `◀️ К поиску`

This keeps actions structured while avoiding a noisy button wall.

## 6) Add-to-draft no-spam compatibility

`+Draft` behavior from Search remains toast-based (`callback.answer`) and does not emit chat confirmation messages.
Draft now cleanly reflects added items when opened/refreshed, preserving the no-spam pattern from W13/PR2.

## 7) Local verification commands (exact)

```bash
pytest -q tests/test_bot_draft_smoke.py tests/test_bot_search_smoke.py tests/test_bot_ui_foundation.py
```

## 8) Tests added/updated for this PR

Targeted coverage now includes:

1. Draft open uses container/edit-in-place semantics.
2. Remove item updates the same panel.
3. Clear confirm/apply works in the same panel.
4. Draft rendering smoke + human-readable labels (no internal key dump).
5. Add-to-draft remains toast/no-spam compatible (search test remains green).

## 9) Canonical baseline migration policy

**No schema change was needed in W13/PR3.**

- Canonical baseline migration was **not modified**.
- No new Alembic migration chain was created.
