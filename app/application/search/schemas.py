from dataclasses import dataclass, field
from uuid import UUID


@dataclass(slots=True)
class SearchDocument:
    id: str
    product_id: str
    trade_name: str
    product_name: str
    brand: str
    aliases: list[str]
    ingredient_names: list[str]
    ester_component_tokens: list[str]
    concentration_tokens: list[str]
    dosage_unit_tokens: list[str]
    form_factor: str | None
    normalized_tokens: list[str]
    composition_summary: str | None
    official_url: str | None
    authenticity_notes: str | None
    media_refs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SearchResultItem:
    document_id: str
    product_id: UUID
    product_name: str
    brand: str
    composition_summary: str | None
    form_factor: str | None


@dataclass(slots=True)
class SearchResponse:
    query: str
    normalized_query: str
    results: list[SearchResultItem]
    total: int
    degraded: bool = False
    degradation_reason: str | None = None


@dataclass(slots=True)
class OpenCard:
    product_id: UUID
    product_name: str
    brand: str
    composition_summary: str | None
    form_factor: str | None
    official_url: str | None
    authenticity_notes: str | None
    source_links: list["CardSourceLink"] = field(default_factory=list)
    media_items: list["CardMediaItem"] = field(default_factory=list)


@dataclass(slots=True)
class CardSourceLink:
    kind: str
    label: str
    url: str
    priority: int
    is_active: bool


@dataclass(slots=True)
class CardMediaItem:
    media_kind: str
    ref: str
    priority: int
    is_cover: bool
    source_layer: str | None
    is_active: bool


@dataclass(slots=True)
class CatalogIngredientRow:
    ingredient_name: str
    amount: str | None
    unit: str | None
    qualifier: str | None


@dataclass(slots=True)
class CatalogProjectionRow:
    product_id: UUID
    product_name: str
    trade_name: str
    brand_name: str
    release_form: str | None
    concentration_raw: str | None
    aliases: list[str]
    ingredients: list[CatalogIngredientRow]
    official_url: str | None
    authenticity_notes: str | None
    media_refs: list[str]
