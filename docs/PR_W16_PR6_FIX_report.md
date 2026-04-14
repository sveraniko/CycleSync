# PR W16 / PR6 FIX — finishing polish (wording & consistency)

## 1) Какие поверхности дочищены
- **Search / card / media:** результаты поиска, карточка продукта, переключатели «показать/скрыть», навигация по страницам и медиа, admin-блок политики медиа/источников.
- **Draft / preview / active protocol:** пользовательские кнопки и формулировки в экранах «Мой протокол» и «Черновик».
- **Settings / protocol status:** статус протокола полностью русифицирован.
- **Admin runtime + catalog sync:** панель runtime, блоки коммерции/отладки, заголовки и описания синхронизации каталога, результат последнего запуска.
- **Labs / triage / specialist / operator:** корневая навигация, кнопки действий, история/кейсы, triage- и operator-панели.
- **Smoke tests:** обновлены ожидания текстов в smoke-тестах под финализированную русскую копию.

## 2) Какие категории wording нормализованы
- **RU/EN leaks:** убраны остатки английских action-labels (`Back to results`, `Run AI triage`, `Consult specialist`, `Course estimate`, `Runtime status`, `Catalog sync result` и др.).
- **Статусные лейблы:** `ON/OFF` на user/admin surface заменены на `ВКЛ/ВЫКЛ` там, где это пользовательский/операторский текст.
- **Кнопки:** унифицированы короткие глагольные подписи («Открыть», «Запустить триаж», «Перегенерировать», «Взять в работу» и т.д.).
- **Заголовки секций:** приведены к единому русскому стилю («Рабочая зона отчёта», «Состояние рантайма», «Результат синхронизации» и т.д.).

## 3) Примеры before/after
- `Back to results` → `← К результатам`
- `Show media` / `Hide media` → `Показать медиа` / `Скрыть медиа`
- `Run AI triage` → `Запустить AI-триаж`
- `Consult specialist` → `Консультация специалиста`
- `Course estimate` → `Оценка курса`
- `Protocol status:\n- no active protocol` → `Статус протокола:\n• активный протокол не найден`
- `Runtime status` → `Состояние рантайма`
- `Catalog sync result` → `Результат синхронизации`
- `commerce_enabled: ON/OFF` → `Коммерческий режим: ВКЛ/ВЫКЛ`

## 4) Exact local verification commands
1. `python -m compileall -q app tests`
2. `pytest -q tests/test_bot_search_smoke.py tests/test_bot_settings_smoke.py tests/test_bot_admin_runtime_smoke.py tests/test_bot_checkout_smoke.py tests/test_bot_labs_smoke.py tests/test_bot_access_key_smoke.py`

## 5) Baseline/schema policy
- **Schema changes:** не требовались.
- **Canonical baseline migration:** не менялась.
- **Новые Alembic migration файлы:** не создавались.
