# CycleSync Architecture

> Технический архитектурный документ для **CycleSync** — Telegram-first системы расчета и сопровождения фармакологических протоколов.

---

## 1. Назначение документа

Этот документ раскрывает архитектурную рамку продукта, заданную в README.

Его задача — зафиксировать:

- системные контуры продукта;
- архитектурные слои;
- bounded contexts;
- правила владения данными;
- точки интеграции;
- модульные границы;
- правила взаимодействия между контекстами;
- принципы надежности и graceful degradation;
- место алгоритмического ядра (`pulse_engine`) в системе;
- технические ограничения и опорные решения для последующей реализации.

Этот документ **не является**:

- PR-планом;
- wave/sprint-планом;
- детальным data model документом;
- детальным event catalog;
- state-machine документом;
- testing strategy;
- rollout plan.

Все это должно оформляться отдельными файлами в `/docs`.

---

## 2. Архитектурное намерение

CycleSync должен быть спроектирован как **Telegram-first, modular, math-driven operating system** для сопровождения пользователей на фармакологических протоколах.

Архитектура должна обеспечивать:

- центральную роль **алгоритма расчета пульсинга и ровного фона**;
- простые пользовательские сценарии в Telegram;
- жесткое отделение **каталога препаратов** от **реестра пользователей**;
- предвычисляемое расписание протокола и reminder-систему;
- историю соблюдения протокола как отдельный слой правды;
- подключение блока анализов без разрушения core flow;
- AI-предварительную оценку как вспомогательный модуль, а не центр продукта;
- передачу кейса специалисту уже с собранной историей;
- рост в сторону модуля мужского здоровья и лабораторных интеграций без разрушения ядра.

Центральное правило архитектуры:

> **Главная ценность продукта — не интерфейс, не каталог и не AI, а математически точный движок, удерживающий максимально ровный фон на заданном протоколе.**

Все остальные контуры должны усиливать этот движок, а не размывать его.

---

## 3. Архитектурные принципы

### 3.1 Telegram-first

Основная модель взаимодействия — Telegram bot flow.

Продукт не должен зависеть от Mini App / Web App в v1.
Это допустимое расширение позже, но не блокер для core value.

### 3.2 Algorithm-first

Продукт должен строиться вокруг `pulse_engine`.

Это означает:

- user-facing сценарии подчинены логике расчета;
- reminders строятся из предвычисленного расписания;
- AI, labs и specialist flow не определяют core truth протокола;
- каталог существует для того, чтобы кормить движок корректными данными.

### 3.3 Domain-first, transport-second

Система моделируется вокруг доменных понятий, а не вокруг Telegram callbacks, ORM convenience или UI shortcuts.

### 3.4 Bounded contexts first, physical extraction later

Логическая модульность должна быть с самого начала.
Физическое разделение на сервисы / отдельные БД допускается только при реальной необходимости.

### 3.5 Transactional truth vs derived views

Архитектура должна жестко различать:

- transactional truth;
- projections/read models;
- analytics projections;
- specialist-facing summaries;
- AI summaries.

Ни одна derived view не может молча стать бизнес-истиной.

### 3.6 Event-aware design

Значимые изменения должны оформляться как события, чтобы:

- reminders;
- adherence tracking;
- analytics;
- AI triage;
- specialist case routing

могли эволюционировать без прямой грязной сцепки с core flow.

### 3.7 Graceful degradation

Система должна продолжать работать, даже если временно недоступны:

- AI-слой;
- OCR;
- аналитика;
- specialist queue;
- внешние интеграции.

Если `pulse_engine`, `protocols` и `reminders` работают, продукт сохраняет основную ценность.

### 3.8 User safety through constrained freedom

Обычный пользователь не должен получать полную свободу ручного управления сложной математикой протокола.

Свобода дается:

- через выбор препаратов;
- weekly target;
- длительность;
- ограничения по объему и удобству;
- выбор preset.

