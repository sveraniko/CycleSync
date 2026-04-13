# CycleSync Pulse Engine — PK Upgrade Specification

> Спецификация перехода от ingredient-aware weighted model к per-ester PK simulator  
> с полной моделью фасовки, human-readable выводом и ровным фоном.

---

## 1. Контекст и проблема

### 1.1. Текущее состояние движка

Текущий `PulseCalculationEngine` (`app/application/protocols/pulse_engine.py`, 762 строки) работает по модели **ingredient-aware weighted product allocation**:

1. **Единый effective half-life на продукт** — `_effective_half_life()` берёт все ингредиенты продукта, взвешивает их `half_life_days` по `amount_mg` и возвращает **одно число** (строки 626–658).
2. **Упрощённая модель decay** — `_calculate_flatness()` использует `exp(-0.693 * t / t½)` для **одного слоя** на продукт, а не для каждого эфира отдельно (строки 608–624).
3. **Аллокация в mg/week на продукт целиком** — `_resolve_allocation()` раздаёт mg/week на продукт, а не на каждый эфир.
4. **Schedule entries без per-ester PK** — `_generate_entries()` (строки 569–606) создаёт `PulsePlanEntry` с `computed_mg` = mg активного вещества суммарно, без разбивки по эфирам.

### 1.2. Почему это недостаточно

**Микс-продукты (blends)** содержат несколько эфиров с радикально разными half-life:

| Продукт (пример) | Эфиры | Half-life |
|---|---|---|
| Sustanon 250 | Test Propionate (1.2d), Test Phenylpropionate (2.5d), Test Isocaproate (4d), Test Decanoate (7.5d) | 1.2 — 7.5 дней |
| Tri-Tren 200 | Tren Acetate (1d), Tren Enanthate (4.5d), Tren Hexahydrobenzylcarbonate (6d) | 1 — 6 дней |

Единый weighted half-life ~4 дня для Sustanon — **математическая фикция**. В реальности:
- Propionate выходит на пик через 12 часов и исчезает через 3 дня
- Decanoate набирает уровень медленно и держится неделю

Текущая модель не может отразить этот наложенный фармакокинетический профиль. Результат: flatness score врёт, schedule не оптимален.

### 1.3. Проблемы фасовки и human-readable вывода

Параллельно, `CourseEstimatorService` (`course_estimator.py`, 170 строк) выдаёт:
- `package_count_required` как Decimal (например `2.4000`)
- `package_count_required_rounded` через `ROUND_CEILING`

Но **модель фасовки неполная**:
- `package_kind` поддерживает только `vial | ampoule | tablet | capsule`
- Нет понятия «ампулы в коробке», «блистеры в коробке», «баночка = 1 шт»
- Нет multi-level packaging: 10 ампул × 1ml в коробке, 3 блистера × 10 таблеток в коробке
- Нет human-readable округления: `0.4 флакона` — абсурд, никто не покупает 0.4 флакона

---

## 2. Целевая архитектура

### 2.1. Per-ester PK simulator

Вместо одного decay-слоя на продукт — **отдельная кривая на каждый эфир** (ester).

```
Total_level(t) = Σ [ Σ C_ester_j(t) ]   для каждого продукта и каждого эфира
                  product  ester

C_ester(t) = Σ dose_ester_i · exp(-ln2 · (t - t_injection_i) / t½_ester)
             для всех инъекций i до момента t
```

Где:
- `dose_ester_i` — доля эфира в разовой инъекции (из composition)
- `t½_ester` — half-life конкретного эфира
- `t_injection_i` — момент инъекции

### 2.2. Что это даёт

1. **Честный flatness score** — минимизация CV (coefficient of variation) суммарной кривой `Total_level(t)`, а не фиктивной средневзвешенной
2. **Оптимальный phase offset** — `_optimize_phase_offsets()` будет двигать фазы на основе реального PK-профиля, а не агрегата
3. **Корректное обнаружение пиков и впадин** — система сможет показать пользователю: «вот здесь короткий эфир уже ушёл, а длинный ещё не добрал»
4. **Правильные volume и frequency решения** — при split-дозе коротких и длинных эфиров

---

## 3. Модель данных — расширение ингредиентов

