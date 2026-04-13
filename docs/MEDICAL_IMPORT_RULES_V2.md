# MEDICAL_IMPORT_RULES_V2.md

## 1. Назначение

Этот документ фиксирует **правила импорта** для `medical_v2.xlsx` в CycleSync.

Документ отвечает на вопросы:

- в каком порядке импортируются sheet-ы;
- как обрабатываются `Products`, `Ingredients`, `Sources`, `Media`, `Aliases`;
- что считается `upsert`;
- что считается deactivate/disable;
- что нельзя молча удалять;
- как работают sync toggles;
- как importer должен вести себя при повторном запуске;
- как обеспечивается предсказуемость и auditability.

## 2. Базовые принципы

## 2.1. V2 only
Importer V2 работает только с `medical_v2.xlsx`.
Legacy `medical.xlsx` не рассматривается как основной контракт.

## 2.2. Layered import, not blind replace
Импорт работает как **слоистый upsert**, а не как:
> “удали всё и залей заново”

Это особенно важно для:
- manual media/source layer
- admin overrides
- live catalog state

## 2.3. Import is deterministic
Один и тот же workbook при одинаковом state должен давать:
- один и тот же результат,
- без случайного reorder,
- без непредсказуемого удаления,
- без “магического восстановления” отключенных manual сущностей.

## 2.4. Import must be auditable
Каждый запуск импорта должен давать:
- понятный summary,
- counts:
  - created
  - updated
  - unchanged
  - deactivated
  - warnings
  - errors

## 3. Import pipeline order

Импорт должен идти строго по порядку:

1. `Products`
2. `Ingredients`
3. `Sources`
4. `Media`
5. `Aliases`
6. validation of sheet-level consistency
7. optional projection/search rebuild trigger
8. import report generation

### Почему именно так
- `Products` создают базовые сущности
- `Ingredients`, `Sources`, `Media`, `Aliases` зависят от `product_key`
- сначала основа, потом дочерние слои

## 4. Import modes

Importer должен поддерживать минимум два режима запуска:

### 4.1. `dry_run`
- ничего не пишет в БД
- валидирует workbook
- показывает planned changes
- useful for admin/operator

### 4.2. `apply`
- реально применяет изменения

Рекомендуемый CLI/API contract:
- `--mode dry-run`
- `--mode apply`

## 5. Product import rules

Sheet: `Products`

### Unique key
Основной ключ:
- `product_key`

### Upsert behavior
Если `product_key` уже существует:
- обновляем product-level import-controlled поля
- не трогаем manual-only state unless explicitly allowed

### Fields allowed to update from import
Product-level import may update:
- `brand`
- `trade_name`
- `display_name`
- `release_form`
- `form_factor`
- `package_kind`
- `units_per_package`
- `volume_per_package_ml`
- `official_url` (если `sync_sources` позволяет)
- `authenticity_notes`
- `media_policy`
- `sync_images`
- `sync_videos`
- `sync_sources`
- `is_active`
- `pharmacology_notes`
- other import-owned descriptive fields

### Fields not to overwrite blindly
Если в системе есть runtime/admin-specific state:
- UI display mode
- admin local flags
- manual media/source state
- local moderation flags

они не должны молча перетираться import-ом.

### Missing product in workbook
Если продукт есть в БД, но отсутствует в workbook:
- не удалять физически по умолчанию
- рекомендованное MVP поведение:
  - пометить import-owned product as `is_active=false`
  - only if it belongs to workbook-managed catalog scope
- если продукт создан вручную вне импортируемого каталога:
  - не трогать

## 6. Ingredient import rules

Sheet: `Ingredients`

### Natural row identity
Ingredient row identity рекомендуется задавать как:
- `product_key`
- `ingredient_order`

Допустим также explicit `ingredient_key`, если будет введен позже.

### Upsert behavior
Если строка с тем же `product_key + ingredient_order` существует:
- обновляем ingredient fields

### Replace semantics
Для конкретного продукта importer должен считать ingredient set authoritative for import layer.

То есть:
- все ingredient rows из workbook for that product = canonical import ingredient set
- missing import ingredient rows may be deactivated/removed from import layer

### Validation
Hard error if:
- ingredient references missing `product_key`
- referenced product missing
- both `amount_per_ml_mg` and `amount_per_unit_mg` absent where required
- `basis` invalid
- `half_life_days` missing
- `active_fraction` missing

### Product without ingredients
Hard validation failure.
Product cannot be import-valid without at least one ingredient row.

## 7. Source import rules

Sheet: `Sources`

### Natural row identity
Recommended identity:
- `product_key`
- normalized `url`
- `source_kind`

### Upsert behavior
Importer only manages **import-layer source items**.

### Sync precondition
If `Products.sync_sources == false`:
- do not modify source rows for that product
- skip source import for that product
- log as skipped, not error

### Missing source rows in workbook
For import-layer source items only:
- if source existed in previous import but no longer present in workbook:
  - mark import-layer source as inactive
  - do not delete manual-layer sources

### Manual layer protection
Never delete or overwrite manual-layer source rows via workbook import.

### Official URL
`official_url` is treated as separate product field.
It should obey `sync_sources`.
If `sync_sources=false`, importer should not overwrite existing official URL from workbook.

## 8. Media import rules

Sheet: `Media`

### Natural row identity
Recommended identity:
- `product_key`
- `media_kind`
- normalized `ref`

### Import scope
Importer only manages **import-layer media**.

### Channel toggles
Importer must obey:
- `sync_images`
- `sync_videos`

### Mapping
- `image` affected by `sync_images`
- `video`, `gif`, `animation` affected by `sync_videos`

