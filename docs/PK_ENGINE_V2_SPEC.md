# PK_ENGINE_V2_SPEC.md

## 1. Назначение

`PK_ENGINE_V2_SPEC.md` фиксирует целевую модель следующей версии расчетного ядра CycleSync.

Цель V2:
- перейти от текущей **product-level weighted model** к **ingredient-aware / ester-aware PK engine**;
- считать mixed products не как “один продукт с одним effective half-life”, а как сумму отдельных компонентных кривых;
- дать системе честную математику для:
  - `auto_pulse`
  - `stack_smoothing`
  - `total_target`
  - `inventory_constrained`
- сохранить расчет practical и объяснимым, не превращая его в псевдоклинический симулятор всего мира.

## 2. Почему нужен V2

Текущий движок уже полезен, но у него есть ограничение:

### Сейчас
- продукт считается как единая сущность;
- mixed products учитываются через ingredient-aware weighting;
- итоговая кривая строится на product-level, не на уровне отдельных эфиров.

### Проблема
Для продуктов типа:
- Sustanon
- Pharma Mix 1
- любых “миксов”
мы теряем точность:
- короткие эфиры и длинные эфиры сглаживаются в одну усредненную модель;
- flatness/stability оценивается не по реальной сумме кривых, а по сглаженной замене.

### Зачем V2
V2 нужен, чтобы:
- считать вклад каждого ингредиента/эфира отдельно;
- суммировать их в общую концентрационную кривую;
- уже на этой реальной сумме оценивать:
  - flatness,
  - pulsing quality,
  - необходимость более частого введения,
  - компромиссы при inventory constraints.

## 3. Scope V2

## 3.1. Что делаем в V2
В V2 делаем:

1. **Per-ingredient / per-ester simulation**
2. **Parent-substance aware aggregation**
3. **Ingredient-level half-life**
4. **Ingredient-level active fraction**
5. **Product schedule planning with PK evaluation on aggregated curves**
6. **Real flatness scoring from simulated curves**
7. **Mode-aware planning for existing input modes**
8. **Support for mixed products like Pharma Mix 1 / Sustanon**
9. **Practical explainable metrics for users and specialists**

## 3.2. Что НЕ делаем в V2
В V2 не делаем:

- сложные bioavailability models;
- tissue compartment modeling;
- receptor occupancy modeling;
- super-exotic release profiles;
- fully individualized physiology;
- disease-state medicine simulator;
- interaction model between oils/solvents in same syringe;
- sterility / solvent compatibility validator;
- clinical recommendation engine.

## 4. Fundamental modeling principles

## 4.1. Unit of pharmacokinetic truth
Главная единица расчета в V2 — это **ingredient row**, а не product row.

Один продукт может содержать:
- 1 ingredient
- 2 ingredients
- 3 ingredients
- 4+ ingredients

Каждый ingredient моделируется отдельно.

## 4.2. Product remains UI/business object
Продукт всё еще остается:
- объектом каталога,
- объектом выбора в Draft,
- единицей назначения в расписании.

Но PK engine внутри продукта видит **ingredient set**, а не одну усредненную массу.

## 4.3. Schedule is still product-level
Даже в V2 user schedule остается привязанным к продуктам и событиям введения.

То есть:
- событие введения происходит по продукту;
- внутри этого события product dose раскладывается по ingredient rows;
- затем engine моделирует кривые компонент.

Это важно, потому что продуктовый UX должен оставаться practical.

## 5. Required input data from workbook V2

PK V2 relies on `Ingredients` sheet.

Для каждого ingredient нужны как минимум:

- `product_key`
- `ingredient_order`
- `parent_substance`
- `ingredient_name`
- `ester_name`
- `basis`
- `amount_per_ml_mg` or `amount_per_unit_mg`
- `half_life_days`
- `active_fraction`
- `is_pulse_driver`
- optional:
  - `tmax_hours`
  - `release_model`
  - guidance fields

## 5.1. Parent substance
`parent_substance` нужен, чтобы:
- агрегировать отдельные эфиры одного базового вещества;
- строить итоговые curves и summaries не только по ingredient, но и по substance.

Пример:
- Testosterone Phenylpropionate
- Testosterone Cypionate
оба сворачиваются в parent substance `Testosterone`.

## 5.2. Active fraction
`active_fraction` обязателен.

Зачем:
- ингредиент хранится как esterified / formulated component;
- для more honest active payload analysis нужно отделять:
  - nominal mg of esterified ingredient
  - effective active payload

