# PR W16 / PR1 — Product card media/source wiring foundation

## Scope
This PR implements the **data + wiring foundation** for product-card media/source UX surface.
It does **not** implement the full TradeFlow media gallery or admin policy UI.

---

## 1) How sources are now wired from catalog to card

### Import/workbook layer
- V2 ingest now parses `Sources` sheet rows into structured `SourceLinkInput` items:
  - `kind` (`source_kind`)
  - `label`
  - `url`
  - `priority`
  - `is_active`
  - `source_layer` (default `import`)
- The ingest builder keeps one row = one source link item (no semicolon concatenation).

### Catalog persistence layer
- Added first-class catalog entity/table `product_source_refs`.
- Catalog upsert now replaces source rows per product using structured records and priority ordering.

### Runtime read model / card path
- `get_open_card` now loads product source refs and maps only active rows into `OpenCard.source_links`.
- Card-level source links are returned as structured list objects and consumed by bot card rendering.

---

## 2) Official / source / media separation

The runtime/card model now enforces strict separation:
- `official_url` remains dedicated and special-case.
- `source_links` are structured source buttons (not media).
- `media_items` are structured media references (not source buttons).

No cross-over wiring remains in card button generation.

---

## 3) Card DTO / read-model changes

`OpenCard` now contains:
- `official_url` (unchanged, dedicated official CTA)
- `source_links: list[CardSourceLink]`
- `media_items: list[CardMediaItem]`

`CardSourceLink` fields:
- `kind`, `label`, `url`, `priority`, `is_active`

`CardMediaItem` fields:
- `media_kind`, `ref`, `priority`, `is_cover`, `source_layer`, `is_active`

This structure is merge-policy ready for `import_only`, `manual_only`, `prefer_manual`, `merge` in follow-up PRs.

---

## 4) Button rendering semantics now

Product card rendering is now data-driven:
- if `official_url` exists → render `Official` button
- each active `source_links` item → its own source button (label-driven)
- `Show sources` now reports `Нет данных.` when there are no source/official links
- `Show media` now reflects real structured media presence from `media_items`

This removes the previous half-empty “sources available below” state when no real buttons existed.

---

## 5) What is intentionally NOT implemented in PR1

Not part of this PR:
- full TradeFlow gallery/media hub UX
- advanced media merge-resolution UI/policy controls
- admin media/source policy management UI

Those remain for PR2+.

---

## 6) Local verification commands

Executed locally:

```bash
pytest -q tests/test_bot_search_smoke.py tests/test_catalog_v2_ingest_foundation.py tests/test_search_service.py tests/test_search_projection.py
```

Coverage of key expectations in this PR includes:
1. official button rendering
2. multiple per-source buttons
3. truthful `Show sources` behavior
4. structured media surfaced in card/UI path
5. official/source/media separation
6. priority-based source button ordering

---

## 7) Canonical baseline migration handling

Schema changes **were required** for first-class source/media wiring, and were applied by updating the **existing canonical baseline migration in place**:
- updated `alembic/versions/20260411_0012_baseline_consolidated.py`
- no new migration chain/file was created

Changes made in baseline:
- extended `product_media_refs` with:
  - `is_cover`
  - `source_layer`
- added new table `product_source_refs` with structured source link fields

