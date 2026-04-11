# PR_W4_PR1 — Reminder materialization foundation

## 1) Какие reminder truth tables введены

Добавлены таблицы:
- `reminders.protocol_reminders` — materialized execution truth для reminder rows.
- `user_registry.user_notification_settings` — user reminder settings truth.
- `reminders.reminder_schedule_requests` расширена полем `error_message` для trace failed materialization.

## 2) Как работает materialization

Пайплайн:
1. `ReminderApplicationService.materialize_requested_schedules()` читает `requested` requests.
2. На каждый request пишет старт-событие в outbox: `reminder_schedule_materialization_started`.
3. Загружает protocol user + active pulse plan entries + user settings.
4. Создает `protocol_reminders` idempotent-образом (по уникальности entry/kind).
5. Помечает request как `materialized` либо `failed`.
6. Пишет финальное событие: `reminder_schedule_materialized` или `reminder_schedule_materialization_failed`.

## 3) Где живут user reminder settings

Persistence: `user_registry.user_notification_settings`.
Поля:
- `user_id`
- `reminders_enabled`
- `preferred_reminder_time_local`
- `timezone_name`
- timestamps

## 4) Как работает toggle on/off

В боте добавлен minimal settings UX:
- entrypoint текстом `Settings`
- показ текущего состояния reminders/time/timezone
- toggle кнопка `Turn On/Turn Off`
- установка времени через `Set reminder time`

При выключенных reminders materializer создает rows в статусе `suppressed` (и `is_enabled=false`), что фиксирует opt-out и не смешивает его с breach/adherence.

## 5) Как обеспечена idempotency

- На таблице `protocol_reminders` установлен unique key: `(pulse_plan_entry_id, reminder_kind)`.
- Materializer перед вставкой читает уже materialized entry ids и пропускает existing.
- Повторный запуск request path repeat-safe: rows не дублируются.

## 6) Что сознательно НЕ сделано в этом PR

- Нет Telegram delivery runtime.
- Нет `sent/awaiting_action/snoozed/completed/skipped/expired` runtime-state transitions.
- Нет adherence scoring.
- Нет broken-protocol automation.

## 7) Команды локальной проверки

```bash
alembic upgrade head
pytest -q
python -m scripts.materialize_reminders
make reminders-materialize
```