Детальная ручная раскладка по веществам и интервалам — это **specialist mode**, а не обычный сценарий.

---

## 4. Контурная карта системы

CycleSync состоит из следующих первичных bounded contexts:

1. **Compound Catalog**
2. **User Registry**
3. **Protocols**
4. **Pulse Engine**
5. **Reminders**
6. **Adherence**
7. **Labs**
8. **AI Triage**
9. **Expert Cases**
10. **Analytics**
11. **Integrations** (позже)

Эти контексты неравнозначны по критичности.

### 4.1 Критичность по слоям

#### Tier A: mission-critical core

- Compound Catalog
- User Registry
- Protocols
- Pulse Engine
- Reminders
- Adherence

#### Tier B: safety and support layer

- Labs
- AI Triage
- Expert Cases

#### Tier C: optimization and growth layer

- Analytics
- lab integrations
- men's health module
- advanced visualizations

Архитектура должна быть устроена так, чтобы Tier C не ломал Tier A.

---

## 5. Высокоуровневые системные контуры

### 5.1 User contour

Отвечает за пользовательское взаимодействие.

Основные возможности:

- выбор препаратов;
- создание протокола;
- выбор preset / ограничений;
- просмотр pulse-plan;
- reminders;
- done / snooze / skip;
- просмотр истории соблюдения;
- загрузка анализов;
- запрос на передачу кейса специалисту.

### 5.2 Specialist contour

Отвечает за работу специалиста с уже собранным кейсом.

Основные возможности:

- открытие кейса пользователя;
- просмотр текущего протокола;
- просмотр adherence-истории;
- просмотр анализа и AI summary;
- ответ пользователю;
- follow-up рекомендации;
- опционально specialist-mode корректировка протокола позже.

### 5.3 Catalog / content contour

Отвечает за поддержку базы препаратов.

Основные возможности:

- ведение Google Sheets;
- обновление веществ, брендов, концентраций, half-life;
- управление справочными параметрами;
- контроль качества контента.

Важно: этот контур **не ведет пользователей**, а только математическую справочную базу.

### 5.4 Owner / operations contour (позже)

Отвечает за visibility и управленческие сводки.

Основные возможности:

- активные протоколы;
- adherence metrics;
- lab uploads;
- escalations;
- conversion to specialist;
- популярные preset profiles;
- частота risk flags.

---

## 6. Общая слоистая структура системы

### Layer 1. Interface layer

Граница взаимодействия.

Компоненты:

- `UserBot`
- `SpecialistBot` или specialist panel adapter
- worker-triggered Telegram notifications
- будущие интерфейсы позже

Ответственности:

- прием Telegram updates;
- command / callback routing;
- запуск conversation entry points;
- rendering сообщений и карточек;
- сбор пользовательского input;
- передача управления в application layer.

Правила:

- никаких тяжелых доменных расчетов в handlers;
- никаких прямых SQL в Telegram handlers;
- никаких прямых AI-решений внутри UI маршрутов;
- handlers — только тонкие точки входа.

### Layer 2. Application layer

Оркестрация use cases между контекстами.

Примеры use cases:

- register user
- search compound
- create protocol draft
- compute pulse plan
- confirm protocol
- schedule reminder chain
- record reminder action
- upload lab report
- create AI assessment
- open expert case
- send specialist reply
- build adherence summary

Правила:

- может координировать несколько контекстов;
- не должен превращаться в свалку правил;
- использует repositories/contracts, а не raw soup logic;
- публикует события, если есть downstream consumers.

### Layer 3. Domain layer

Здесь живут доменные понятия и правила.

Каждый bounded context определяет:

- entities;
- value objects;
- domain services;
- repositories/contracts;
- domain events;
- invariants.

Именно здесь закрепляется продуктовая логика.

### Layer 4. Projections / read-model layer

Содержит derived views, оптимизированные для:

- поиска по каталогу;
- user history;
- adherence summaries;
- specialist case overviews;
- analytics;
- owner views позже.