### 3.1. Текущая модель `CompoundIngredient`

```python
class CompoundIngredient:
    ingredient_name: str          # "Testosterone Enanthate"
    amount: Decimal               # 250 (mg per ml или per tablet)
    unit: str                     # "mg"
    basis: str                    # "per_ml" | "per_unit"
    half_life_days: Decimal       # 4.5
    is_pulse_driver: bool
    dose_guidance_*: Decimal      # min/max/typical
```

### 3.2. Необходимые дополнения

```python
class CompoundIngredient:
    # --- существующие поля ---
    ingredient_name: str
    amount: Decimal
    unit: str
    basis: str
    half_life_days: Decimal
    is_pulse_driver: bool
    dose_guidance_*: Decimal

    # --- новые поля ---
    ester_name: str | None        # "Enanthate", "Propionate", None для не-эфирных
    parent_substance: str | None  # "Testosterone", "Trenbolone", "Nandrolone"
    active_fraction: Decimal | None  # доля чистого вещества (0.72 для Enanthate, 0.80 для Propionate)
    release_model: str            # "first_order" (default) | "zero_order" | "biphasic"
    tmax_hours: Decimal | None    # время до пиковой концентрации после инъекции
    bioavailability: Decimal | None # для oral: 0.05–0.15 для testosterone undecanoate oral
```

### 3.3. Зачем `active_fraction`

Testosterone Enanthate — это не 100% тестостерон. Это эфир с молекулярным хвостом.
- Testosterone Propionate → ~83% чистый тестостерон (MW test / MW ester = 288/344)
- Testosterone Enanthate → ~72% (288/400)
- Testosterone Decanoate → ~62% (288/462)

Это значит: 250mg Test E = ~180mg чистого testosterone.
Без `active_fraction` engine сравнивает яблоки с апельсинами при аллокации между продуктами с разными эфирами.

### 3.4. Зачем `parent_substance`

Для правильной агрегации PK-кривых: «ровный фон testosterone» требует суммирования **только** testosterone-эфиров, а не смешивания testosterone + nandrolone в одну кривую. У них разные рецепторы, разные эффекты.

---

## 4. Новая PK-модель расчёта

### 4.1. Архитектура `EsterPKSimulator`

```python
@dataclass(slots=True)
class EsterPKProfile:
    """PK-профиль одного эфира в одном продукте."""
    product_id: UUID
    ester_name: str
    parent_substance: str
    half_life_days: Decimal
    active_fraction: Decimal
    amount_per_unit: Decimal    # mg эфира в 1 ml или 1 tablet
    active_mg_per_unit: Decimal # = amount_per_unit × active_fraction
    is_pulse_driver: bool


@dataclass(slots=True)
class PKTimePoint:
    """Одна точка суммарной кривой."""
    time_hours: float
    total_active_level: float           # суммарный уровень всех веществ
    per_substance_level: dict[str, float]  # {"Testosterone": 142.3, "Nandrolone": 87.1}
    per_ester_level: dict[str, float]      # {"Test E": 102.1, "Test P": 40.2, ...}


class EsterPKSimulator:
    """Per-ester pharmacokinetic simulator."""

    RESOLUTION_HOURS: int = 6  # шаг симуляции: каждые 6 часов

    def simulate(
        self,
        *,
        ester_profiles: list[EsterPKProfile],
        injection_events: list[InjectionEvent],
        duration_days: int,
    ) -> list[PKTimePoint]:
        """
        Моделирует суммарную концентрацию для каждого временного шага.
        Каждый injection_event содержит: day_offset, volume_ml, product_id.
        """
        ...

    def calculate_flatness(self, curve: list[PKTimePoint]) -> FlatnessMetrics:
        """
        Рассчитывает метрики ровности фона.
        """
        ...
```

### 4.2. Модель decay — first-order kinetics

Для каждого эфира `j`, каждой инъекции `i`:

```
C_j(t) = (dose_j_i × active_fraction_j) × exp(-ln2 × (t - t_i) / t½_j)

Total_substance_s(t) = Σ C_j(t)  для всех j с parent_substance = s
Total(t) = Σ Total_substance_s(t)
```

### 4.3. Flatness metrics — расширение

