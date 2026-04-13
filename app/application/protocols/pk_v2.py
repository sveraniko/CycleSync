from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import exp, log
from statistics import pstdev
from typing import Protocol
from uuid import UUID


@dataclass(slots=True)
class IngredientPKProfile:
    ingredient_name: str
    parent_substance: str
    basis: str
    amount_per_ml_mg: Decimal | None
    amount_per_unit_mg: Decimal | None
    half_life_days: Decimal
    active_fraction: Decimal
    ester_name: str | None = None
    tmax_hours: Decimal | None = None
    release_model: str | None = None
    is_pulse_driver: bool = True


@dataclass(slots=True)
class ProductPKProfile:
    product_id: UUID
    product_key: str
    release_form: str
    ingredients: list[IngredientPKProfile]


@dataclass(slots=True)
class PKDoseEvent:
    day_offset: int
    product_id: UUID
    product_key: str
    event_volume_ml: Decimal | None = None
    event_unit_count: Decimal | None = None
    event_time_hour: int = 0


@dataclass(slots=True)
class PKSimulationInput:
    draft_id: UUID
    planned_start_date: date | None
    product_profiles: list[ProductPKProfile]
    dose_events: list[PKDoseEvent]
    horizon_days: int | None = None
    resolution_hours: int = 1
    constraint_forced_longer_interval: bool = False
    inventory_forced_degradation: bool = False


ProtocolPKInput = PKSimulationInput


@dataclass(slots=True)
class IngredientDose:
    product_id: UUID
    product_key: str
    ingredient_name: str
    parent_substance: str
    half_life_days: Decimal
    tmax_hours: Decimal | None
    active_fraction: Decimal
    dose_mg: Decimal
    event_hour: int


@dataclass(slots=True)
class IngredientCurvePoint:
    hour_offset: int
    concentration: Decimal


@dataclass(slots=True)
class SubstanceCurvePoint:
    hour_offset: int
    concentration: Decimal


@dataclass(slots=True)
class PKEvaluationMetrics:
    peak_concentration: Decimal
    trough_concentration: Decimal
    peak_trough_spread_pct: Decimal
    variability_cv_pct: Decimal
    flatness_stability_score: Decimal


@dataclass(slots=True)
class PKCurveResult:
    ingredient_curves: dict[str, list[IngredientCurvePoint]]
    substance_curves: dict[str, list[SubstanceCurvePoint]]
    overall_curve: list[SubstanceCurvePoint]
    metrics: PKEvaluationMetrics
    warning_flags: list[str]


class PKEngineV2(Protocol):
    def calculate(self, data: PKSimulationInput) -> PKCurveResult: ...


def decompose_product_dose(*, profile: ProductPKProfile, event: PKDoseEvent) -> list[IngredientDose]:
    doses: list[IngredientDose] = []
    event_hour = event.day_offset * 24 + event.event_time_hour
    for ingredient in profile.ingredients:
        if ingredient.basis == "per_ml":
            if event.event_volume_ml is None or ingredient.amount_per_ml_mg is None:
                continue
            dose = event.event_volume_ml * ingredient.amount_per_ml_mg
        elif ingredient.basis == "per_unit":
            if event.event_unit_count is None or ingredient.amount_per_unit_mg is None:
                continue
            dose = event.event_unit_count * ingredient.amount_per_unit_mg
        else:
            continue
        doses.append(
            IngredientDose(
                product_id=profile.product_id,
                product_key=profile.product_key,
                ingredient_name=ingredient.ingredient_name,
                parent_substance=ingredient.parent_substance,
                half_life_days=ingredient.half_life_days,
                tmax_hours=ingredient.tmax_hours,
                active_fraction=ingredient.active_fraction,
                dose_mg=dose,
                event_hour=event_hour,
            )
        )
    return doses


