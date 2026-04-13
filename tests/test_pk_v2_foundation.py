from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.application.protocols.engine_selector import resolve_pulse_engine_version
from app.application.protocols.pk_v2 import (
    IngredientPKProfile,
    ProductPKProfile,
    ProtocolPKInput,
    decompose_product_dose,
    group_doses_by_parent_substance,
)
from app.core.config import Settings


def test_decompose_mixed_injectable_into_ingredients() -> None:
    profile = ProductPKProfile(
        product_id=uuid4(),
        product_key="mix",
        release_form="injectable_oil",
        ingredients=[
            IngredientPKProfile("TPP", "Testosterone", "per_ml", Decimal("50"), None, Decimal("4.5"), Decimal("0.72")),
            IngredientPKProfile("TC", "Testosterone", "per_ml", Decimal("200"), None, Decimal("8"), Decimal("0.7")),
            IngredientPKProfile("BU", "Boldenone", "per_ml", Decimal("200"), None, Decimal("14"), Decimal("0.62")),
        ],
    )

    doses = decompose_product_dose(profile=profile, event_volume_ml=Decimal("1.2"), event_unit_count=None)
    assert [dose.dose_mg for dose in doses] == [Decimal("60.0"), Decimal("240.0"), Decimal("240.0")]


def test_parent_substance_grouping() -> None:
    profile = ProductPKProfile(
        product_id=uuid4(),
        product_key="sust",
        release_form="injectable_oil",
        ingredients=[
            IngredientPKProfile("TPP", "Testosterone", "per_ml", Decimal("60"), None, Decimal("4"), Decimal("0.7")),
            IngredientPKProfile("TC", "Testosterone", "per_ml", Decimal("100"), None, Decimal("8"), Decimal("0.7")),
        ],
    )
    doses = decompose_product_dose(profile=profile, event_volume_ml=Decimal("1"), event_unit_count=None)
    grouped = group_doses_by_parent_substance(doses)
    assert grouped["Testosterone"] == Decimal("160")


def test_pk_v2_protocol_model_smoke() -> None:
    model = ProtocolPKInput(draft_id=uuid4(), planned_start_date=date.today(), product_profiles=[])
    assert model.product_profiles == []


def test_engine_config_defaults_to_v1() -> None:
    settings = Settings()
    assert resolve_pulse_engine_version(settings) == "v1"
