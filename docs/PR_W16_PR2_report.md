# PR W16 / PR2 — Product-grade media UX for product card

## Scope
This PR ports the **media interaction pattern** from TradeFlow into CycleSync's current card/catalog runtime model, without copying unrelated TradeFlow modules.

Implemented here:
- media hub/toggle UX in the product card panel;
- deterministic primary cover resolver;
- UI display mode seam (`none`, `on_demand`, `show_cover_on_open`);
- real media presentation (typed, counted, navigable), not raw refs;
- strict source/media surface separation preserved.

Intentionally deferred:
- full admin media manager/policy editor UI;
- persistent per-product display mode admin controls.

---

## 1) What TradeFlow media pattern was ported conceptually
Ported concept (adapted to CycleSync):
1. Media interaction is a **separate card state** (gallery hub), not mixed with source links.
2. Product card has **intentional media access** via `Show media` / `Hide media`.
3. Gallery has **stateful navigation** (`Prev media` / `Next media`) in panel callbacks.
4. Card renders a compact media summary first, then detailed gallery state when opened.
5. Media and sources are rendered as **three distinct surfaces**:
   - Official URL button
   - Source buttons
   - Media hub/gallery and media link actions

This keeps the TradeFlow interaction spirit while matching CycleSync's `OpenCard.media_items` DTO.

---

## 2) Cover resolution logic
Primary cover resolver is deterministic and policy-aware:
1. `manual` item with `is_cover=true` (if allowed by current media policy)
2. `import` item with `is_cover=true` (if allowed)
3. highest-priority active media from effective gallery
4. no cover

Policy seam (UI/runtime) currently supports:
- `import_only`
- `manual_only`
- `prefer_manual`
- `merge`

If policy is missing/invalid, resolver safely falls back to `merge`.

---

## 3) Media display mode behavior
Implemented UI-level display mode resolver:
- `none`
- `on_demand`
- `show_cover_on_open`

Behavior:
- If mode resolves to `show_cover_on_open` and cover exists, card shows explicit cover block on open.
- If mode resolves to `on_demand`, card shows availability hint and opens media via toggle.
- If no media exists, card shows truthful `Нет медиа-файлов.` state.
- If mode is absent/invalid, fallback is `on_demand` (clean temporary strategy until admin persistence lands).

---

## 4) Product card media UX changes
### Before
- Media section was close to abstract refs/placeholders.
- Toggle had little practical value.

### Now
- Card always includes truthful media availability block.
- `Show media` opens a compact **media gallery hub** with:
  - image/video counts,
  - explicit primary cover indication,
  - current gallery position and typed item label,
  - shortened current media reference.
- `Hide media` collapses media hub.
- When gallery has multiple items, panel navigation buttons (`Prev media` / `Next media`) update current gallery index.
- When opened, media section can provide direct URL buttons for first external media items (without mixing them into source buttons).

This creates practical card/gallery behavior without turning card into a giant media dump.

---

## 5) Source/media separation (preserved)
Separation remains strict:
- `Official` = dedicated button from `official_url`.
- Sources = only `source_links` buttons.
- Media = gallery/toggle section + optional media URL actions only when media hub is open.

No media refs are reused as source buttons.

---

## 6) Tests added/updated
Targeted behavior tests now cover:
1. cover resolution order (manual/import/priority)
2. `show_cover_on_open` rendering
3. `on_demand` rendering behavior
4. truthful no-media state
5. source/media separation
6. product card media toggle smoke
7. panel-driven media interaction smoke

Also kept core search/card regression checks green.

---

## 7) Exact local verification commands
Executed locally:

```bash
pytest -q tests/test_bot_search_smoke.py
pytest -q tests/test_search_service.py tests/test_search_projection.py tests/test_catalog_v2_ingest_foundation.py
```

---

## 8) Canonical baseline migration handling
No schema change was required for this PR.

Therefore:
- canonical baseline migration **was not modified**;
- no new Alembic migration chain/file was created.

Reason: PR2 delivers UI/runtime media interaction seam using already-available structured `media_items` and read model fields.
