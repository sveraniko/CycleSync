from dataclasses import dataclass
from datetime import date
from decimal import Decimal
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
class ProtocolPKInput:
    draft_id: UUID
    planned_start_date: date | None
    product_profiles: list[ProductPKProfile]


@dataclass(slots=True)
class IngredientDose:
    product_id: UUID
    product_key: str
    ingredient_name: str
    parent_substance: str
    dose_mg: Decimal


@dataclass(slots=True)
class SubstanceCurveResult:
    parent_substance: str
    points: list[tuple[int, Decimal]]


@dataclass(slots=True)
class PKCurveResult:
    ingredient_curves: dict[str, list[tuple[int, Decimal]]]
    substance_curves: list[SubstanceCurveResult]


class PKEngineV2(Protocol):
    def calculate(self, data: ProtocolPKInput) -> PKCurveResult: ...


def decompose_product_dose(*, profile: ProductPKProfile, event_volume_ml: Decimal | None, event_unit_count: Decimal | None) -> list[IngredientDose]:
    doses: list[IngredientDose] = []
    for ingredient in profile.ingredients:
        if ingredient.basis == "per_ml":
            if event_volume_ml is None or ingredient.amount_per_ml_mg is None:
                continue
            dose = event_volume_ml * ingredient.amount_per_ml_mg
        elif ingredient.basis == "per_unit":
            if event_unit_count is None or ingredient.amount_per_unit_mg is None:
                continue
            dose = event_unit_count * ingredient.amount_per_unit_mg
        else:
            continue
        doses.append(
            IngredientDose(
                product_id=profile.product_id,
                product_key=profile.product_key,
                ingredient_name=ingredient.ingredient_name,
                parent_substance=ingredient.parent_substance,
                dose_mg=dose,
            )
        )
    return doses


def group_doses_by_parent_substance(doses: list[IngredientDose]) -> dict[str, Decimal]:
    grouped: dict[str, Decimal] = {}
    for dose in doses:
        grouped[dose.parent_substance] = grouped.get(dose.parent_substance, Decimal("0")) + dose.dose_mg
    return grouped