Текущий flatness: один CoV score.

Новые метрики:

```python
@dataclass(slots=True)
class FlatnessMetrics:
    overall_cv: Decimal              # CoV суммарной кривой (0 = идеально ровно)
    overall_flatness_score: Decimal  # 100 - cv*100, как сейчас

    per_substance_cv: dict[str, Decimal]       # {"Testosterone": 0.12, "Nandrolone": 0.08}
    per_substance_flatness: dict[str, Decimal]  # {"Testosterone": 88, "Nandrolone": 92}

    peak_trough_ratio: Decimal       # max/min суммарной кривой
    trough_hours_from_last_injection: Decimal  # когда достигается минимум
    steady_state_reached_day: int | None  # день, после которого CV < 5%

    per_ester_contribution: dict[str, Decimal]  # доля каждого эфира в среднем уровне
```

### 4.4. Оптимизация: что меняется

Текущий `_optimize_phase_offsets()` перебирает фазы и оценивает flatness. Модель не меняется, но:
- Внутри flatness теперь per-ester симуляция
- Optimization target: minimize `overall_cv` + penalty за `per_substance_cv` > threshold
- Новый constraint: `peak_trough_ratio < 2.0` (пик не более чем вдвое выше впадины)

---

## 5. Интеграция с текущим engine

### 5.1. Стратегия: обёртка, не замена

Текущий `PulseCalculationEngine` остаётся рабочим. Новый `EsterPKSimulator`:
1. Вызывается **после** `_generate_entries()` для **уточнения** flatness-метрик
2. Вызывается **внутри** `_optimize_phase_offsets()` для корректной оценки кандидатов
3. Не ломает существующий flow: validate → allocate → build → optimize → generate

### 5.2. Маршрут вызова

```
PulseCalculationEngine.calculate()
  ├── _resolve_allocation()           # без изменений
  ├── _build_plan_products()          # без изменений
  ├── _generate_entries()             # без изменений (schedule events)
  │
  ├── EsterPKSimulator.simulate()     # NEW: per-ester curve на основе entries
  ├── EsterPKSimulator.flatness()     # NEW: честный flatness
  │
  ├── _optimize_phase_offsets()       # MODIFIED: использует simulator.flatness()
  │     └── EsterPKSimulator.simulate() + flatness() на каждом кандидате
  │
  ├── _generate_entries() (final)     # повторная генерация после оптимизации
  └── build PulseCalculationResult    # summary_metrics расширяется
```

### 5.3. Fallback

Если продукт содержит только один ингредиент без `ester_name` — simulator degraded к текущей модели. Backward compatible.

---

## 6. Модель фасовки — полная спецификация

### 6.1. Текущее состояние

`CompoundProduct` имеет:
```
package_kind:         "vial" | "ampoule" | "tablet" | "capsule"
units_per_package:    Decimal (e.g. 10 — ампул в коробке или таблеток в блистере)
volume_per_package_ml: Decimal (e.g. 10.0 — мл во флаконе, или 1.0 — мл в ампуле)
unit_strength_mg:     Decimal (e.g. 25 — мг в таблетке)
```

### 6.2. Проблема

Real-world фасовка — **двухуровневая**:

| Тип | Уровень 1 (unit) | Уровень 2 (package) |
|---|---|---|
| Флакон | 1 vial × 10ml | 1 vial в коробке |
| Ампула | 1 ampoule × 1ml | 10 ampoules в коробке |
| Таблетки (блистер) | 1 blister × 10 tablets | 3 blisters в коробке |
| Таблетки (банка) | 1 jar × 100 tablets | 1 jar в коробке |

### 6.3. Расширение модели

Добавить поля в `CompoundProduct`:

```python
# Уровень 1 — единица (уже есть partial)
package_kind: str               # "vial" | "ampoule" | "tablet" | "capsule"
volume_per_unit_ml: Decimal     # для injectables: ml в 1 ампуле/флаконе
unit_strength_mg: Decimal       # для oral: mg в 1 таблетке

# Уровень 2 — упаковка (NEW)
container_kind: str             # "box" | "jar" | "blister_box" | "single"
units_per_container: int        # ампул в коробке, таблеток в банке, блистеров × таблеток
sub_units_per_container: int | None  # если container = blister_box:
                                     #   units_per_container = кол-во блистеров
                                     #   sub_units_per_container = таблеток в блистере
                                     #   total = units_per_container × sub_units_per_container
```

