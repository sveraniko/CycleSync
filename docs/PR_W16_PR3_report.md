# PR W16 / PR3 — Admin control layer for product media/source policy

## 1) Added admin controls

Implemented admin-only per-product control surface directly from product card:

- `media_policy` controls:
  - `import_only`
  - `manual_only`
  - `prefer_manual`
  - `merge`
- `display_mode` controls:
  - `none`
  - `on_demand`
  - `show_cover_on_open`
- Sync channel toggles:
  - `sync_images`
  - `sync_videos`
  - `sync_sources`

UX shape:
- Admin-only entrypoint button on card: `🛠 Media/source policy`.
- Compact in-panel controls (policy/mode/toggles) with immediate in-place refresh.
- Existing admin media upload flow preserved (`🖼️ Добавить медиа`).

## 2) How persisted media policy now affects card behavior

Card behavior now reads policy from persisted product state (`compound_products.media_policy`) via `OpenCard`.

Effects:
- Effective media gallery respects persisted policy (`import_only` / `manual_only` / `prefer_manual` / `merge`).
- Primary cover resolver runs on effective gallery after policy filtering.
- Source buttons now also respect the same persisted layer policy (import/manual filtering), keeping source/media semantics aligned.

Fallback behavior:
- Fallback to `merge` only when persisted policy is truly missing/invalid.

## 3) How persisted display mode now affects card behavior

Card media block now resolves display mode from persisted state (`compound_products.media_display_mode`):

- `none` → media block hidden by mode
- `on_demand` → availability text + open via `Show media`
- `show_cover_on_open` → explicit cover-on-open block when cover exists

Fallback behavior:
- Fallback to `on_demand` only when persisted mode is missing/invalid.

## 4) How sync toggles now work

Product-level persisted toggles (`compound_products.sync_images/sync_videos/sync_sources`) are now admin-managed and used by import persistence logic:

- `sync_images=false` blocks import-layer image replacement.
- `sync_videos=false` blocks import-layer video/gif/animation replacement.
- `sync_sources=false` blocks import-layer source link replacement and blocks workbook official URL overwrite.

Import behavior adjusted to avoid hidden magic:
- Import updates import layer only.
- Manual media/source rows are no longer deleted by workbook sync paths.
- Source/media replacement is channel-aware and toggle-aware.

## 5) Intentionally out of scope

Still intentionally not implemented in this PR:

- Giant media CMS / full media manager.
- Google/XLSX admin sync UI controls.
- Checkout/commercial scope coupling.
- Import job operational dashboard.

## 6) Exact local verification commands

```bash
python -m py_compile \
  app/bots/handlers/search.py \
  app/infrastructure/catalog/repository.py \
  app/infrastructure/search/repository.py \
  app/application/search/service.py \
  app/application/search/repository.py \
  app/application/search/schemas.py \
  app/domain/models/compound_catalog.py

pytest -q tests/test_bot_search_smoke.py tests/test_admin_media_upload_policy_smoke.py
```

## 7) Canonical baseline migration update

Schema change was required.

Per baseline-rewrite policy, no new Alembic revision was created.
Instead, canonical baseline migration was updated in place:

- Updated file: `alembic/versions/20260411_0012_baseline_consolidated.py`
- Added `compound_catalog.compound_products` columns:
  - `media_policy`
  - `media_display_mode`
  - `sync_images`
  - `sync_videos`
  - `sync_sources`

This keeps a single canonical baseline migration chain.
