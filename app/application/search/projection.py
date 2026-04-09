from app.application.search.normalization import normalize_token_set, tokenize_for_search
from app.application.search.schemas import CatalogProjectionRow, SearchDocument


class CompoundSearchProjectionBuilder:
    def build_document(self, row: CatalogProjectionRow) -> SearchDocument:
        ingredient_tokens: list[str] = []
        concentration_tokens = tokenize_for_search(row.concentration_raw or "")
        dosage_unit_tokens: list[str] = []

        for ingredient in row.ingredients:
            ingredient_tokens.extend(tokenize_for_search(ingredient.ingredient_name))
            if ingredient.amount:
                dosage_unit_tokens.extend(tokenize_for_search(ingredient.amount))
            if ingredient.unit:
                dosage_unit_tokens.extend(tokenize_for_search(ingredient.unit))
            if ingredient.qualifier:
                ingredient_tokens.extend(tokenize_for_search(ingredient.qualifier))

        composition_summary = _build_composition_summary(row)
        normalized_tokens = normalize_token_set(
            row.product_name,
            row.trade_name,
            row.brand_name,
            row.release_form,
            row.concentration_raw,
            " ".join(row.aliases),
            " ".join(i.ingredient_name for i in row.ingredients),
            " ".join(i.qualifier or "" for i in row.ingredients),
        )

        return SearchDocument(
            id=str(row.product_id),
            product_id=str(row.product_id),
            trade_name=row.trade_name,
            product_name=row.product_name,
            brand=row.brand_name,
            aliases=row.aliases,
            ingredient_names=[i.ingredient_name for i in row.ingredients],
            ester_component_tokens=sorted(set(ingredient_tokens)),
            concentration_tokens=sorted(set(concentration_tokens)),
            dosage_unit_tokens=sorted(set(dosage_unit_tokens)),
            form_factor=row.release_form,
            normalized_tokens=normalized_tokens,
            composition_summary=composition_summary,
            official_url=row.official_url,
            authenticity_notes=row.authenticity_notes,
            media_refs=row.media_refs,
        )


def _build_composition_summary(row: CatalogProjectionRow) -> str | None:
    chunks: list[str] = []
    for ingredient in row.ingredients:
        part = ingredient.ingredient_name
        if ingredient.amount and ingredient.unit:
            part = f"{part} {ingredient.amount}{ingredient.unit}"
        if ingredient.qualifier:
            part = f"{part} ({ingredient.qualifier})"
        chunks.append(part)
    if not chunks:
        return None
    return "; ".join(chunks)