Правила:

- projections могут быть eventually consistent;
- projections не заменяют transactional truth;
- projections должны быть перестраиваемыми.

### Layer 5. Infrastructure layer

Содержит технические реализации:

- PostgreSQL;
- Redis / queue mechanism;
- Google Sheets adapter;
- OCR adapter;
- LLM adapter;
- object/file storage;
- background workers;
- observability;
- outbox transport.

Правила:

- инфраструктура не должна протекать в домен;
- внешние интеграции должны быть изолированы контрактами.

---

## 7. Bounded context specification

## 7.1 Compound Catalog

### Ответственности

- каталог веществ;
- бренды;
- концентрации;
- эфиры;
- half-life;
- ограничения по объему;
- опорные справочные значения для движка;
- синк из Google Sheets.

### Core entities

- `Compound`
- `CompoundBrand`
- `CompoundSpec`
- `CatalogSyncRun`

### Owned data

Этот контекст владеет **справочной truth** по препаратам.

### Не владеет

- пользовательской историей;
- протоколами;
- расписаниями;
- анализами;
- specialist cases.

---

## 7.2 User Registry

### Ответственности

- канонический пользовательский профиль;
- базовые настройки;
- timezone;
- ограничения и предпочтения;
- статус пользователя;
- связь с Telegram identity.

### Core entities

- `User`
- `UserProfile`
- `UserPreference`
- `UserLimitProfile`

### Owned data

Контекст владеет identity и базовыми параметрами пользователя.

### Не владеет

- каталогом веществ;
- логикой расчета;
- расписаниями;
- экспертными заключениями.

---

## 7.3 Protocols

### Ответственности

- создание и хранение протокола;
- набор выбранных препаратов;
- weekly target / duration;
- выбранный preset;
- ограничения по объему / частоте;
- protocol lifecycle;
- связь протокола с pulse-plan.

### Core entities

- `Protocol`
- `ProtocolCompound`
- `ProtocolConstraint`
- `ProtocolPreset`

### Принцип

`Protocols` описывает **что пользователь хочет пройти**, но не владеет математикой расчета ритма.

Эта математика принадлежит `Pulse Engine`.

---

## 7.4 Pulse Engine

### Ответственности

- алгоритм расчета ровного фона;
- работа с half-life, concentration, volume constraints;
- расчёт pulse-plan;
- выбор / применение preset logic;
- генерация предвычисленного расписания;
- расчет summary показателей устойчивости.

### Core entities / concepts

- `PulsePlan`
- `PulsePlanLine`
- `InjectionWindow`
- `PulsePresetStrategy`
- `FlatnessScore`

### Важный принцип

`Pulse Engine` — **ядро всей системы**.

Если бы пришлось выбирать один домен, который обязан быть идеальным в v1, это был бы именно он.

### Preset strategies

На уровне архитектуры должны быть поддержаны разные стратегии:

- `Unified Rhythm`
- `Layered Pulse`
- `Golden Pulse / Conveyor`

Детальные формулы выносятся в отдельный документ по алгоритму.

---

## 7.5 Reminders

### Ответственности

- генерация reminder chain из подтвержденного pulse-plan;
- планирование уведомлений;
- отправка напоминаний;
- reschedule / snooze behavior;
- контроль notification state.

### Core entities

- `ReminderEvent`
- `ReminderDispatch`
- `ReminderSchedule`
- `ReminderActionState`

### Важный принцип

Reminders не “дополняют” протокол, а **исполняют его во времени**.

---

## 7.6 Adherence

### Ответственности

- фиксация done / snooze / skip;
- история соблюдения;
- агрегаты дисциплины;
- user-facing и specialist-facing summaries;
- связь нарушений дисциплины с протоколом.

### Core entities

- `AdherenceLog`
- `AdherenceSummary`
- `MissedAction`
- `ProtocolComplianceSnapshot`

### Важный принцип