### 6.4. Примеры фасовки

**Флакон 10ml × 250mg/ml (1 шт в коробке):**
```
package_kind = "vial"
volume_per_unit_ml = 10
concentration_value = 250
container_kind = "single"
units_per_container = 1
```

**Ампулы 1ml × 250mg/ml (10 шт в коробке):**
```
package_kind = "ampoule"
volume_per_unit_ml = 1
concentration_value = 250
container_kind = "box"
units_per_container = 10
```

**Таблетки 25mg (блистер 10 шт, 3 блистера в коробке):**
```
package_kind = "tablet"
unit_strength_mg = 25
container_kind = "blister_box"
units_per_container = 3
sub_units_per_container = 10
# total tablets = 30
```

**Таблетки 10mg (банка 100 шт):**
```
package_kind = "tablet"
unit_strength_mg = 10
container_kind = "jar"
units_per_container = 100
```

### 6.5. Конвертация: active mg → human-readable purchase unit

```python
@dataclass(slots=True)
class PurchaseRequirement:
    product_name: str
    required_active_mg_total: Decimal

    # для injectables
    required_ml_total: Decimal | None
    required_units: int | None         # кол-во ампул (целое, ceiling)
    required_containers: int           # кол-во коробок (целое, ceiling)

    # для oral
    required_tablets_total: int | None # кол-во таблеток (целое, ceiling)
    required_containers: int           # кол-во упаковок

    # human-readable
    display_text: str                  # "3 коробки (30 ампул × 1ml)"
    leftover_text: str | None          # "остаток: ~6 ампул"
```

---

## 7. Human-readable вывод — правила округления

### 7.1. Фундаментальное правило

> **Никогда не выводить дробные единицы фасовки.**  
> `0.4 флакона` — абсурд. Пользователь покупает **1 флакон**.

### 7.2. Правила округления

| Единица | Правило | Пример |
|---|---|---|
| Ампула | `ceil()` — всегда вверх | 7.2 → 8 ампул |
| Флакон | `ceil()` — всегда вверх | 1.3 → 2 флакона |
| Коробка | `ceil()` — всегда вверх | 2.1 → 3 коробки |
| Таблетка | `ceil()` — всегда вверх | 43.7 → 44 таблетки |
| Упаковка (блистеры) | `ceil()` — всегда вверх | 1.5 → 2 упаковки |

### 7.3. Human-readable формат

**Injectables:**
```
Testosterone Enanthate 250mg/ml (флаконы 10ml):
  Потребуется: 2 флакона
  Использовано: ~18.4ml из 20ml
  Остаток: ~1.6ml (≈ 1 инъекция)
```

**Injectables (ампулы в коробке):**
```
Testosterone Propionate 100mg/ml (ампулы 1ml, 10 шт/коробка):
  Потребуется: 3 коробки (30 ампул)
  Использовано: 28 ампул
  Остаток: 2 ампулы
```

**Oral (блистеры в коробке):**
```
Anastrozole 1mg (блистер 10 шт, 3 блистера/коробка):
  Потребуется: 1 коробка (30 таблеток)
  Использовано: 24 таблетки
  Остаток: 6 таблеток
```

**Oral (банка):**
```
Oxandrolone 10mg (банка 100 шт):
  Потребуется: 2 банки (200 таблеток)
  Использовано: 168 таблеток
  Остаток: 32 таблетки
```

### 7.4. Правило остатка

Если остаток > 50% упаковки — добавить warning:
```
⚠ Остаток 7 ампул из 10 — возможно стоит пересмотреть длительность курса
```

---

## 8. Расчёт для oral-препаратов

### 8.1. Принципиальное отличие

Oral compounds имеют:
- Короткий half-life (часы, не дни)
- Низкую bioavailability (5–15% для некоторых)
- Несколько приёмов в день (2–4 раза)

### 8.2. Schedule для oral

Текущий engine генерирует `PulsePlanEntry` с `day_offset`. Для oral нужен **intra-day split**:

