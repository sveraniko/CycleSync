from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.application.protocols.pulse_engine import PulseCalculationEngine
from app.application.protocols.schemas import DraftSettingsView, PulseIngredientProfile, PulseProductProfile


def _settings(preset: str, max_inj: int = 4) -> DraftSettingsView:
    return DraftSettingsView(
        draft_id=uuid4(),
        protocol_input_mode="total_target",
        weekly_target_total_mg=Decimal("300"),
        duration_weeks=4,
        preset_code=preset,
        max_injection_volume_ml=Decimal("2.5"),
        max_injections_per_week=max_inj,
        planned_start_date=None,
        updated_at=datetime.now(timezone.utc),
    )


def _products() -> list[PulseProductProfile]:
    return [
        PulseProductProfile(
            product_id=uuid4(),
            product_name="Long Ester",
            concentration_mg_ml=Decimal("250"),
            max_injection_volume_ml=Decimal("2.5"),
            ingredients=[
                PulseIngredientProfile(
                    "Test E",
                    Decimal("4.5"),
                    Decimal("250"),
                    True,
                    dose_guidance_typical_mg_week=Decimal("200"),
                )
            ],
        ),
        PulseProductProfile(
            product_id=uuid4(),
            product_name="Short Ester",
            concentration_mg_ml=Decimal("100"),
            max_injection_volume_ml=Decimal("2.5"),
            ingredients=[
                PulseIngredientProfile(
                    "Test P",
                    Decimal("1.2"),
                    Decimal("100"),
                    True,
                    dose_guidance_typical_mg_week=Decimal("100"),
                )
            ],
        ),
    ]


def test_calculation_works_for_unified_preset() -> None:
    result = PulseCalculationEngine().calculate(settings=_settings("unified_rhythm"), products=_products())

    assert result.status in {"success", "success_with_warnings"}
    assert result.preset_applied == "unified_rhythm"
    assert result.summary_metrics is not None
    assert result.entries


def test_calculation_works_for_layered_preset() -> None:
    result = PulseCalculationEngine().calculate(settings=_settings("layered_pulse"), products=_products())

    assert result.status in {"success", "success_with_warnings"}
    assert result.preset_applied == "layered_pulse"
    assert result.entries


def test_golden_falls_back_to_layered_in_complex_case() -> None:
    products = _products() + [
        PulseProductProfile(
            product_id=uuid4(),
            product_name=f"P{i}",
            concentration_mg_ml=Decimal("200"),
            max_injection_volume_ml=Decimal("2.5"),
            ingredients=[PulseIngredientProfile("x", Decimal("2"), Decimal("100"), True)],
        )
        for i in range(3)
    ]
    result = PulseCalculationEngine().calculate(settings=_settings("golden_pulse"), products=products)

    assert result.status == "degraded_fallback"
    assert result.preset_applied == "layered_pulse"
    assert "golden_pulse_fallback_to_layered" in result.warning_flags


def test_schedule_generation_has_monotonic_offsets() -> None:
    result = PulseCalculationEngine().calculate(settings=_settings("layered_pulse"), products=_products())

    offsets = [entry.day_offset for entry in result.entries]
    assert offsets == sorted(offsets)
    assert all(entry.injection_event_key.startswith("evt_d") for entry in result.entries)


def test_allocation_prefers_typical_guidance_weights() -> None:
    result = PulseCalculationEngine().calculate(settings=_settings("layered_pulse"), products=_products())
    summary = result.summary_metrics or {}

    assert result.allocation_mode == "guidance_weighted"
    per_product = summary.get("per_product_weekly_target_mg") or {}
    allocations = sorted(per_product.values(), reverse=True)
    assert allocations[0] > allocations[1]
    assert summary.get("guidance_coverage_score", 0) > 80


def test_allocation_falls_back_to_equal_when_no_guidance_or_half_life() -> None:
    products = [
        PulseProductProfile(
            product_id=uuid4(),
            product_name="A",
            concentration_mg_ml=Decimal("200"),
            max_injection_volume_ml=Decimal("2.5"),
            ingredients=[PulseIngredientProfile("A", None, Decimal("100"), None)],
        ),
        PulseProductProfile(
            product_id=uuid4(),
            product_name="B",
            concentration_mg_ml=Decimal("200"),
            max_injection_volume_ml=Decimal("2.5"),
            ingredients=[PulseIngredientProfile("B", None, Decimal("100"), None)],
        ),
    ]
    result = PulseCalculationEngine().calculate(settings=_settings("unified_rhythm"), products=products)
    assert result.allocation_mode == "equal_fallback"
    assert "allocation_used_equal_fallback" in (result.calculation_quality_flags or [])