Adherence — это не UI-логи, а отдельная доменная правда о том, **что реально было исполнено**.

---

## 7.7 Labs

### Ответственности

- загрузка анализов;
- хранение lab reports;
- структурированные маркеры;
- связи с датами и протоколами;
- история изменений по анализам.

### Core entities

- `LabReport`
- `LabMarker`
- `LabMarkerValue`
- `LabAttachment`

### Принцип

Labs хранят **сырые и структурированные данные анализов**, но не владеют AI-интерпретацией.

---

## 7.8 AI Triage

### Ответственности

- OCR/parse intake orchestration;
- структурирование анализа;
- сравнение с историей;
- выделение risk flags;
- AI summary;
- подготовка кейса для специалиста.

### Core entities

- `AIAssessment`
- `RiskFlag`
- `TrendObservation`
- `AssessmentSummary`

### Принцип

AI Triage — это вспомогательный safety layer.

Он **не владеет** протоколом, не заменяет специалиста и не является главным differentiator продукта.

---

## 7.9 Expert Cases

### Ответственности

- открытие кейса специалисту;
- сбор контекста пользователя;
- specialist communication thread;
- follow-up decisions;
- история экспертного сопровождения.

### Core entities

- `ExpertCase`
- `ExpertCaseContext`
- `ExpertMessage`
- `ExpertRecommendation`

### Принцип

Specialist flow работает **поверх**:

- протокола;
- pulse-plan;
- adherence history;
- lab history;
- AI summary.

Он не должен переопределять ядро продукта.

---

## 7.10 Analytics

### Ответственности

- event ingestion;
- projections по активным протоколам;
- adherence metrics;
- reminder metrics;
- lab upload metrics;
- escalation metrics;
- preset usage metrics.

### Core concepts

- `AnalyticsEvent`
- `MetricProjection`
- `SegmentProjection`

### Принцип

Analytics — derived layer, не transactional truth.

---

## 7.11 Integrations (later)

### Потенциальные интеграции

- лаборатории типа Synevo;
- платежные провайдеры;
- внешние specialist workflows;
- calendars;
- external health-data sinks.

Все интеграции должны сидеть за контрактами/gateways.

---

## 8. Правила владения данными

### 8.1 Источник правды по транзакционным данным

| Context | Owns truth for |
|---|---|
| Compound Catalog | справочная база веществ и их параметров |
| User Registry | identity и базовые параметры пользователя |
| Protocols | состав и параметры протокола |
| Pulse Engine | рассчитанный pulse-plan |
| Reminders | scheduling / dispatch state напоминаний |
| Adherence | фактическое исполнение / нарушение |
| Labs | сами анализы и маркеры |
| Expert Cases | экспертные кейсы и ответы |

### 8.2 Derived data ownership

| Layer | Purpose |
|---|---|
| Catalog search projection | быстрый поиск по каталогу |
| User protocol summary | быстрый обзор активной схемы |
| Adherence summary | дисциплина и нарушения |
| Specialist case summary | condensed case view |
| Analytics projections | KPI и метрики |

### 8.3 Главное правило

Ни AI summary, ни specialist case overview, ни analytics projection не могут стать единственным trusted source of truth.

---

## 9. Data architecture strategy

### 9.1 Initial approach

Рекомендуемая архитектура на старте:

- одна primary PostgreSQL database / cluster;
- schema-level logical separation по контекстам;
- отдельный search/projection subsystem при необходимости;
- object/file storage для анализов и вложений;
- async worker mechanism;
- Google Sheets sync в каталог;
- projections строятся отдельно от write-model.

### 9.2 Почему не много БД сразу

Много физических БД на старте дадут:

- лишнюю операционную нагрузку;
- overhead миграций;
- рост сложности дебага;
- premature fragmentation.

### 9.3 Когда extraction будет оправдан

Отдельный context можно физически выносить позже, если:

- резко расходится profile нагрузки;
- нужен отдельный release cadence;
- появляются интеграционные причины для изоляции;
- specialist/lab layer растет быстрее core;
- analytics начинает давить на primary DB.

### 9.4 Suggested schema-level separation

Иллюстративно:

- `compound_catalog`
- `user_registry`
- `protocols`
- `pulse_engine`
- `reminders`
- `adherence`
- `labs`
- `expert_cases`
- `analytics_raw`
- `analytics_views`

---

## 10. Event architecture

Система должна строиться вокруг meaningful domain events.

### 10.1 Примеры ключевых событий

- `user_registered`
- `compound_catalog_synced`
- `protocol_created`
- `protocol_confirmed`
- `pulse_plan_computed`
- `pulse_plan_recomputed`
- `reminder_scheduled`
- `reminder_sent`
- `reminder_done`
- `reminder_snoozed`
- `reminder_skipped`
- `lab_uploaded`
- `lab_structured`
- `ai_assessment_created`
- `expert_case_opened`
- `expert_reply_sent`

### 10.2 Event consumers

Возможные consumers:

- reminder scheduler;
- adherence aggregator;
- AI triage pipeline;
- specialist case builder;
- analytics projections;
- owner insights later.

### 10.3 Reliability requirements

Событийная система должна поддерживать:

- outbox pattern или эквивалент;
- retry strategy;
- idempotent handlers;
- dead-letter visibility later;
- projection rebuildability.

---

## 11. Search architecture

Search для CycleSync — это не общий web-search, а прикладной retrieval layer.

### 11.1 Search target scope (v1)

В v1 поиск в первую очередь должен покрывать:

- compound catalog;
- user lookup для specialist side;
- активные протоколы / recent activity;
- быстрый доступ к user case context.

### 11.2 Search normalization requirements

Должны поддерживаться:

- case normalization;
- whitespace cleanup;
- brand / compound tokenization;
- alias tokens later;
- transliteration later if needed;
- recent usage weighting where useful.

### 11.3 Fallback rule

Если search subsystem временно недоступен:

- каталог должен быть доступен через fallback DB lookup;
- specialist side должен иметь reduced, но working user lookup;
- core operations не должны останавливаться.

---

## 12. Reminder and adherence architecture

Reminders и Adherence — это связанная архитектурная подсистема.

### 12.1 Почему это central capability

Даже идеальный pulse-plan не имеет ценности, если пользователь его не исполняет.

Значит архитектурно система должна:

- хранить предвычисленный schedule;
- планировать notifications;
- отслеживать пользовательское действие;
- строить compliance truth;
- показывать discipline state пользователю и специалисту.

### 12.2 Reminder chain concept

После подтверждения протокола:

1. создается pulse-plan;
2. pulse-plan преобразуется в reminder events;
3. worker dispatches reminders по времени;
4. пользователь отвечает done / snooze / skip;
5. response записывается в adherence layer;
6. downstream layers видят дисциплину.

### 12.3 Key rule

Reminder state и Adherence state — это не одно и то же.

- `Reminder` знает, что было отправлено и когда.
- `Adherence` знает, что реально сделал пользователь.

---

## 13. Labs, AI and specialist architecture

Это safety/support контур, построенный поверх core value.

### 13.1 Labs intake flow

1. пользователь загружает PDF / фото / manual values;
2. attachment хранится отдельно;
3. markers структурируются;
4. report связывается с user и protocol context;
5. downstream AI получает материал для triage.

### 13.2 AI triage flow

1. structured lab data + history;
2. comparison vs previous results;
3. risk flags;
4. trend summary;
5. specialist-ready summary.

### 13.3 Expert case flow

1. пользователь или система открывает кейс;
2. кейс собирает pulse-plan, adherence, labs, AI summary;
3. специалист получает condensed view;
4. ответ возвращается пользователю;
5. история кейса сохраняется.

### 13.4 Rule of non-blocking core

Если AI/Expert layer временно недоступен:

- core протоколы;
- pulse-plan;
- reminders;
- adherence tracking

должны продолжать работать.

---

## 14. Resilience and degradation model

### 14.1 Degradation rules

Если AI недоступен:

- протоколы и reminders продолжают работать;
- labs сохраняются;
- AI assessment можно создать позже.

Если OCR недоступен:

- остается manual input fallback.

Если specialist queue недоступна:

- пользователь получает статус ожидания;
- core protocol flow не ломается.

Если analytics lagging:

- core user/specialist flows продолжают работать.

Если Google Sheets недоступен:

- используется последняя кэшированная версия каталога;
- sync retry запускается позже.

### 14.2 Isolation strategy

Не-core side effects должны быть asynchronous там, где это возможно.

### 14.3 Idempotency

Все event consumers должны быть идемпотентны.

### 14.4 Rebuildability

Derived projections должны быть rebuildable.

---

## 15. Suggested technical building blocks (non-binding)

### Transactional core

- PostgreSQL

### Async/background processing

- worker queue / job processing mechanism

### Cache / scheduling aid

- Redis or equivalent

### File/media storage

- object storage / S3-compatible or equivalent

### Bot application

- aiogram-based Telegram bot layer

### Observability

- structured logging
- metrics
- health checks
- projection lag visibility later

### Integrations

- Google Sheets adapter
- OCR adapter
- LLM adapter
- later lab provider adapter

Эти решения вторичны по отношению к архитектурным границам.

---

## 16. Suggested repository structure (illustrative)

```text
cyclesync/
  app/
    bots/
      user_bot/
      specialist_bot/
    application/
      compound_catalog/
      user_registry/
      protocols/
      pulse_engine/
      reminders/
      adherence/
      labs/
      ai_triage/
      expert_cases/
      analytics/
    domain/
      compound_catalog/
      user_registry/
      protocols/
      pulse_engine/
      reminders/
      adherence/
      labs/
      ai_triage/
      expert_cases/
      analytics/
    infrastructure/
      db/
      queue/
      storage/
      sheets/
      ocr/
      llm/
      integrations/
    projections/
      catalog/
      adherence/
      analytics/
      specialist/
    workers/
  docs/
    10_architecture.md
    20_domain_model.md
    ...
```

Финальная структура может отличаться, но intent separation должен сохраниться.

---

## 17. Что v1 обязан защитить архитектурно

Даже в первом релизе нужно защитить:

- centrality of `pulse_engine`;
- разделение `compound_catalog` и `user_registry`;
- protocols как самостоятельный домен;
- reminders и adherence как отдельные слои;
- labs / AI / specialist как non-blocking second layer;
- projections как derived, а не authoritative views;
- graceful degradation при частичных сбоях;
- event-aware extensibility.

Даже если реализация маленькая, архитектура уже должна позволять расти, не разваливая spine.

---

## 18. Что намеренно вынесено в отдельные документы

Отдельно должны быть описаны:

- detailed domain model;
- detailed protocol lifecycle;
- detailed pulse presets and formulas;
- detailed data model;
- reminder/adherence state machines;
- AI triage prompt/contracts;
- expert case workflow;
- analytics metric catalog;
- integrations contracts;
- deployment topology;
- testing strategy;
- rollout / PR plan.

Это разделение сознательное и не дает architecture doc превратиться в свалку.

---

## 19. Финальное архитектурное утверждение

CycleSync должен быть построен как **Telegram-first, layered, modular, math-centered operating system** для сопровождения пользователей на фармакологических протоколах.

Его архитектура обязана гарантировать, что:

- `pulse_engine` остается центром продукта;
- каталог препаратов служит движку, а не смешивается с user data;
- reminders и adherence превращают расчет в реальное исполнение;
- анализы, AI и specialist flow усиливают систему, но не подменяют ее;
- derived layers остаются derived layers;
- частичные сбои деградируют мягко, а не валят весь продукт.

Этот документ фиксирует технический spine системы.