MVP правило:
- schedule planning и catalog dosage semantics могут использовать nominal formulation mg;
- PK summaries и advanced analytics должны уметь считать active-equivalent layer через `active_fraction`.

## 5.3. Half-life
`half_life_days` обязателен на уровне ингредиента.

Это основной MVP PK driver.

## 5.4. tmax
`tmax_hours` — optional в V2 MVP.

Если нет:
- используем упрощенный default release assumption.

Если есть:
- используем для более realistic first-rise shaping.

## 6. Core mathematical model

## 6.1. Base release/decay model
MVP V2 использует упрощенную PK-модель:

- first-order release / decay
- per ingredient
- event-based accumulation
- discrete time sampling over planning horizon

Это достаточно practical, честно и воспроизводимо.

## 6.2. Simulation horizon
Horizon должен покрывать:
- duration of protocol
- плюс хвост для post-dose carryover if needed for stability assessment

Минимальный practical horizon:
- whole protocol duration
- plus optional tail window for metrics if calculation mode requires it

## 6.3. Time resolution
Recommended MVP:
- internal simulation at hourly or sub-daily resolution
- user-facing schedule still day/event based

Нельзя считать flatness только по грубым day points, если хотим реально улучшить V1.

## 6.4. Dose event decomposition
Каждое product-level введение раскладывается на ingredient doses.

Для injectables:
- `event_volume_ml × amount_per_ml_mg` for each ingredient

Для tablet/capsule products:
- `event_unit_count × amount_per_unit_mg`

## 6.5. Ingredient curve
Для каждого event × ingredient строится contribution curve.

Итог по ингредиенту:
- сумма всех его event contributions over time

Итог по продукту:
- сумма ingredient curves продукта

Итог по protocol:
- сумма всех product curves

## 6.6. Parent-substance aggregation
Отдельно считаем aggregated curves by `parent_substance`.

Это нужно, чтобы:
- видеть реальный суммарный Testosterone curve
- видеть реальный суммарный Boldenone curve
- и т.д.

Особенно важно для mixed products.

## 7. Supported product patterns

## 7.1. Simple single-ingredient product
Пример:
- Masteron Enanthate
- Testosterone Enanthate
- Boldenone Undecylenate

Модель:
- одна ingredient curve
- product curve = ingredient curve

## 7.2. Mixed ester / mixed ingredient product
Пример:
- Sustanon
- Pharma Mix 1

Модель:
- одна product event
- несколько ingredient curves
- итоговая product curve = их сумма
- итоговые parent-substance curves могут частично агрегироваться между ингредиентами

## 7.3. Multi-product stack
Если user выбирает несколько продуктов:
- каждый product имеет свои events
- каждый event decomposed into ingredient curves
- protocol curve = sum of all product curves
- parent-substance summary aggregates across products and across ingredients

## 8. Input modes and V2 behavior

## 8.1. `auto_pulse`
User задает:
- selected products
- duration
- constraints
- preset

System:
- берет guidance from ingredients/products
- proposes product-level event schedule
- evaluates resulting PK using V2 ingredient-aware simulator

## 8.2. `total_target`
User задает:
- selected products
- total weekly mg target
- duration
- constraints
- preset

System:
- decides product allocation
- builds product-level events
- validates/evaluates with ingredient-aware PK curves

## 8.3. `stack_smoothing`
User задает:
- fixed per-product weekly composition
- duration
- constraints
- preset

System:
- НЕ меняет composition
- only optimizes event pattern
- evaluates actual PK from ingredient curves

Это один из самых важных beneficiaries V2.

## 8.4. `inventory_constrained`
User задает:
- stock constraints
- duration
- constraints
- preset

System:
- builds best-effort schedule within stock limits
- evaluates actual PK with degradation flags

## 9. Presets and V2

Existing presets remain:

- `unified_rhythm`
- `layered_pulse`
- `golden_pulse`

But in V2 they are reinterpreted as:

### `unified_rhythm`
- simpler pattern
- fewer injections
- evaluate real PK after schedule proposal

### `layered_pulse`
- slightly more distributed layer smoothing
- evaluate real PK of mixed products more honestly

### `golden_pulse`
- most aggressive smoothing within constraints
- V2 should especially improve this preset for mixed ester stacks

Important:
Presets remain **schedule strategies**, not PK models.

## 10. Flatness / stability metrics in V2

## 10.1. Current problem
V1 flatness is not based on real summed ingredient curves.

