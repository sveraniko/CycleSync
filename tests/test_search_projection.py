from uuid import uuid4

from app.application.search.projection import CompoundSearchProjectionBuilder
from app.application.search.schemas import CatalogIngredientRow, CatalogProjectionRow


def test_projection_builder_builds_deterministic_document() -> None:
    builder = CompoundSearchProjectionBuilder()
    row = CatalogProjectionRow(
        product_id=uuid4(),
        product_name="Sustanon 250",
        trade_name="Sustanon",
        brand_name="Pharmacom",
        release_form="oil",
        concentration_raw="250 mg/ml",
        aliases=["sust", "суст"],
        ingredients=[
            CatalogIngredientRow(
                ingredient_name="Testosterone Phenylpropionate",
                amount="60",
                unit="mg",
                qualifier=None,
            )
        ],
        official_url="https://example.com/sustanon",
        authenticity_notes="Check QR",
        media_refs=["https://cdn/img.png"],
    )

    doc = builder.build_document(row)

    assert doc.product_name == "Sustanon 250"
    assert doc.brand == "Pharmacom"
    assert "sust" in doc.aliases
    assert "testosterone" in doc.ester_component_tokens
    assert "250" in doc.concentration_tokens
    assert doc.composition_summary == "Testosterone Phenylpropionate 60mg"
