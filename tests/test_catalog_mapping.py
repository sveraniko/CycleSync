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