If channel toggle false:
- skip those items
- do not modify existing items in that channel
- log skip reason

### Missing media rows in workbook
For import-layer media only:
- mark missing import media inactive
- do not delete manual media

### Cover behavior
Import may set/update import-layer `is_cover=true`.
But final displayed cover is resolved later by display policy and merge rules.

Importer does NOT decide final visible cover, it only updates import-layer data.

### Manual layer protection
Never delete/overwrite manual media from workbook import.

## 9. Alias import rules

Sheet: `Aliases`

### Natural row identity
Recommended identity:
- `product_key`
- normalized `alias`
- `alias_kind`

### Upsert behavior
Aliases from workbook are authoritative for import-layer alias set.

### Missing alias rows
For import-layer aliases:
- mark missing aliases inactive
- do not delete possible future manual aliases if such layer appears

### Validation
Hard error if:
- alias empty
- alias_kind invalid
- referenced product missing

## 10. Sheet validation rules

## 10.1. Workbook-level hard errors
- required sheet missing
- duplicate `product_key` in `Products`
- orphan rows in `Ingredients`, `Sources`, `Media`, `Aliases`
- invalid enums
- invalid numeric fields where required
- malformed URLs in `official_url` or `Sources.url`

## 10.2. Workbook-level soft warnings
- product has no sources
- product has no media
- product has no aliases
- multiple cover flags in same product media set
- missing `tmax_hours`
- missing guidance values
- unusual packaging metadata

## 11. Import ownership model

Каждая import-managed сущность должна знать, что она:
- `source_layer=import`
или
- `source_layer=manual`

### Importer rule
Importer modifies only:
- `source_layer=import`
- product import-owned fields

It must never silently mutate manual-layer records.

## 12. Conflict resolution rules

## 12.1. Product field conflicts
If product field exists in DB and workbook supplies a different value:
- import updates it if field is import-owned
- import report should count as `updated`

## 12.2. Source/media conflicts
If same `url/ref` exists in both import and manual layer:
- keep both layers logically separate if schema allows
- UI merge layer later dedupes for display
- importer should not collapse manual into import

## 12.3. Invalid row conflicts
If one row invalid but workbook otherwise good:
- recommended MVP:
  - fail whole import in `apply`
  - produce full validation report
This is safer for catalog integrity than partial silent success.

Optional future:
- `--allow-partial`
But not required now.

## 13. Import transaction semantics

Recommended behavior:
- validate workbook fully first
- if hard errors exist:
  - no writes
- if validation passes:
  - apply import in transaction
- if fatal DB write error happens:
  - rollback entire import run

This prevents half-imported catalog states.

## 14. Search / projection implications

Importer itself should not directly mutate search index row-by-row in ad hoc fashion.

Preferred flow:
1. import workbook into DB truth
2. trigger rebuild or targeted reindex
3. produce post-import search summary

### Recommended modes
- `--rebuild-search yes|no`
- or separate explicit rebuild command

For pilot/admin operations, separate explicit rebuild is acceptable and safer.

## 15. Media/source sync behavior examples

## 15.1. Example: source sync enabled
Product:
- `sync_sources = true`

Workbook:
- 2 source rows

DB before:
- 1 old import source
- 1 manual source

Result:
- import source set becomes exactly workbook-defined import set
- old missing import source -> inactive
- manual source untouched

## 15.2. Example: image sync disabled
Product:
- `sync_images = false`

Workbook:
- 3 image rows

DB before:
- existing import images
- 1 manual image

Result:
- importer skips image updates
- nothing changes in image layer
- report shows skipped-by-toggle

## 15.3. Example: video sync enabled
Product:
- `sync_videos = true`

Workbook:
- 1 new video row

DB before:
- no import videos

Result:
- new import video created
- manual videos untouched

## 16. Import report requirements

Каждый import run должен возвращать/писать structured report with at least:

### Global
- workbook path / source id
- started_at
- finished_at
- mode (`dry_run` / `apply`)
- status (`success`, `failed`, `success_with_warnings`)

### Counts
- product_created
- product_updated
- product_deactivated
- ingredient_created
- ingredient_updated
- ingredient_deactivated
- source_created
- source_updated
- source_deactivated
- media_created
- media_updated
- media_deactivated
- alias_created
- alias_updated
- alias_deactivated
- skipped_by_toggle
- warnings_count
- errors_count

### Error details
- sheet
- row reference
- error code
- human-readable message

## 17. Recommended CLI/API behavior

Minimum operational functions:

1. `validate workbook`
2. `dry-run import`
3. `apply import`
4. optional `apply + rebuild search`
5. export/import report path

Example desired behavior:
- validate first
- show delta
- apply intentionally

## 18. What importer must NOT do

Importer V2 must NOT:
- delete manual media/source
- blindly wipe whole catalog
- silently ignore hard data errors
- recreate product identities on every run
- silently restore disabled manual items
- mix workbook links into one semicolon field again
- mutate checkout / commercial / protocol data
- try to be shopping/procurement system

## 19. Minimal next implementation steps after this rules doc

После утверждения этого документа нужно сделать:

1. align `medical_v2.xlsx` with:
   - `Products`
   - `Ingredients`
   - `Sources`
   - `Media`
   - `Aliases`
2. update importer to layered V2 rules
3. update source/media UI to consume first-class source/media rows
4. add validation + dry-run reporting
5. keep search rebuild as explicit operational step unless later automated safely

---

**Итог:**  
Importer V2 должен быть предсказуемым, слоистым и бережным к manual data. Он должен обновлять каталог как систему truth-слоев, а не как тупую заливку “снесли всё и загрузили заново”.
