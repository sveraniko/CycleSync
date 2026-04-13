from app.application.catalog.normalization import (
    normalize_concentration,
    parse_bool,
    normalize_text,
    parse_decimal,
    split_list_field,
)
from app.application.catalog.schemas import CatalogProductInput, IngredientInput, IngestIssue


def _derive_package_kind(packaging_raw: str | None) -> str | None:
    """Parse the 'packaging' column (e.g. '10 ml vial') into a package_kind."""
    if not packaging_raw:
        return None
    text = packaging_raw.strip().lower()
    if "vial" in text:
        return "vial"
    if "ampoule" in text or "ampule" in text or "amp" in text:
        return "ampoule"
    if "tablet" in text or "tab" in text:
        return "tablet"
    if "capsule" in text or "caps" in text:
        return "capsule"
    return None


def parse_ingredient_token(token: str) -> IngredientInput:
    # name|qualifier|amount|unit|basis|half_life_days|dose_min|dose_max|dose_typical|is_pulse_driver
    parts = [part.strip() for part in token.split("|")]
    padded = parts + [""] * (10 - len(parts))
    name, qualifier, amount_raw, unit, basis, half_life_raw, dose_min_raw, dose_max_raw, dose_typical_raw, pulse_raw = (
        padded[:10]
    )
    return IngredientInput(
        ingredient_name=normalize_text(name),
        qualifier=normalize_text(qualifier) if qualifier else None,
        amount=parse_decimal(amount_raw),
        unit=normalize_text(unit) if unit else None,
        basis=normalize_text(basis) if basis else None,
        half_life_days=parse_decimal(half_life_raw),
        dose_guidance_min_mg_week=parse_decimal(dose_min_raw),
        dose_guidance_max_mg_week=parse_decimal(dose_max_raw),
        dose_guidance_typical_mg_week=parse_decimal(dose_typical_raw),
        is_pulse_driver=parse_bool(pulse_raw),
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
        max_injection_volume_ml=parse_decimal(row.get("max_injection_volume_ml")),
        is_automatable=parse_bool(row.get("is_automatable")) is not False,
        pharmacology_notes=normalize_text(row.get("pharmacology_notes", "")) or None,
        composition_basis_notes=normalize_text(row.get("composition_basis_notes", "")) or None,
        package_kind=normalize_text(row.get("package_kind", "")) or _derive_package_kind(row.get("packaging")),
        volume_per_package_ml=parse_decimal(row.get("volume_per_package_ml")) or parse_decimal(row.get("vial_volume_ml")),
        unit_strength_mg=parse_decimal(row.get("unit_strength_mg")) or concentration_value,
        units_per_package=parse_decimal(row.get("units_per_package")),
        aliases=split_list_field(row.get("aliases", "")),
        ingredients=ingredients,
        image_refs=split_list_field(row.get("image_refs", "")),
        video_refs=split_list_field(row.get("video_refs", "")),
        source_payload=row,
    )
    return product, None
