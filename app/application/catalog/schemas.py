from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class IngredientInput:
    ingredient_name: str
    qualifier: str | None
    amount: Decimal | None
    unit: str | None
    basis: str | None
    half_life_days: Decimal | None
    dose_guidance_min_mg_week: Decimal | None
    dose_guidance_max_mg_week: Decimal | None
    dose_guidance_typical_mg_week: Decimal | None
    is_pulse_driver: bool | None


@dataclass(slots=True)
class CatalogProductInput:
    source_row_key: str
    brand_name: str
    display_name: str
    trade_name: str
    release_form: str | None
    concentration_raw: str | None
    concentration_value: Decimal | None
    concentration_unit: str | None
    concentration_basis: str | None
    official_url: str | None
    authenticity_notes: str | None
    max_injection_volume_ml: Decimal | None
    is_automatable: bool
    pharmacology_notes: str | None
    composition_basis_notes: str | None
    # Packaging / estimator fields (optional — only present when columns exist in source)
    package_kind: str | None
    volume_per_package_ml: Decimal | None
    unit_strength_mg: Decimal | None
    units_per_package: Decimal | None
    aliases: list[str]
    ingredients: list[IngredientInput]
    image_refs: list[str]
    video_refs: list[str]
    source_payload: dict[str, str]


@dataclass(slots=True)
class IngestIssue:
    row_key: str
    message: str


@dataclass(slots=True)
class IngestResult:
    status: str
    total_rows: int
    processed_rows: int
    created_count: int
    updated_count: int
    issue_count: int
