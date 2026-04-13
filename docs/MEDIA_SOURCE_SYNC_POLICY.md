# MEDIA_SOURCE_SYNC_POLICY.md

## 1. Назначение

Этот документ фиксирует **единую политику работы с media и source data** в CycleSync для каталога препаратов.

Документ отвечает на вопросы:

- откуда берутся изображения / видео / источники;
- что считается **import layer**, а что считается **manual layer**;
- кто кого переопределяет;
- что значит `media_policy`;
- что делают toggles:
  - `sync_images`
  - `sync_videos`
  - `sync_sources`;
- что должно показываться в карточке товара;
- как система должна вести себя при повторном импорте / синхронизации.

## 2. Базовая модель

В системе есть **два источника данных** для media/source layer:

### 2.1. Import layer
Данные, пришедшие из workbook / Google Sheets import:

- `Media` sheet
- `Sources` sheet
- `Products.official_url`

Это каталоговый слой.

### 2.2. Manual layer
Данные, добавленные руками через бот / admin UI:

- вручную загруженные изображения;
- вручную загруженные видео;
- вручную добавленные source links;
- вручную заданный cover;
- вручную выключенные / скрытые элементы.

Это админский слой.

## 3. Основной принцип

### 3.1. Manual layer не должен молча уничтожаться import-ом
Если админ руками добавил или переопределил media/source, очередной импорт **не должен это стирать**, если policy и sync toggles не разрешают это явно.

### 3.2. Import layer — это базовый слой
Import layer считается:
- дефолтным,
- воспроизводимым,
- пригодным для массового обновления каталога.

### 3.3. Manual layer — это продуктовая настройка
Manual layer считается:
- локальной настройкой продукта,
- более прицельной,
- потенциально более приоритетной для UI.

## 4. Типы данных

## 4.1. Media
Media item — это один объект типа:
- `image`
- `video`
- `gif`
- `animation`

Media item может иметь:
- `priority`
- `is_cover`
- `is_active`
- `caption`
- `source_layer` (`import` / `manual`)

## 4.2. Sources
Source item — это одна ссылка.

Source item может иметь:
- `source_kind`
- `label`
- `priority`
- `is_active`
- `source_layer` (`import` / `manual`)

## 4.3. Official URL
`official_url` — специальный singleton field на уровне продукта.

Он не должен смешиваться с general source list:
- `official_url` — это primary official button
- все прочие ссылки — только через `Sources`

## 5. Политика media/source merging

У каждого продукта есть `media_policy`.

Поддерживаются 4 режима:

### 5.1. `import_only`
Смысл:
- UI использует **только import layer**
- manual media/source не показываются

Использовать когда:
- продукт полностью управляется каталогом
- ручные overrides не допускаются

### 5.2. `manual_only`
Смысл:
- UI использует **только manual layer**
- import data хранится, но в UI не участвует

Использовать когда:
- админ хочет полностью взять карточку под ручной контроль

### 5.3. `prefer_manual`
Смысл:
- если по данному каналу есть manual data — используем её
- если manual data нет — используем import layer

Это дефолтно рекомендуемый режим для большинства живых карточек.

### 5.4. `merge`
Смысл:
- import + manual объединяются
- dedupe выполняется по `ref/url`
- сортировка идет по:
  1. priority
  2. source_layer preference if needed
  3. insertion order fallback

Использовать когда:
- и каталоговые, и ручные материалы нужны одновременно

## 6. Sync toggles

На уровне продукта управляются три отдельных toggles:

- `sync_images`
- `sync_videos`
- `sync_sources`

### 6.1. `sync_images`
Если `false`:
- import layer не обновляет image items для продукта
- existing import image items можно:
  - оставить как frozen snapshot
  - либо не трогать вообще
- manual images unaffected

### 6.2. `sync_videos`
Если `false`:
- import layer не обновляет video/gif/animation items
- manual video unaffected

### 6.3. `sync_sources`
Если `false`:
- import layer не обновляет `Sources`
- existing manual sources unaffected

### 6.4. Separate `official_url`
`official_url` желательно синхронизировать отдельно, либо считать его частью `sync_sources`.
Рекомендуемая MVP-логика:
- `official_url` obeys `sync_sources`

## 7. Import behavior rules

## 7.1. General rule
Import работает **по слоям**, а не как “удалить всё и залить заново”.

### 7.2. Import updates only import layer
При импорте:
- создаются/обновляются записи `source_layer=import`
- manual layer не трогается

### 7.3. Import delete semantics
Удаление import rows должно быть **controlled**, не слепым.

Рекомендуемый MVP:
- если item исчез из workbook:
  - import-layer item можно:
    - пометить `is_active=false`, либо
    - удалить только если нет manual override и режим допускает cleanup