```python
@dataclass(slots=True)
class PulsePlanEntry:
    day_offset: int
    scheduled_day: date | None
    product_id: UUID
    ingredient_context: str | None
    volume_ml: Decimal              # 0 для oral
    computed_mg: Decimal
    injection_event_key: str
    sequence_no: int
    # --- NEW ---
    administration_route: str       # "im" | "subq" | "oral" | "sublingual"
    time_of_day_slot: str | None    # "morning" | "afternoon" | "evening" | None
    units_count: int | None         # кол-во таблеток (целое)
    units_label: str | None         # "таблетка" / "капсула"
```

### 8.3. Oral schedule generation

Для oral compound с half-life = 8 часов:
- Рекомендуемая частота: каждые 6–8 часов
- 3 приёма/день: утро, обед, вечер

```
Oxandrolone 10mg (50mg/day target):
  День 1: 20mg утро (2 табл), 10mg обед (1 табл), 20mg вечер (2 табл)
  День 2: повторить
```

### 8.4. Округление дозы к целым таблеткам

> **Никто не ломает таблетку на 0.7.**

Правило: dose_per_event округляется до ближайшего целого числа таблеток.

```python
def round_to_tablets(dose_mg: Decimal, tablet_strength_mg: Decimal) -> int:
    raw = dose_mg / tablet_strength_mg
    return max(1, int(raw.to_integral_value(rounding=ROUND_HALF_UP)))
```

Если rounded dose отклоняется от target > 15% — warning + suggestion:
```
⚠ Целевая доза 35mg/день, ближайшая к таблеткам: 40mg (4 × 10mg) или 30mg (3 × 10mg).
  Рекомендуем: 40mg — ближе к целевому.
```

---

## 9. Concentration-aware allocation

### 9.1. Текущая проблема

Engine аллоцирует `weekly_mg` на продукт. Но `weekly_mg` — это mg **эфира**, а не mg **чистого вещества**.

Пример: Target 500mg testosterone/week
- Product A: Test Enanthate (active_fraction = 0.72) → нужно 500/0.72 ≈ 694mg эфира
- Product B: Test Propionate (active_fraction = 0.83) → нужно 500/0.83 ≈ 602mg эфира

Если engine раздаёт поровну 250mg/product — это **250mg эфира каждому**, что даёт:
- A: 250 × 0.72 = 180mg чистого testosterone
- B: 250 × 0.83 = 207.5mg чистого testosterone
- Итого: 387.5mg — **не** 500mg.

### 9.2. Решение: target в active mg

Allocation pipeline должен:
1. Получить `weekly_target_active_mg` (сколько чистого вещества нужно)
2. Для каждого продукта рассчитать `effective_active_fraction` (средневзвешенная по ингредиентам)
3. Рассчитать `weekly_ester_mg = weekly_target_active_mg / effective_active_fraction`
4. Из `weekly_ester_mg` рассчитать volume: `ml = mg / concentration_mg_ml`

### 9.3. Обратная совместимость

Если `active_fraction` не заполнен в catalog — fallback к текущей модели (assume fraction = 1.0). Warning flag: `active_fraction_missing`.

---

## 10. Модель профилей расчёта

### 10.1. Зачем профили

Разные цели протокола → разные приоритеты:

| Профиль | Цель | Приоритет flatness | Частота |
|---|---|---|---|
| TRT (replacement) | Стабильный физиологический фон | Максимальный | Умеренная |
| Cycle (performance) | Эффективная загрузка | Высокий | Гибкая |
| Bridge (between cycles) | Поддержание минимального фона | Средний | Минимальная |
| PCT (post-cycle) | Восстановление | Низкий | По протоколу |

### 10.2. Mapping к presets

```
TRT profile:
  - preferred preset: golden_pulse
  - max_injections_per_week: 2–3
  - flatness target: CV < 0.15
  - peak_trough_ratio target: < 1.5

Cycle profile:
  - preferred preset: layered_pulse или golden_pulse
  - max_injections_per_week: 3–7
  - flatness target: CV < 0.25
  - допускаются компромиссы ради удобства

Bridge profile:
  - preferred preset: unified_rhythm
  - max_injections_per_week: 1–2
  - minimal dose, minimal frequency
```

