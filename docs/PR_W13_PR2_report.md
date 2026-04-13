# PR W13 / PR2 — Search panel + Product card UX redesign

## 1) Search panel architecture

Search flow in `app/bots/handlers/search.py` is now single-panel and callback-driven:

- text query triggers `search_entrypoint(...)`;
- results are rendered as one compact panel via `safe_edit_or_send(...)`;
- panel header includes query echo, total count, page indicator;
- every result row is compact and readable (name, brand, form, short composition preview);
- callback navigation (`open`, `+Draft`, `next/prev`, `back`) edits the same container panel.

This removes the old one-result-per-message pattern and prevents chat flooding.

## 2) Product card architecture

Product card is rebuilt as structured HTML card with grouped sections:

- bold product name;
- compact brand + form lines;
- dedicated composition block;
- no internal IDs/UUIDs in card text;
- no raw dump of URL strings in body text.

Card rendering is handled by `_render_product_card(...)` and posted with HTML parse mode through the flow helpers.

## 3) Added toggles and buttons

Card includes toggle-based secondary sections (in-place edit, no extra message):

- `Show/Hide authenticity`
- `Show/Hide media`
- `Show/Hide sources`

Also added URL buttons using `InlineKeyboardButton(..., url=...)`:

- `Official`
- `Source 1..N` (from media/source links)

Main card body intentionally avoids raw URLs.

## 4) Back to results behavior

`Back to results` returns user from card to the previous search panel page without forcing a fresh query round-trip.

State preservation strategy:

- query + total + current page + current page items are cached in FSM state (`SEARCH_STATE_KEY`);
- `search:back` re-renders results from cached page context and edits the same container message.

## 5) Chat spam reduction

Implemented anti-spam changes:

- search and card navigation are panel edits instead of new message bursts;
- pagination and section toggles are in-place edits;
- `search:draft:*` now uses `callback.answer(...)` toast confirmations (`Добавлено в Draft` / `Уже есть в Draft`) and does not create extra chat messages.

## 6) Exact local verification commands

Executed locally:

1. `pytest -q tests/test_bot_search_smoke.py tests/test_bot_ui_foundation.py`

## 7) Baseline migration policy

No schema changes were required for this PR.

Canonical baseline migration was **not modified**.