- manual items никогда не удаляются import-ом

### 7.4. Dedupe
Dedupe rules:

#### Media
Дедупликация по:
- exact `ref`
- same `media_kind`
- same `product_key`

#### Sources
Дедупликация по:
- exact normalized `url`
- same `product_key`

## 8. Override semantics by channel

Нужно думать не “одна глобальная магия”, а **по каналам**:

- images
- videos
- sources
- official_url

Пример:
- images → `prefer_manual`
- videos → `import_only`
- sources → `merge`

Если система пока не поддерживает channel-specific policy на уровне DB, допускается MVP:
- один `media_policy` на продукт
- + per-channel sync toggles

Но в логике нужно оставлять seam под future channel-level policy.

## 9. Правила отображения в product card

## 9.1. Official
Если `official_url` есть:
- показывать отдельную кнопку `Official`

## 9.2. Sources
Если есть source items:
- каждая активная ссылка = отдельная кнопка
- label брать:
  - из `label`
  - иначе fallback `Source 1`, `Source 2`, ...

Нельзя:
- показывать source links одной простыней
- хранить все ссылки только через `;` в одной ячейке как основной контракт

## 9.3. Media
Карточка должна поддерживать 3 display modes:

### `none`
Ничего не показываем автоматически

### `on_demand`
Media открывается по кнопке/toggle

### `show_cover_on_open`
Если есть cover:
- показываем primary cover при открытии карточки

Это не то же самое, что `media_policy`.
Это UI display mode.

## 9.4. Cover selection
Cover выбирается так:

1. manual item with `is_cover=true`
2. import item with `is_cover=true`
3. highest-priority active media
4. no cover

Если `media_policy=import_only`, manual cover игнорируется.
Если `manual_only`, import cover игнорируется.
Если `prefer_manual`, manual cover приоритетен.
Если `merge`, cover выбирается по правилам выше.

## 10. Admin behavior rules

## 10.1. Admin manual add
При ручном добавлении media/source:
- создается manual-layer item
- import-layer не трогается

## 10.2. Admin disable/hide
Если админ отключает конкретный item:
- желательно хранить это как state на самом item
- если отключается import-layer item, импорт не должен автоматически снова сделать его видимым без explicit refresh policy

## 10.3. Admin mode controls
Для продукта должны существовать admin options:

- media display mode:
  - `none`
  - `on_demand`
  - `show_cover_on_open`
- media/source sync toggles:
  - images
  - videos
  - sources
- merge/override policy:
  - `import_only`
  - `manual_only`
  - `prefer_manual`
  - `merge`

## 11. Рекомендуемое поведение по умолчанию

Для большинства продуктов default рекомендуется такой:

- `media_policy = prefer_manual`
- `sync_images = true`
- `sync_videos = true`
- `sync_sources = true`
- `display_mode = on_demand`

Почему:
- import дает базу
- manual admin work может точечно улучшать карточку
- ничего не ломается молча

## 12. Validation rules

## 12.1. Hard errors
- invalid `media_policy`
- invalid media kind
- invalid source URL format
- duplicate `official_url` ambiguity
- empty `ref` / `url`

## 12.2. Soft warnings
- product has source toggle enabled but no sources
- product has media toggle enabled but no media
- multiple covers active
- source labels missing
- same source duplicated in import + manual layers

## 13. Import examples

## 13.1. Example: import_only
- workbook has 2 images, 1 video, 2 sources
- admin later adds image manually
- card still shows only workbook media/source

## 13.2. Example: prefer_manual
- workbook has 2 images
- admin uploads new cover
- card uses admin cover
- if no admin video exists, workbook video still used

## 13.3. Example: merge
- workbook has 2 images, 2 sources
- admin adds 1 custom image and 1 custom source
- card shows merged list, deduped, sorted by priority

## 14. Что НЕ делаем сейчас

В этой policy deliberately не делаем:
- CDN/media transformation pipeline
- automatic preview extraction from video
- content moderation
- shopping/gallery commerce behavior
- separate per-channel override policy in DB if one product-level policy is enough for MVP

## 15. Что должно быть реализовано после утверждения policy

После утверждения этого документа нужно сделать:

1. workbook v2 fields aligned with this policy
2. importer v2 aligned with:
   - `Media`
   - `Sources`
   - sync toggles
   - import-layer only updates
3. product card/source/media UX aligned with:
   - separate source buttons
   - official button
   - cover/on-demand modes
4. admin controls aligned with:
   - policy
   - display mode
   - sync toggles

---

**Итог:**  
Media и source в CycleSync должны перестать быть “какой-то ссылкой где-то в карточке” и стать нормальным двухслойным каталогово-ручным механизмом с явными правилами override, sync и показа.