### 10.3. Как это влияет на engine

Профиль добавляется в `DraftSettingsInput`:

```python
@dataclass(slots=True)
class DraftSettingsInput:
    protocol_input_mode: str | None
    protocol_profile: str | None  # "trt" | "cycle" | "bridge" | "pct" | None
    weekly_target_total_mg: Decimal | None
    ...
```

Engine использует профиль для:
- Выбора flatness target при optimization
- Подсказки preset если не выбран
- Определения допустимого peak_trough_ratio
- Генерации warnings (e.g. «для TRT flatness ниже рекомендуемой»)

---

## 11. Миграция данных

### 11.1. Каталог — новые поля

Alembic migration для `CompoundIngredient`:
```sql
ALTER TABLE compound_catalog.compound_ingredients
  ADD COLUMN ester_name VARCHAR(128),
  ADD COLUMN parent_substance VARCHAR(128),
  ADD COLUMN active_fraction NUMERIC(6,4),
  ADD COLUMN release_model VARCHAR(32) DEFAULT 'first_order',
  ADD COLUMN tmax_hours NUMERIC(8,3),
  ADD COLUMN bioavailability NUMERIC(6,4);
```

Alembic migration для `CompoundProduct`:
```sql
ALTER TABLE compound_catalog.compound_products
  ADD COLUMN container_kind VARCHAR(32),
  ADD COLUMN units_per_container INTEGER,
  ADD COLUMN sub_units_per_container INTEGER;
```

### 11.2. Обратная совместимость

Все новые поля `NULLABLE`. Engine работает без них (fallback to current model).

### 11.3. Google Sheets mapping

Колонки в Google Sheets для ингредиентов:
```
ester_name | parent_substance | active_fraction | tmax_hours
```

Колонки для фасовки:
```
container_kind | units_per_container | sub_units_per_container
```

Mapping в `CatalogProductInput` → ingest pipeline без изменения архитектуры.

---

## 12. Изменения в PulsePlanEntry

### 12.1. Расширенный entry

```python
@dataclass(slots=True)
class PulsePlanEntry:
    day_offset: int
    scheduled_day: date | None
    product_id: UUID
    ingredient_context: str | None
    volume_ml: Decimal
    computed_mg: Decimal
    injection_event_key: str
    sequence_no: int

    # --- NEW ---
    administration_route: str           # "im" | "subq" | "oral"
    time_of_day_slot: str | None        # "morning" | "afternoon" | "evening"
    units_count: int | None             # целое кол-во единиц (ампул, таблеток)
    units_label: str | None             # "амп." | "табл." | "капс."
    computed_active_mg: Decimal | None  # mg чистого вещества (после active_fraction)

    # per-ester breakdown (for PK display)
    ester_breakdown: list[EsterDoseBreakdown] | None


@dataclass(slots=True)
class EsterDoseBreakdown:
    ester_name: str
    parent_substance: str
    ester_mg: Decimal
    active_mg: Decimal
```

### 12.2. DB migration для entries

Минимальное: `administration_route`, `units_count` как новые nullable columns.
`ester_breakdown` — хранить в `JSONB` внутри entry или как отдельную summary в `summary_metrics_json`.

---

## 13. Выходные артефакты для пользователя

### 13.1. Protocol Summary (human-readable)

```
📋 Протокол: TRT (8 недель)
Preset: Golden Pulse
Flatness: 91% (отлично)

💉 Schedule (один цикл):
  Пн — Testosterone Enanthate 250mg/ml: 0.4ml (100mg)
  Чт — Testosterone Enanthate 250mg/ml: 0.4ml (100mg)

💊 Anastrozole 1mg: 1 табл. через день (утро)

📦 Что купить:
  • Test Enanthate 250mg/ml (флакон 10ml): 1 флакон
    использовано ~6.4ml, остаток ~3.6ml
  • Anastrozole 1mg (30 табл/коробка): 1 коробка
    использовано 28 табл, остаток 2 табл
```

### 13.2. PK Curve Data (для визуализации позже)

