from decimal import Decimal

from app.application.catalog.mapping import map_sheet_row


def test_map_sheet_row_minimal_valid_row() -> None:
    product, issue = map_sheet_row(
        {
            "row_key": "42",
            "brand": "PharmaCom",
            "display_name": "Sustanon 250",
            "trade_name": "Sustanon",
            "ingredients": "Testosterone|Phenylpropionate|60|mg|ml",
            "aliases": "sust 250; сустанон",
        },
        row_number=42,
    )

    assert issue is None
    assert product is not None
    assert product.source_row_key == "42"
    assert product.brand_name == "PharmaCom"
    assert product.ingredients[0].amount == Decimal("60")
    assert product.aliases == ["sust 250", "сустанон"]


def test_map_sheet_row_reports_missing_brand() -> None:
    product, issue = map_sheet_row(
        {
            "row_key": "7",
            "display_name": "No Brand Product",
        },
        row_number=7,
    )

    assert product is None
    assert issue is not None
    assert issue.row_key == "7"


def test_map_sheet_row_parses_pharmacology_columns() -> None:
    product, issue = map_sheet_row(
        {
            "row_key": "88",
            "brand": "PharmaCom",
            "display_name": "Enanthate 250",
            "trade_name": "Test E",
            "is_automatable": "yes",
            "max_injection_volume_ml": "2.5",
            "pharmacology_notes": "Long ester",
            "composition_basis_notes": "Label based",
            "ingredients": "Testosterone|Enanthate|250|mg|ml|4.5|150|600|350|true",
        },
        row_number=88,
    )

    assert issue is None
    assert product is not None
    assert product.max_injection_volume_ml == Decimal("2.5")
    assert product.is_automatable is True
    assert product.ingredients[0].half_life_days == Decimal("4.5")
    assert product.ingredients[0].dose_guidance_typical_mg_week == Decimal("350")
    assert product.ingredients[0].is_pulse_driver is True
