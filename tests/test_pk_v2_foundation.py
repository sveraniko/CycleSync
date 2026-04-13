from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.application.protocols.engine_selector import build_live_pulse_engine, resolve_pulse_engine_version
from app.application.protocols.pk_v2 import (
    FirstOrderPKEngineV2,
    IngredientPKProfile,
    PKDoseEvent,
    PKSimulationInput,
    ProductPKProfile,
    build_simulation_input_from_pulse_plan,
    decompose_product_dose,
    group_doses_by_parent_substance,
)
from app.application.protocols.schemas import PulsePlanEntry
from app.core.config import Settings


def _build_profile(
    *,
    product_key: str,
    ingredient_rows: list[tuple[str, str, Decimal, Decimal, Decimal | None]],
) -> ProductPKProfile:
    return ProductPKProfile(
        product_id=uuid4(),
        product_key=product_key,
        release_form="injectable_oil",
        ingredients=[
            IngredientPKProfile(
                ingredient_name=ingredient_name,
                parent_substance=parent,
                basis="per_ml",
                amount_per_ml_mg=amount_per_ml,
                amount_per_unit_mg=None,
                half_life_days=half_life_days,
                active_fraction=Decimal("1"),
                tmax_hours=tmax,
            )
            for ingredient_name, parent, amount_per_ml, half_life_days, tmax in ingredient_rows
        ],
    )


def test_single_ingredient_curve_simulation() -> None:
    profile = _build_profile(
        product_key="test_e",
        ingredient_rows=[("Testosterone Enanthate", "Testosterone", Decimal("250"), Decimal("5"), Decimal("12"))],
    )
    event = PKDoseEvent(day_offset=0, product_id=profile.product_id, product_key=profile.product_key, event_volume_ml=Decimal("1"))
    model = PKSimulationInput(draft_id=uuid4(), planned_start_date=date.today(), product_profiles=[profile], dose_events=[event], horizon_days=7)

    result = FirstOrderPKEngineV2().calculate(model)

    ingredient_curve = result.ingredient_curves["Testosterone Enanthate"]
    assert ingredient_curve[0].concentration == Decimal("0.00")
    assert ingredient_curve[12].concentration > ingredient_curve[1].concentration
    assert ingredient_curve[-1].concentration < ingredient_curve[24].concentration


def test_mixed_product_multi_ingredient_simulation() -> None:
    profile = _build_profile(
        product_key="mix",
        ingredient_rows=[
            ("TPP", "Testosterone", Decimal("50"), Decimal("2.5"), Decimal("4")),
            ("TC", "Testosterone", Decimal("200"), Decimal("8"), Decimal("14")),
            ("BU", "Boldenone", Decimal("200"), Decimal("14"), None),
        ],
    )
    event = PKDoseEvent(day_offset=0, product_id=profile.product_id, product_key=profile.product_key, event_volume_ml=Decimal("1.2"))
    model = PKSimulationInput(draft_id=uuid4(), planned_start_date=date.today(), product_profiles=[profile], dose_events=[event], horizon_days=10)

    result = FirstOrderPKEngineV2().calculate(model)

    assert {"TPP", "TC", "BU"}.issubset(set(result.ingredient_curves.keys()))
    assert {"Testosterone", "Boldenone"}.issubset(set(result.substance_curves.keys()))


def test_repeated_event_accumulation() -> None:
    profile = _build_profile(
        product_key="mast",
        ingredient_rows=[("Masteron Enanthate", "Drostanolone", Decimal("200"), Decimal("7"), None)],
    )
    events = [
        PKDoseEvent(day_offset=0, product_id=profile.product_id, product_key=profile.product_key, event_volume_ml=Decimal("1")),
        PKDoseEvent(day_offset=2, product_id=profile.product_id, product_key=profile.product_key, event_volume_ml=Decimal("1")),
    ]
    result = FirstOrderPKEngineV2().calculate(
        PKSimulationInput(draft_id=uuid4(), planned_start_date=date.today(), product_profiles=[profile], dose_events=events, horizon_days=10)
    )

    curve = result.ingredient_curves["Masteron Enanthate"]
    assert curve[48].concentration > curve[47].concentration


def test_parent_substance_aggregation_from_ingredient_curves() -> None:
    profile = _build_profile(
        product_key="sust",
        ingredient_rows=[
            ("Testosterone Phenylpropionate", "Testosterone", Decimal("60"), Decimal("4"), None),
            ("Testosterone Cypionate", "Testosterone", Decimal("100"), Decimal("8"), None),
        ],
    )
    event = PKDoseEvent(day_offset=0, product_id=profile.product_id, product_key=profile.product_key, event_volume_ml=Decimal("1"))
    result = FirstOrderPKEngineV2().calculate(
        PKSimulationInput(draft_id=uuid4(), planned_start_date=date.today(), product_profiles=[profile], dose_events=[event], horizon_days=5)
    )

    tp_curve = result.ingredient_curves["Testosterone Phenylpropionate"]
    tc_curve = result.ingredient_curves["Testosterone Cypionate"]
    testosterone_curve = result.substance_curves["Testosterone"]
    assert testosterone_curve[24].concentration == (tp_curve[24].concentration + tc_curve[24].concentration)


