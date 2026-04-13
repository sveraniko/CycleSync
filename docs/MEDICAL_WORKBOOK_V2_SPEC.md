# MEDICAL_WORKBOOK_V2_SPEC.md

## 1. Назначение

`medical_v2.xlsx` — это **единственный** поддерживаемый workbook-контракт для каталога препаратов, PK-расчётов, поиска, media/source wiring и regression-сценариев CycleSync.

Старый `medical.xlsx` считается legacy seed-файлом для ранних smoke-тестов и не должен развиваться дальше.

## 2. Цели V2

V2 нужен для того, чтобы система умела:

1. хранить **продукт** отдельно от его **ингредиентов / эфиров**;
2. считать **mixed products** не как “одну банку с одним half-life”, а как состав из нескольких компонентов;
3. хранить фасовку / упаковку так, чтобы этого хватало для:
   - course estimator,
   - inventory-constrained mode,
   - package-aware planning;
4. хранить `source_url` и media **не в одной ячейке**, а как first-class сущности;
5. поддерживать нормальный поиск по:
   - trade name,
   - brand,
   - ingredient,
   - ester,
   - alias / slang / translit;
6. поддерживать ручной media override через бот без хаоса и потери импортных данных.

## 3. Общие принципы

### 3.1. Только V2
- поддерживаем **только** `medical_v2.xlsx`;
- dual-format support (`v1` + `v2`) не делаем;
- если нужны миграции данных из старого seed-файла, это отдельный разовый conversion path.

### 3.2. Нормализация
Workbook строится не как один перегруженный sheet, а как набор нормализованных sheet-ов:

1. `Products`
2. `Ingredients`
3. `Sources`
4. `Media`
5. `Aliases`
6. `PulseScenarios`
7. `SearchCases`

### 3.3. PK scope v2
В V2 делаем:
- ingredient-aware / ester-aware model;
- per-ingredient half-life;
- parent substance;
- active fraction;
- optional `tmax_hours`;
- product-level schedule planning с PK evaluation по ингредиентам.

В V2 **не** делаем:
- сложные bioavailability models;
- экзотические release models;
- полный клинический симулятор всех случаев;
- “медицинский ИИ, знающий всё”.

## 4. Sheet: `Products`

Одна строка = один товар / препарат.

### Обязательные колонки

| Column | Type | Required | Описание |
|---|---|---:|---|
| `product_key` | string | yes | стабильный уникальный ключ продукта |
| `brand` | string | yes | бренд / производитель |
| `trade_name` | string | yes | торговое название |
| `display_name` | string | yes | имя для UI-карточек |
| `release_form` | enum | yes | `injectable_oil`, `injectable_water`, `tablet`, `capsule`, `oral_liquid`, `transdermal`, etc. |
| `form_factor` | enum | yes | `vial`, `ampoule`, `blister`, `bottle`, `strip`, etc. |
| `package_kind` | enum | yes | тип упаковки для estimator: `vial`, `ampoule`, `tablet_pack`, `capsule_pack`, `bottle`, etc. |
| `units_per_package` | number | conditional | число единиц в упаковке; обязательно для tablet/capsule/blister semantics |
| `volume_per_package_ml` | number | conditional | объём упаковки в мл; обязательно для vial/ampoule/bottle injectables |
| `official_url` | string/url | no | официальный URL продукта/производителя |
| `authenticity_notes` | string | no | текст по верификации подлинности |
| `media_policy` | enum | yes | `import_only`, `manual_only`, `prefer_manual`, `merge` |
| `sync_images` | bool | yes | синхронизировать изображения из workbook |
| `sync_videos` | bool | yes | синхронизировать видео из workbook |
| `sync_sources` | bool | yes | синхронизировать source links из workbook |
| `is_active` | bool | yes | активен ли продукт в каталоге |

### Рекомендуемые колонки

| Column | Type | Required | Описание |
|---|---|---:|---|
| `product_family` | string | no | семейство продукта / серия |
| `country` | string | no | страна производителя |
| `pharmacology_notes` | string | no | product-level заметки |
| `default_ui_cover_mode` | enum | no | `none`, `show_cover_on_open`, `on_demand` |
| `default_currency` | string | no | если позже появится закупочная/коммерческая логика |

### Правила

1. `product_key` — основной join key между sheets.
2. `official_url` — только официальный/основной URL. Все остальные источники идут в `Sources`.
3. `media_policy` определяет поведение merge/override между импортом и ручным media attach через бот.
4. Для injectables `volume_per_package_ml` обязателен.
5. Для tablet/capsule `units_per_package` обязателен.

## 5. Sheet: `Ingredients`

Одна строка = **один ингредиент / один эфир / один активный компонент** внутри продукта.

Это основной sheet для PK v2.

### Обязательные колонки

