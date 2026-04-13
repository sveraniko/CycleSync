# PR_W13_PR6 — Labs UX hardening (Wave 13 / PR6)

## 1) Labs root теперь single-panel
- Вход `Labs` переведен на контейнерный паттерн через `safe_edit_or_send(...)`.
- Основные ветки в одной стабильной панели:
  - New report
  - Report workspace
  - History
  - Run AI triage
  - Consult specialist
  - My specialist cases
  - Operator (только при role-gated доступе)
- Простая навигация больше не спамит новыми сообщениями.

## 2) Report-entry hierarchy вместо плоской button wall
- Рабочая зона отчета сделана иерархической:
  - **Panels**: male hormones, hematology, lipids, liver, metabolic, GH-related
  - **AI**: run triage, latest triage, regenerate
  - **Actions**: finalize report, consult specialist, back
- В корне report workspace нет 11 плоских кнопок; группы открываются подменой той же панели.

## 3) Marker input flow стал single-panel
- Ввод marker-by-marker полностью в одном контейнере с редактированием текущей панели.
- Текущий шаг (value/unit/ref min/ref max) отображается в карточке шага.
- Пользовательские numeric input сообщения удаляются после обработки (`delete_user_input_message`).
- Невалидный ввод очищается и отражается в той же панели.

## 4) History / triage / specialist views улучшены
- **History**:
  - компактный список (date + lab + marker count + protocol reference)
  - без raw UUID dump в пользовательском тексте
  - кнопки `Open ...` для перехода в карточку отчета
- **AI triage**:
  - card-like формат
  - summary + статус + urgent indicator
  - компактный flags list c severity icons
- **Specialist cases**:
  - open confirmation в карточке
  - compact case list
  - readable case detail + user-facing answer section

## 5) Что оставлено intentionally simple
- Не строился giant admin CRM: staff-side остался легким, но panel-driven.
- Не добавлялись тяжелые dashboard/аналитические экраны.
- Не расширялись доменные процессы outside Labs UX scope.

## 6) Exact local verification commands
- `pytest tests/test_bot_labs_smoke.py tests/test_bot_specialist_flow_smoke.py`

## 7) Baseline migration policy
- Schema changes не потребовались.
- Canonical baseline migration **не менялась**.
- Новая migration chain **не создавалась**.
