# CycleSync — Local Pilot Runbook (Short)

Дата: 2026-04-14

## 1) Поднять проект

1. Подготовить env:
   - `cp .env.example .env`
   - обязательно заполнить:
     - `BOT_TOKEN`
     - `BOT_ADMIN_IDS`
2. Поднять инфраструктуру:
   - `docker compose up --build -d`
3. Проверить доступность:
   - `python -m scripts.check_connectivity`
4. Применить baseline:
   - `alembic upgrade head`
5. Запустить процессы:
   - API: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
   - Bot: `python -m app.run_bot`

## 2) Загрузить каталог (V2)

1. Validate (dry-run):
   - admin panel: `📦 Catalog sync -> ✅ Validate workbook (dry-run)`
2. Apply ingest:
   - admin panel: `📦 Catalog sync -> 🚀 Run XLSX ingest (apply)`
3. Убедиться, что используется `docs/medical_v2.xlsx`.

## 3) Проверить поиск

1. Выполнить rebuild:
   - `python -m scripts.rebuild_search_projection`
2. В боте проверить поиск по:
   - trade name;
   - ingredient;
   - ester;
   - alias/RU/EN/translit.

## 4) Проверить карточку товара

1. Открыть карточку из выдачи.
2. Проверить:
   - кнопку `Official`;
   - source-кнопки (несколько источников);
   - media toggle (`Показать/Скрыть медиа`);
   - cover behavior для `none/on_demand/show_cover_on_open`.
3. Как админ проверить policy/toggles:
   - `media_policy`;
   - `display_mode`;
   - `sync_images/sync_videos/sync_sources`.

## 5) Проверить расчёт / протокол

1. Добавить товар в Draft.
2. Открыть Draft -> wizard -> рассчитать preview.
3. Пройти pre-start -> activation.
4. Проверить active protocol и estimator.
5. Убедиться, что engine работает в V2 (summary metrics).

## 6) Проверить reminders

> Важно: reminders не живут сами без scheduler.

Минимум для локального pilot:
1. Materialize по расписанию:
   - `python -m scripts.materialize_reminders 100`
2. Dispatch по расписанию:
   - `python -m scripts.dispatch_reminders`
3. Рекомендованные интервалы:
   - materialize: 1-5 мин;
   - dispatch: 1 мин.

## 7) Проверить labs / triage

1. `Labs` -> `New report`.
2. Заполнить маркеры.
3. `Run AI triage`.
4. Создать specialist case.
5. Проверить specialist/admin обработку кейса.

## 8) Проверить access / checkout / runtime clarity

1. `Activate key` flow.
2. В admin runtime panel:
   - переключить `commerce_enabled` и проверить видимость checkout entrypoint.
   - переключить `debug_enabled` и проверить role gating debug-действий.
3. Проверить coupon/checkout demo path при включенной коммерции.

## 9) Свернуть всё обратно

1. Остановить API/Bot процессы.
2. Остановить инфраструктуру:
   - `docker compose down -v`
