# PR W1 / PR2 — Search Foundation (Meilisearch)

## Что сделано

- Добавлен `search_read` слой c состоянием projection и логами поисковых запросов (включая not-found).
- Реализован `CompoundSearchDocument` shape и детерминированный projection builder из transactional catalog truth.
- Добавлен Meilisearch gateway на `httpx` (тонкий adapter), без протекания raw payloads в domain/application.
- Реализован `SearchApplicationService` с degradable behavior при недоступности Meili.
- Добавлен full rebuild (`scripts/rebuild_search_projection.py`) и targeted rebuild (`scripts/rebuild_search_projection.py <product_id...>`).
- Добавлен search-first bot UX:
  - текстовый entrypoint,
  - выдача результатов,
  - действия `Open` и `+Draft` (hook/stub).
- Добавлен compact Open card: name, brand, composition summary, form, official URL, authenticity notes, media refs.
- Diagnostics показывают состояние search dependency (Meili connectivity).

## Search document shape

`CompoundSearchDocument`:

- `id` / `product_id`
- `trade_name`
- `product_name`
- `brand`
- `aliases[]`
- `ingredient_names[]`
- `ester_component_tokens[]`
- `concentration_tokens[]`
- `dosage_unit_tokens[]`
- `form_factor`
- `normalized_tokens[]`
- `composition_summary`
- `official_url`
- `authenticity_notes`
- `media_refs[]`

Документ построен как управляемая поисковая проекция (а не dump).

## Индексация

- Meili index создается/настраивается через gateway (`ensure_index`).
- Upsert документов выполняется батчем (`upsert_documents`).
- Для targeted rebuild есть удаление устаревших документов по ID (`delete_documents`) с последующим upsert.
- Search выполняется через нормализованный query и возвращает domain-friendly структуру.

## Rebuild approach

- **Full rebuild**: выборка всех активных продуктов каталога → build docs → upsert.
- **Targeted rebuild**: выборка конкретных `product_id` → delete old docs → upsert rebuilt docs.
- Состояние rebuild/checkpoint пишется в `search_read.search_projection_state`.

## Bot UX delivered

- `/start` приглашает к поиску.
- Любой текст (кроме команд) трактуется как search query.
- Показывается список результатов с action-кнопками:
  - `Open`
  - `+Draft`
- `Open` возвращает compact card.
- `+Draft` пока stub (готов seam под PR3 persistence).

## Что отложено на PR3

- Draft persistence и полноценный `compound_added_to_draft` write path.
- Более продвинутые ranking/rules tuning и фильтры.
- Voice input channel (оставлен seam в `source`).
- Event emission в outbox для search events (`search_executed`, `search_zero_result`, etc.).