def test_flatness_metric_is_derived_from_simulated_series() -> None:
    profile = _build_profile(
        product_key="tp",
        ingredient_rows=[("TP", "Testosterone", Decimal("100"), Decimal("1.5"), None)],
    )
    sparse = [PKDoseEvent(day_offset=0, product_id=profile.product_id, product_key=profile.product_key, event_volume_ml=Decimal("1"))]
    dense = [PKDoseEvent(day_offset=d, product_id=profile.product_id, product_key=profile.product_key, event_volume_ml=Decimal("0.15")) for d in range(0, 7)]

    engine = FirstOrderPKEngineV2()
    sparse_result = engine.calculate(PKSimulationInput(draft_id=uuid4(), planned_start_date=date.today(), product_profiles=[profile], dose_events=sparse, horizon_days=7))
    dense_result = engine.calculate(PKSimulationInput(draft_id=uuid4(), planned_start_date=date.today(), product_profiles=[profile], dose_events=dense, horizon_days=7))

    assert dense_result.metrics.flatness_stability_score > sparse_result.metrics.flatness_stability_score


def test_warning_flags_emitted_on_degraded_pattern() -> None:
    profile = _build_profile(
        product_key="sust",
        ingredient_rows=[
            ("TPP", "Testosterone", Decimal("100"), Decimal("2"), None),
            ("TU", "Testosterone", Decimal("100"), Decimal("12"), None),
        ],
    )
    events = [PKDoseEvent(day_offset=0, product_id=profile.product_id, product_key=profile.product_key, event_volume_ml=Decimal("1"))]
    result = FirstOrderPKEngineV2().calculate(
        PKSimulationInput(
            draft_id=uuid4(),
            planned_start_date=date.today(),
            product_profiles=[profile],
            dose_events=events,
            horizon_days=14,
            resolution_hours=6,
            constraint_forced_longer_interval=True,
            inventory_forced_degradation=True,
        )
    )

    assert "mixed_ester_short_component_spikes" in result.warning_flags
    assert "constraint_forced_longer_interval" in result.warning_flags
    assert "inventory_forced_degradation" in result.warning_flags


def test_adapter_from_schedule_events_to_pk_input() -> None:
    profile = _build_profile(
        product_key="test_c",
        ingredient_rows=[("Testosterone Cypionate", "Testosterone", Decimal("200"), Decimal("8"), None)],
    )
    entries = [
        PulsePlanEntry(
            day_offset=3,
            scheduled_day=date.today(),
            product_id=profile.product_id,
            ingredient_context="TC",
            volume_ml=Decimal("0.7"),
            computed_mg=Decimal("140"),
            injection_event_key="evt_d3",
            sequence_no=0,
        )
    ]

    simulation_input = build_simulation_input_from_pulse_plan(
        draft_id=uuid4(),
        planned_start_date=date.today(),
        product_profiles=[profile],
        plan_entries=entries,
    )

    assert simulation_input.dose_events[0].day_offset == 3
    assert simulation_input.dose_events[0].event_volume_ml == Decimal("0.7")
    assert simulation_input.dose_events[0].product_key == "test_c"


def test_decompose_mixed_injectable_into_ingredients() -> None:
    profile = _build_profile(
        product_key="mix",
        ingredient_rows=[
            ("TPP", "Testosterone", Decimal("50"), Decimal("4.5"), None),
            ("TC", "Testosterone", Decimal("200"), Decimal("8"), None),
            ("BU", "Boldenone", Decimal("200"), Decimal("14"), None),
        ],
    )
    event = PKDoseEvent(day_offset=0, product_id=profile.product_id, product_key=profile.product_key, event_volume_ml=Decimal("1.2"))

    doses = decompose_product_dose(profile=profile, event=event)
    assert [dose.dose_mg for dose in doses] == [Decimal("60.0"), Decimal("240.0"), Decimal("240.0")]


def test_parent_substance_grouping() -> None:
    profile = _build_profile(
        product_key="sust",
        ingredient_rows=[
            ("TPP", "Testosterone", Decimal("60"), Decimal("4"), None),
            ("TC", "Testosterone", Decimal("100"), Decimal("8"), None),
        ],
    )
    event = PKDoseEvent(day_offset=0, product_id=profile.product_id, product_key=profile.product_key, event_volume_ml=Decimal("1"))
    doses = decompose_product_dose(profile=profile, event=event)
    grouped = group_doses_by_parent_substance(doses)

    assert grouped["Testosterone"] == Decimal("160")


def test_engine_config_defaults_to_v1() -> None:
    settings = Settings()
    assert resolve_pulse_engine_version(settings) == "v1"


def test_engine_selector_wires_requested_version() -> None:
    settings = Settings(pulse_engine_version="v2")
    engine = build_live_pulse_engine(settings)
    assert engine.pulse_engine_version == "v2"
