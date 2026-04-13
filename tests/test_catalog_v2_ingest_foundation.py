from decimal import Decimal


from app.application.catalog.v2_ingest import build_v2_inputs, read_workbook_v2


def test_v2_workbook_ingredient_ingest_mixed_product() -> None:
    sheets = read_workbook_v2("docs/medical_v2.xlsx")
    products, issues = build_v2_inputs(sheets)
    assert not issues

    mix = next(item for item in products if item.product_key == "pharmacom_mix1_vial")
    assert len(mix.ingredients) == 3
    assert {ing.parent_substance for ing in mix.ingredients} == {"Testosterone", "Boldenone"}
    assert all(ing.half_life_days is not None for ing in mix.ingredients)
    assert all(ing.active_fraction is not None for ing in mix.ingredients)


def test_v2_validation_fails_on_missing_pk_critical_fields() -> None:
    sheets = read_workbook_v2("docs/medical_v2.xlsx")
    sheets.ingredients[0]["half_life_days"] = ""

    _, issues = build_v2_inputs(sheets)
    assert any("half_life_days" in issue.message for issue in issues)


def test_orphan_ingredient_detection() -> None:
    sheets = read_workbook_v2("docs/medical_v2.xlsx")
    sheets.ingredients.append(
        {
            "product_key": "missing_product",
            "ingredient_order": "99",
            "parent_substance": "X",
            "ingredient_name": "X",
            "basis": "per_ml",
            "amount_per_ml_mg": "100",
            "half_life_days": "3",
            "active_fraction": "0.8",
            "is_pulse_driver": "true",
        }
    )

    _, issues = build_v2_inputs(sheets)
    assert any("unknown product_key" in issue.message for issue in issues)