## 10.2. V2 rule
Flatness/stability must be calculated from simulated concentration series.

### Core metrics
Recommended:
- peak-to-trough variability
- coefficient of variation over stable interval
- max single-step jump
- time-in-target-band if target semantics available

### User-facing simplification
User still sees:
- one `flatness/stability score`

But this score must now come from:
- real PK simulation,
not weighted product approximation.

## 10.3. Warning flags
Need flags like:
- `mixed_ester_short_component_spikes`
- `constraint_forced_longer_interval`
- `inventory_forced_degradation`
- `injections_above_preference`
- `peak_trough_spread_high`

## 11. Practical output model

## 11.1. User-facing
User should not see 500 technical curves.

Need compact output:
- schedule
- overall flatness/stability
- injections/week
- max volume/event
- derived weekly totals
- warnings
- optionally compact per-substance weekly view

## 11.2. Specialist-facing / debug
Need richer output:
- per ingredient curves
- per parent-substance curves
- major peak/trough windows
- why this preset was chosen / degraded

## 11.3. Explainability
System must be able to explain in human terms:
- why one injection/week was accepted
- why more frequent pattern improves flatness
- why mixed ester products behave differently

## 12. Mixed products and real-world mixing

Иногда user physically combines multiple products into one injection event.

Важно:
- V2 engine **может** считать несколько active agents introduced at the same time;
- V2 engine **не** моделирует chemical compatibility of solvents/oils;
- V2 engine **не** validates storage/sterility behavior outside dose timing logic.

То есть:
- simultaneous event timing is supported in math;
- formulation safety/compatibility is explicitly out of scope.

Это должно быть честно указано в docs and warnings, not hidden.

## 13. Packaging / estimator relation

V2 PK engine should not absorb course estimator logic.

But PK v2 must expose enough truth for estimator:
- actual event doses
- per-product totals
- per-ingredient totals if needed
- protocol duration totals

Estimator then uses packaging semantics separately.

## 14. Validation requirements before calculation

Hard fail if:
- product selected but no ingredient rows
- ingredient missing `half_life_days`
- ingredient missing `active_fraction`
- injectables missing `amount_per_ml_mg`
- tablets missing `amount_per_unit_mg`
- invalid basis
- duration invalid
- impossible constraint configuration

Soft warnings if:
- `tmax_hours` missing
- guidance incomplete
- mixed product has sparse PK metadata
- schedule feasible but degraded

## 15. Backward compatibility strategy

We do **not** keep V1 workbook as primary format.

But rollout can be staged:

### Phase 1
- introduce workbook V2
- importer V2
- simulator V2 hidden behind flag

### Phase 2
- compare V1 vs V2 outputs on regression scenarios

### Phase 3
- make V2 default engine
- keep V1 only as temporary fallback if truly needed

Recommended:
- short-lived compatibility window
- not permanent dual-engine chaos

## 16. Regression requirements

V2 must ship with explicit regression pack.

Need minimum scenario coverage:
1. simple single-ester injectable
2. mixed ester product (Sustanon / Pharma Mix 1)
3. multi-product stack
4. `auto_pulse`
5. `stack_smoothing`
6. `inventory_constrained`
7. tablet product
8. constrained vs unconstrained comparison

Need compare:
- event count
- max volume
- flatness
- degradation flags
- per-substance totals

## 17. MVP acceptance criteria

V2 can be considered implemented when:

1. workbook V2 supplies ingredient-level PK fields;
2. importer V2 loads them correctly;
3. engine simulates ingredient-level curves;
4. mixed products are no longer reduced to one effective half-life;
5. flatness/stability is calculated from simulated curves;
6. existing input modes still work;
7. user-facing output remains compact and understandable;
8. regression scenarios pass.

## 18. Explicit non-goals

V2 is **not**:
- a hospital chemo simulator
- a universal medical pharmacology engine
- a compatibility validator for oils and solvents
- a substitute for clinical oversight
- a place for giant theoretical PK overengineering

## 19. Recommended implementation waves after this spec

### Wave A
- workbook V2
- importer V2
- seed data migration

### Wave B
- PK core simulator
- ingredient/ester-aware flatness scoring

### Wave C
- UI/reporting adaptation
- specialist-facing richer summaries
- regression pack hardening

---

**Итог:**  
PK Engine V2 должен перевести CycleSync из режима “умный weighted calculator” в режим **ingredient-aware practical pulse engine**, где миксы и эфиры считаются честно, но без превращения проекта в псевдонаучный монстр.
