from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.application.protocols.pulse_engine import PulseCalculationEngine
from app.application.protocols.schemas import DraftSettingsView, PulseIngredientProfile, PulseProductProfile


def _settings(preset: str, max_inj: int = 4) -> DraftSettingsView:
    return DraftSettingsView(
        draft_id=uuid4(),
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
            ingredients=[PulseIngredientProfile("Test E", Decimal("4.5"), Decimal("250"), True)],
        ),
        PulseProductProfile(
            product_id=uuid4(),
            product_name="Short Ester",
            concentration_mg_ml=Decimal("100"),
            max_injection_volume_ml=Decimal("2.5"),
            ingredients=[PulseIngredientProfile("Test P", Decimal("1.2"), Decimal("100"), True)],
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


def test_failed_validation_status() -> None:
    result = PulseCalculationEngine().calculate(settings=None, products=[])
    assert result.status == "failed_validation"
    assert result.error_message == "validation_failed"
