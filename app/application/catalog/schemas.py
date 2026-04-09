from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class IngredientInput:
    ingredient_name: str
    qualifier: str | None
    amount: Decimal | None
    unit: str | None
    basis: str | None


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
