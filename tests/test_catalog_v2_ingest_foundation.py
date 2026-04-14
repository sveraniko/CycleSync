from decimal import Decimal


from app.application.catalog.v2_ingest import WorkbookV2Sheets, build_v2_inputs, read_workbook_v2


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


def test_v2_build_inputs_wires_structured_sources_and_media() -> None:
    sheets = WorkbookV2Sheets(
        products=[
            {
                "product_key": "p1",
                "brand": "B",
                "display_name": "Prod",
                "trade_name": "Prod",
                "release_form": "injectable_oil",
                "volume_per_package_ml": "10",
                "official_url": "https://official.example",
            }
        ],
        ingredients=[
            {
                "product_key": "p1",
                "ingredient_order": "1",
                "ingredient_name": "Test",
                "basis": "per_ml",
                "amount_per_ml_mg": "250",
                "half_life_days": "5",
                "active_fraction": "0.7",
            }
        ],
        sources=[
            {
                "product_key": "p1",
                "source_kind": "source",
                "label": "COA",
                "url": "https://coa.example",
                "priority": "1",
                "is_active": "true",
            },
            {
                "product_key": "p1",
                "source_kind": "community",
                "label": "Forum",
                "url": "https://forum.example",
                "priority": "2",
                "is_active": "false",
            },
        ],
        media=[
            {
                "product_key": "p1",
                "media_kind": "image",
                "ref": "https://img.example",
                "priority": "1",
                "is_cover": "true",
            }
        ],
        aliases=[],
    )

    products, issues = build_v2_inputs(sheets)
    assert not issues
    assert len(products) == 1
    assert products[0].source_links[0].label == "COA"
    assert products[0].source_links[1].is_active is False
    assert products[0].media_items[0].is_cover is True