| Column | Type | Required | Описание |
|---|---|---:|---|
| `product_key` | string | yes | связь с `Products.product_key` |
| `ingredient_order` | integer | yes | порядок отображения / стабильная сортировка |
| `parent_substance` | string | yes | базовое вещество, например `Testosterone`, `Boldenone`, `Drostanolone` |
| `ingredient_name` | string | yes | полное имя компонента |
| `ester_name` | string | no | эфир, если применимо (`Phenylpropionate`, `Cypionate`, `Undecylenate`, etc.) |
| `amount_per_ml_mg` | number | conditional | мг/мл для liquid injectables |
| `amount_per_unit_mg` | number | conditional | мг на таблетку/капсулу для solid forms |
| `basis` | enum | yes | `per_ml`, `per_unit` |
| `half_life_days` | number | yes | ориентировочный active half-life этого компонента |
| `active_fraction` | number | yes | доля активного вещества после учета эфира, 0..1 |
| `is_pulse_driver` | bool | yes | участвует ли как pulse-driving component |
| `dose_guidance_min_mg_week` | number | no | нижняя граница guidance |
| `dose_guidance_typical_mg_week` | number | no | типичное значение guidance |
| `dose_guidance_max_mg_week` | number | no | верхняя граница guidance |

### Рекомендуемые колонки

| Column | Type | Required | Описание |
|---|---|---:|---|
| `release_model` | enum | no | по умолчанию `first_order`; exotic models out of MVP |
| `tmax_hours` | number | no | ориентир пика |
| `pk_notes` | string | no | заметки по фармакокинетике |
| `search_weight` | number | no | если позже понадобится boosting |

### Правила

1. Для injectables используется `amount_per_ml_mg`.
2. Для tablets/capsules используется `amount_per_unit_mg`.
3. `active_fraction` обязателен для ester-aware math.
4. Если у продукта один ингредиент — это всё равно одна строка в `Ingredients`.
5. Если у продукта 3 эфира — это 3 строки.
6. `half_life_days` хранится **на уровне ингредиента**, не продукта.

### Пример mixed product

Для `PHARMA MIX 1` должны быть **три строки**:

1. `Testosterone Phenylpropionate` — 50 mg/ml  
2. `Testosterone Cypionate` — 200 mg/ml  
3. `Boldenone Undecylenate` — 200 mg/ml  

А не одна строка “Mix 450 mg/ml”.

## 6. Sheet: `Sources`

Одна строка = **один источник / одна ссылка**.

### Обязательные колонки

| Column | Type | Required | Описание |
|---|---|---:|---|
| `product_key` | string | yes | связь с продуктом |
| `source_kind` | enum | yes | `official`, `source`, `authenticity`, `community`, etc. |
| `label` | string | yes | подпись для кнопки, например `Source 1`, `Lab page`, `Forum review` |
| `url` | string/url | yes | одна конкретная ссылка |
| `priority` | integer | yes | порядок показа |
| `is_active` | bool | yes | активна ли ссылка |

### Правила

1. **Одна ссылка = одна строка.**
2. Больше не храним список URL через `;` в одной ячейке как основной контракт V2.
3. `official_url` в `Products` — это special-case primary URL.
4. Все остальные ссылки — только через `Sources`.

### UI expectation

- `Official` — отдельная специальная кнопка
- все строки `Sources` -> отдельные кнопки `Source 1`, `Source 2`, `Source 3` или по `label`

## 7. Sheet: `Media`

Одна строка = **один media item**.

### Обязательные колонки

| Column | Type | Required | Описание |
|---|---|---:|---|
| `product_key` | string | yes | связь с продуктом |
| `media_kind` | enum | yes | `image`, `video`, `gif`, `animation` |
| `ref` | string | yes | ссылка / reference value |
| `priority` | integer | yes | порядок |
| `is_cover` | bool | yes | использовать ли как cover |
| `is_active` | bool | yes | активен ли media item |

### Рекомендуемые колонки

| Column | Type | Required | Описание |
|---|---|---:|---|
| `caption` | string | no | подпись |
| `source_layer` | enum | no | по умолчанию `import` |
| `media_notes` | string | no | комментарий |

### Media override model

Media из workbook и media, добавленные через бот, живут в **двух источниках**, а итоговое поведение определяется `media_policy` из `Products`.

Поддерживаемые режимы:

- `import_only` — показываем только media из workbook;
- `manual_only` — показываем только media, добавленные через бот;
- `prefer_manual` — если вручную есть media, показываем их, иначе импортные;
- `merge` — объединяем import + manual.

### Sync toggles

Из workbook разрешается синхронизировать отдельно:
- `sync_images`
- `sync_videos`
- `sync_sources`

Если toggle выключен, импорт по этому каналу не должен затирать уже существующий manual слой.

## 8. Sheet: `Aliases`

Одна строка = один alias/search token.

### Колонки

| Column | Type | Required | Описание |
|---|---|---:|---|
| `product_key` | string | yes | связь с продуктом |
| `alias` | string | yes | alias/token |
| `alias_kind` | enum | yes | `brand`, `trade`, `ingredient`, `ester`, `ru`, `en`, `translit`, `slang` |
| `priority` | integer | yes | приоритет |

### Правила

