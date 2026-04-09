from app.application.catalog.normalization import (
    normalize_concentration,
    normalize_text,
    parse_decimal,
    split_list_field,
)
from app.application.catalog.schemas import CatalogProductInput, IngredientInput, IngestIssue


def parse_ingredient_token(token: str) -> IngredientInput:
    # name|qualifier|amount|unit|basis
    parts = [part.strip() for part in token.split("|")]
    padded = parts + [""] * (5 - len(parts))
    name, qualifier, amount_raw, unit, basis = padded[:5]
    return IngredientInput(
        ingredient_name=normalize_text(name),
        qualifier=normalize_text(qualifier) if qualifier else None,
        amount=parse_decimal(amount_raw),
        unit=normalize_text(unit) if unit else None,
        basis=normalize_text(basis) if basis else None,
    )


def map_sheet_row(row: dict[str, str], row_number: int) -> tuple[CatalogProductInput | None, IngestIssue | None]:
    row_key = row.get("row_key") or str(row_number)
    brand = normalize_text(row.get("brand", ""))
    display_name = normalize_text(row.get("display_name", ""))
    trade_name = normalize_text(row.get("trade_name", display_name))

    if not brand:
        return None, IngestIssue(row_key=row_key, message="Missing brand")
    if not display_name:
        return None, IngestIssue(row_key=row_key, message="Missing display_name")

    concentration_raw = normalize_text(row.get("concentration", "")) or None
    concentration_value, concentration_unit, concentration_basis = normalize_concentration(concentration_raw)

    ingredient_tokens = split_list_field(row.get("ingredients", ""))
    ingredients = [parse_ingredient_token(token) for token in ingredient_tokens if token]

    product = CatalogProductInput(
        source_row_key=row_key,
        brand_name=brand,
        display_name=display_name,
        trade_name=trade_name,
        release_form=normalize_text(row.get("release_form", "")) or None,
        concentration_raw=concentration_raw,
        concentration_value=concentration_value,
        concentration_unit=concentration_unit,
        concentration_basis=concentration_basis,
        official_url=normalize_text(row.get("official_url", "")) or None,
        authenticity_notes=normalize_text(row.get("authenticity_notes", "")) or None,
        aliases=split_list_field(row.get("aliases", "")),
        ingredients=ingredients,
        image_refs=split_list_field(row.get("image_refs", "")),
        video_refs=split_list_field(row.get("video_refs", "")),
        source_payload=row,
    )
    return product, None