def group_doses_by_parent_substance(doses: list[IngredientDose]) -> dict[str, Decimal]:
    grouped: dict[str, Decimal] = {}
    for dose in doses:
        grouped[dose.parent_substance] = grouped.get(dose.parent_substance, Decimal("0")) + dose.dose_mg
    return grouped


class FirstOrderPKEngineV2:
    def calculate(self, data: PKSimulationInput) -> PKCurveResult:
        resolution = max(data.resolution_hours, 1)
        fallback_resolution_used = resolution > 3
        product_by_id = {profile.product_id: profile for profile in data.product_profiles}
        product_by_key = {profile.product_key: profile for profile in data.product_profiles}

        all_doses: list[IngredientDose] = []
        for event in data.dose_events:
            profile = product_by_id.get(event.product_id) or product_by_key.get(event.product_key)
            if profile is None:
                continue
            all_doses.extend(decompose_product_dose(profile=profile, event=event))

        last_event_hour = max((dose.event_hour for dose in all_doses), default=0)
        horizon_days = data.horizon_days if data.horizon_days is not None else max((last_event_hour // 24) + 14, 14)
        horizon_hours = max(horizon_days * 24, 24)

        ingredient_series: dict[str, list[float]] = {}
        ingredient_to_parent: dict[str, str] = {}

        for dose in all_doses:
            ingredient_key = dose.ingredient_name
            ingredient_to_parent[ingredient_key] = dose.parent_substance
            series = ingredient_series.setdefault(ingredient_key, [0.0 for _ in range(horizon_hours + 1)])
            self._accumulate_dose(series=series, dose=dose, horizon_hours=horizon_hours, resolution=resolution)

        substance_series: dict[str, list[float]] = {}
        for ingredient_key, points in ingredient_series.items():
            parent = ingredient_to_parent[ingredient_key]
            merged = substance_series.setdefault(parent, [0.0 for _ in range(horizon_hours + 1)])
            for idx in range(0, horizon_hours + 1, resolution):
                merged[idx] += points[idx]

        overall = [0.0 for _ in range(horizon_hours + 1)]
        for series in substance_series.values():
            for idx in range(0, horizon_hours + 1, resolution):
                overall[idx] += series[idx]

        metrics = self._evaluate_metrics(overall, resolution)
        warning_flags = self._build_warnings(
            ingredient_series=ingredient_series,
            ingredient_to_parent=ingredient_to_parent,
            all_doses=all_doses,
            peak_trough_spread_pct=metrics.peak_trough_spread_pct,
            fallback_resolution_used=fallback_resolution_used,
            constraint_forced_longer_interval=data.constraint_forced_longer_interval,
            inventory_forced_degradation=data.inventory_forced_degradation,
        )

        return PKCurveResult(
            ingredient_curves={
                name: [
                    IngredientCurvePoint(hour_offset=hour, concentration=_q(points[hour]))
                    for hour in range(0, horizon_hours + 1, resolution)
                ]
                for name, points in ingredient_series.items()
            },
            substance_curves={
                name: [
                    SubstanceCurvePoint(hour_offset=hour, concentration=_q(points[hour]))
                    for hour in range(0, horizon_hours + 1, resolution)
                ]
                for name, points in substance_series.items()
            },
            overall_curve=[SubstanceCurvePoint(hour_offset=hour, concentration=_q(overall[hour])) for hour in range(0, horizon_hours + 1, resolution)],
            metrics=metrics,
            warning_flags=warning_flags,
        )

    @staticmethod
    def _accumulate_dose(*, series: list[float], dose: IngredientDose, horizon_hours: int, resolution: int) -> None:
        half_life_days = max(float(dose.half_life_days), 0.1)
        decay_constant = log(2.0) / half_life_days
        base_amount = float(dose.dose_mg * dose.active_fraction)

        for hour in range(max(dose.event_hour, 0), horizon_hours + 1, resolution):
            dt_hours = hour - dose.event_hour
            if dt_hours < 0:
                continue
            elapsed_days = dt_hours / 24.0
            rise = 1.0
            if dose.tmax_hours and dose.tmax_hours > 0:
                rise = min(dt_hours / float(dose.tmax_hours), 1.0)
            series[hour] += base_amount * rise * exp(-decay_constant * elapsed_days)

    @staticmethod
    def _evaluate_metrics(overall: list[float], resolution: int) -> PKEvaluationMetrics:
        sampled = [overall[hour] for hour in range(0, len(overall), resolution)]
        if not sampled:
            zero = Decimal("0.00")
            return PKEvaluationMetrics(zero, zero, zero, zero, zero)

        peak = max(sampled)
        trough = min(sampled)
        mean = sum(sampled) / len(sampled)
        spread_pct = 0.0 if peak <= 0 else ((peak - trough) / peak) * 100.0
        variability = 0.0 if mean <= 0 else (pstdev(sampled) / mean) * 100.0
        flatness = max(0.0, 100.0 - variability - spread_pct * 0.35)

        return PKEvaluationMetrics(
            peak_concentration=_q(peak),
            trough_concentration=_q(trough),
            peak_trough_spread_pct=_q(spread_pct),
            variability_cv_pct=_q(variability),
            flatness_stability_score=_q(flatness),
        )

    @staticmethod
    def _build_warnings(
        *,
        ingredient_series: dict[str, list[float]],
        ingredient_to_parent: dict[str, str],
        all_doses: list[IngredientDose],
        peak_trough_spread_pct: Decimal,
        fallback_resolution_used: bool,
        constraint_forced_longer_interval: bool,
        inventory_forced_degradation: bool,
    ) -> list[str]:
        flags: list[str] = []
        if peak_trough_spread_pct >= Decimal("55"):
            flags.append("peak_trough_spread_high")
        if fallback_resolution_used:
            flags.append("insufficient_resolution_fallback")
        if constraint_forced_longer_interval:
            flags.append("constraint_forced_longer_interval")
        if inventory_forced_degradation:
            flags.append("inventory_forced_degradation")

        parent_half_lives: dict[str, set[Decimal]] = {}
        for dose in all_doses:
            parent_half_lives.setdefault(dose.parent_substance, set()).add(dose.half_life_days)

        for parent, half_lives in parent_half_lives.items():
            if len(half_lives) < 2:
                continue
            shortest = min(half_lives)
            longest = max(half_lives)
            if shortest <= Decimal("3") and longest / max(shortest, Decimal("0.1")) >= Decimal("2"):
                if any(ingredient_to_parent.get(name) == parent for name in ingredient_series):
                    flags.append("mixed_ester_short_component_spikes")
                    break

        return sorted(set(flags))


def build_simulation_input_from_pulse_plan(
    *,
    draft_id: UUID,
    planned_start_date: date | None,
    product_profiles: list[ProductPKProfile],
    plan_entries: list,
    horizon_days: int | None = None,
    resolution_hours: int = 1,
    constraint_forced_longer_interval: bool = False,
    inventory_forced_degradation: bool = False,
) -> PKSimulationInput:
    profile_by_id = {profile.product_id: profile for profile in product_profiles}
    events: list[PKDoseEvent] = []
    for entry in plan_entries:
        profile = profile_by_id.get(entry.product_id)
        product_key = profile.product_key if profile else str(entry.product_id)
        events.append(
            PKDoseEvent(
                day_offset=entry.day_offset,
                product_id=entry.product_id,
                product_key=product_key,
                event_volume_ml=entry.volume_ml,
                event_unit_count=None,
                event_time_hour=0,
            )
        )

    return PKSimulationInput(
        draft_id=draft_id,
        planned_start_date=planned_start_date,
        product_profiles=product_profiles,
        dose_events=events,
        horizon_days=horizon_days,
        resolution_hours=resolution_hours,
        constraint_forced_longer_interval=constraint_forced_longer_interval,
        inventory_forced_degradation=inventory_forced_degradation,
    )


def _q(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))