def test_driver_influence_for_driver_biased_mode() -> None:
    products = [
        PulseProductProfile(
            product_id=uuid4(),
            product_name="Driver",
            concentration_mg_ml=Decimal("250"),
            max_injection_volume_ml=Decimal("2.5"),
            ingredients=[PulseIngredientProfile("D", Decimal("2"), Decimal("100"), True)],
        ),
        PulseProductProfile(
            product_id=uuid4(),
            product_name="Non-driver",
            concentration_mg_ml=Decimal("250"),
            max_injection_volume_ml=Decimal("2.5"),
            ingredients=[PulseIngredientProfile("N", Decimal("2"), Decimal("100"), False)],
        ),
    ]
    result = PulseCalculationEngine().calculate(settings=_settings("layered_pulse"), products=products)
    summary = result.summary_metrics or {}
    assert result.allocation_mode == "driver_biased"
    allocations = summary.get("per_product_weekly_target_mg") or {}
    assert max(allocations.values()) != min(allocations.values())


def test_weighted_effective_half_life_for_mixed_product() -> None:
    product = PulseProductProfile(
        product_id=uuid4(),
        product_name="Mix",
        concentration_mg_ml=Decimal("250"),
        max_injection_volume_ml=Decimal("2.5"),
        ingredients=[
            PulseIngredientProfile("Long", Decimal("7"), Decimal("200"), True),
            PulseIngredientProfile("Short", Decimal("1"), Decimal("100"), False),
        ],
    )

    value = PulseCalculationEngine._effective_half_life(product)
    # with driver boost (200*1.15 + 100) weight => 5.1818 days
    assert value == Decimal("5.1818")


def test_allocation_boundary_evaluation_flags_outside_guidance_band() -> None:
    products = [
        PulseProductProfile(
            product_id=uuid4(),
            product_name="A",
            concentration_mg_ml=Decimal("200"),
            max_injection_volume_ml=Decimal("2.5"),
            ingredients=[
                PulseIngredientProfile(
                    "A",
                    Decimal("4"),
                    Decimal("100"),
                    True,
                    dose_guidance_typical_mg_week=Decimal("200"),
                    dose_guidance_min_mg_week=Decimal("120"),
                    dose_guidance_max_mg_week=Decimal("150"),
                )
            ],
        ),
        PulseProductProfile(
            product_id=uuid4(),
            product_name="B",
            concentration_mg_ml=Decimal("200"),
            max_injection_volume_ml=Decimal("2.5"),
            ingredients=[
                PulseIngredientProfile(
                    "B",
                    Decimal("2"),
                    Decimal("100"),
                    True,
                    dose_guidance_typical_mg_week=Decimal("100"),
                    dose_guidance_min_mg_week=Decimal("40"),
                    dose_guidance_max_mg_week=Decimal("80"),
                )
            ],
        ),
    ]
    result = PulseCalculationEngine().calculate(settings=_settings("layered_pulse"), products=products)

    assert "allocation_above_guidance_for_some_products" in result.calculation_quality_flags
    assert "allocation_outside_guidance_band" in result.calculation_quality_flags
    assert (result.summary_metrics or {}).get("guidance_band_fit_score") < 100


def test_golden_pulse_optimization_is_deterministic_and_non_regressive() -> None:
    products = _products()
    settings = _settings("golden_pulse", max_inj=4)

    first = PulseCalculationEngine().calculate(settings=settings, products=products)
    second = PulseCalculationEngine().calculate(settings=settings, products=products)

    assert (first.summary_metrics or {}).get("flatness_stability_score") == (second.summary_metrics or {}).get(
        "flatness_stability_score"
    )
    assert (first.summary_metrics or {}).get("optimization_gain", 0) >= 0


def test_preview_summary_contains_new_math_diagnostics() -> None:
    result = PulseCalculationEngine().calculate(settings=_settings("golden_pulse", max_inj=4), products=_products())
    summary = result.summary_metrics or {}
    details = result.allocation_details or {}

    assert "guidance_band_fit_score" in summary
    assert "effective_half_life_mode" in summary
    assert "optimization_applied" in summary
    assert "optimization_gain" in summary
    assert "half_life_resolution_quality" in summary
    assert "per_product_guidance_band" in details
    assert "per_product_effective_half_life_days" in details


def test_failed_validation_status() -> None:
    result = PulseCalculationEngine().calculate(settings=None, products=[])
    assert result.status == "failed_validation"
    assert result.error_message == "validation_failed"


def test_auto_pulse_mode_does_not_require_total_target() -> None:
    settings = _settings("layered_pulse")
    settings.protocol_input_mode = "auto_pulse"
    settings.weekly_target_total_mg = None
    result = PulseCalculationEngine().calculate(settings=settings, products=_products())
    assert result.status in {"success", "success_with_warnings", "degraded_fallback"}
    assert result.protocol_input_mode == "auto_pulse"
    assert result.allocation_mode == "auto_pulse_guidance_driven"


def test_locked_mode_returns_clean_validation_issue() -> None:
    settings = _settings("layered_pulse")
    settings.protocol_input_mode = "stack_smoothing"
    result = PulseCalculationEngine().calculate(settings=settings, products=_products())
    assert result.status == "failed_validation"
    assert "stack_smoothing_not_yet_available" in result.validation_issues