```json
{
  "resolution_hours": 6,
  "duration_days": 56,
  "substances": ["Testosterone"],
  "curve_points": [
    {"hour": 0, "Testosterone": 0},
    {"hour": 6, "Testosterone": 45.2},
    {"hour": 12, "Testosterone": 78.1},
    ...
  ],
  "flatness": {
    "overall_cv": 0.09,
    "overall_score": 91,
    "peak_trough_ratio": 1.38,
    "steady_state_day": 12
  }
}
```

---

## 14. План реализации

### Phase 1 — Catalog extension + packaging (2–3 дня)

1. Alembic migrations: новые поля `CompoundIngredient` + `CompoundProduct`
2. Google Sheets mapping: новые колонки
3. `CatalogProductInput` schema update
4. `SqlAlchemyCatalogRepository.upsert_product()` update

### Phase 2 — Packaging engine upgrade (2–3 дня)

1. Новый `PackagingCalculator` service
2. Двухуровневая логика: unit → container → purchase requirement
3. Human-readable formatter
4. Обновление `CourseEstimatorService._build_line()`
5. Тесты: все варианты фасовки

### Phase 3 — EsterPKSimulator core (3–5 дней)

1. `EsterPKSimulator` class с `simulate()` и `calculate_flatness()`
2. `EsterPKProfile` extraction из `PulseProductProfile`
3. `FlatnessMetrics` expanded dataclass
4. Unit tests: single ester, mix ester, Sustanon blend
5. Comparison tests: old flatness vs new flatness

### Phase 4 — Engine integration (2–3 дня)

1. Wire `EsterPKSimulator` into `_calculate_flatness()`
2. Wire into `_optimize_phase_offsets()`
3. Fallback logic для products без ester data
4. Extended `summary_metrics` output
5. Regression tests: existing tests still pass

### Phase 5 — Oral support (2–3 дня)

1. `administration_route` + `time_of_day_slot` в `PulsePlanEntry`
2. Oral schedule generator: intra-day split
3. Tablet rounding logic
4. DB migration для entry extension
5. Tests: oral scenarios

### Phase 6 — Protocol profiles (1–2 дня)

1. `protocol_profile` field in settings
2. Profile-aware flatness targets
3. Profile-aware warnings
4. Tests: TRT vs cycle vs bridge behaviour differences

---

## 15. Файловая карта изменений

| Файл | Действие | Phase |
|---|---|---|
| `app/domain/models/compound_catalog.py` | +поля ester/packaging | 1 |
| `app/application/catalog/schemas.py` | +поля CatalogProductInput | 1 |
| `app/infrastructure/catalog/repository.py` | update upsert | 1 |
| `app/infrastructure/catalog/google_sheets.py` | mapping update | 1 |
| `app/application/protocols/schemas.py` | +PulseIngredientProfile поля, +PulsePlanEntry поля | 2,3 |
| `app/application/protocols/pulse_engine.py` | integrate EsterPKSimulator | 3,4 |
| `app/application/protocols/pk_simulator.py` | **NEW** — EsterPKSimulator | 3 |
| `app/application/protocols/packaging.py` | **NEW** — PackagingCalculator | 2 |
| `app/application/protocols/course_estimator.py` | use PackagingCalculator | 2 |
| `app/infrastructure/protocols/repository.py` | query new fields | 1,5 |
| `app/domain/models/pulse_engine.py` | +entry columns | 5 |
| `app/domain/models/protocols.py` | +protocol_profile | 6 |
| `tests/test_pulse_engine.py` | extend for per-ester | 3,4 |
| `tests/test_pk_simulator.py` | **NEW** | 3 |
| `tests/test_packaging.py` | **NEW** | 2 |
| `tests/test_course_estimator.py` | extend for packaging | 2 |

---

## 16. Критические принципы

1. **Backward compatible** — если ester data нет, engine работает как сейчас
2. **Целые единицы** — никаких 0.4 флакона, 0.7 таблетки
3. **Per-ester PK** — каждый эфир — отдельная кривая decay
4. **Active fraction aware** — аллокация в mg чистого вещества
5. **Human-first output** — результат должен быть понятен человеку без калькулятора
6. **Ровный фон** — optimize для минимального CV, не для пиковых значений
7. **Честный flatness** — если ровный фон невозможен, сказать прямо, а не врать score'ом