1. Search должен уметь жить не только на `trade_name`, но и на alias layer.
2. Mixed products должны быть находимы:
   - по trade name,
   - по component,
   - по ester,
   - по translit,
   - по RU/EN alias.

## 9. Sheet: `PulseScenarios`

Regression sheet для PK/math validation.

### Примерные колонки

| Column | Type | Required | Описание |
|---|---|---:|---|
| `scenario_id` | string | yes | ID сценария |
| `input_mode` | enum | yes | `auto_pulse`, `stack_smoothing`, `total_target`, `inventory_constrained` |
| `preset` | enum | yes | `unified_rhythm`, `layered_pulse`, `golden_pulse` |
| `duration_weeks` | number | yes | длительность |
| `max_injection_volume_ml` | number | no | лимит объема |
| `max_injections_per_week` | number | no | лимит инъекций |
| `expected_status` | string | no | `success`, `warning`, etc. |
| `notes` | string | no | пояснения |

Сами per-product inputs для сценариев могут жить либо:
- в дополнительных колонках,
- либо в отдельном scenario-input sheet в будущем.

Для MVP допускается один compact sheet, если это не уродует контракт.

## 10. Sheet: `SearchCases`

Regression sheet для поиска.

### Колонки

| Column | Type | Required | Описание |
|---|---|---:|---|
| `query` | string | yes | поисковый запрос |
| `expected_primary_trade_name` | string | yes | ожидаемый главный hit |
| `expected_hit` | enum | yes | `yes` / `no` |
| `notes` | string | no | комментарий |

## 11. Packaging semantics для estimator / inventory

### Injectable products
Обязательная база:
- `package_kind = vial | ampoule | bottle`
- `volume_per_package_ml`
- ingredients with `amount_per_ml_mg`

Estimator выводит:
- total required mg
- total required ml
- package count required
- rounded package count required

### Tablet / capsule products
Обязательная база:
- `package_kind = tablet_pack | capsule_pack | blister`
- `units_per_package`
- ingredients with `amount_per_unit_mg`

Estimator выводит:
- total required mg
- total required unit count
- package count required
- rounded package count required

### Out of scope for V2 MVP
Не делаем пока:
- multi-level cartons/cases
- purchase bundles
- pharmacy pack hierarchies
- shopping list logic

## 12. Validation rules

### Hard validation errors
- missing `product_key`
- product without ingredients
- ingredient without `basis`
- injectable without `volume_per_package_ml`
- tablet/capsule without `units_per_package`
- missing `half_life_days`
- missing `active_fraction`
- invalid `media_policy`
- duplicate `official` URL rows if policy forbids ambiguity

### Soft warnings
- product without aliases
- product without sources
- product without media
- product with insufficient guidance values
- product with missing `tmax_hours`
- inactive sources/media still present

## 13. Import rules (high-level)

Workbook V2 должен импортироваться как **layered ingest**:

1. `Products`
2. `Ingredients`
3. `Sources`
4. `Media`
5. `Aliases`
6. regression sheets ignored in production import or used only by validation tools

### Important import principle
Import **не должен молча затирать manual media**, если `media_policy` и sync toggles не разрешают это явно.

## 14. UI expectations driven by V2

V2 должен позволить UI сделать следующие вещи без хаоса:

- product card:
  - title
  - brand
  - form
  - composition lines by ingredient
  - `Official` button
  - source buttons from `Sources`
  - media toggle from `Media`
- admin media:
  - manual attach through bot
  - priority over import according to `media_policy`
- search:
  - find by product, ingredient, ester, alias
- PK engine:
  - считать mixed products по ingredient/ester rows
- estimator:
  - считать packaging по package semantics

## 15. Explicit non-goals

V2 **не** должен пытаться сразу решить:
- shopping / buy flow
- inventory procurement
- полный клинический симулятор
- экзотику по release models
- поддержку десятка несовместимых legacy форматов

## 16. Минимальный seed dataset для V2

В первый `medical_v2.xlsx` обязательно включить:

1. **simple injectable single-ester**
   - пример: Masteron Enanthate / Testosterone Enanthate

2. **mixed ester product**
   - пример: Sustanon / Pharma Mix 1

3. **tablet product**
   - пример: Oxandrolone 10 mg tabs

4. **product with multiple sources**
   - минимум 2 source rows

5. **product with media**
   - минимум 1 image and 1 video ref scenario

Это нужно не для красоты, а чтобы:
- importer,
- search,
- estimator,
- media policy,
- PK v2
были протестированы на реальных типах данных.

## 17. Recommended next docs after this spec

После утверждения этого документа должны быть созданы:

1. `MEDIA_SOURCE_SYNC_POLICY.md`
2. `MEDICAL_IMPORT_RULES_V2.md`
3. `PK_ENGINE_V2_SPEC.md`
4. `medical_v2.xlsx`

---

**Итог:**  
`medical_v2.xlsx` должен стать нормализованным, ingredient-aware, package-aware и media/source-aware workbook-контрактом для следующей версии CycleSync, без наследования хаоса старого seed-файла.
