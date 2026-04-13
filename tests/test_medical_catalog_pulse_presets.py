import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.application.catalog.mapping import map_sheet_row
from app.application.protocols.pulse_engine import PulseCalculationEngine
from app.application.protocols.schemas import DraftSettingsView, PulseIngredientProfile, PulseProductProfile
from app.infrastructure.catalog.xlsx_gateway import XlsxCatalogConfig, XlsxCatalogGateway


def _pulse_profiles(rows: list[dict[str, str]]) -> list[PulseProductProfile]:
    profiles: list[PulseProductProfile] = []
    for row in rows:
        product, issue = map_sheet_row(row=row, row_number=0)
        assert issue is None and product is not None
        profiles.append(
            PulseProductProfile(
                product_id=uuid5(NAMESPACE_URL, f"cyclesync:{product.source_row_key}"),
                product_name=product.trade_name,
                concentration_mg_ml=product.concentration_value,
                max_injection_volume_ml=product.max_injection_volume_ml,
                ingredients=[
                    PulseIngredientProfile(
                        ingredient_name=ingredient.ingredient_name if not ingredient.qualifier else f"{ingredient.ingredient_name} {ingredient.qualifier}",
                        half_life_days=ingredient.half_life_days,
                        amount_mg=ingredient.amount,
                        is_pulse_driver=ingredient.is_pulse_driver,
                        dose_guidance_min_mg_week=ingredient.dose_guidance_min_mg_week,
                        dose_guidance_max_mg_week=ingredient.dose_guidance_max_mg_week,
                        dose_guidance_typical_mg_week=ingredient.dose_guidance_typical_mg_week,
                    )
                    for ingredient in product.ingredients
                ],
            )
        )
    return profiles


def test_seed_catalog_preset_runs() -> None:
    workbook = Path('docs/medical.xlsx')

    async def _load() -> list[dict[str, str]]:
        return await XlsxCatalogGateway(XlsxCatalogConfig(workbook_path=str(workbook), sheet_name='Catalog')).fetch_rows()

    rows = asyncio.run(_load())
    products = _pulse_profiles(rows)
    engine = PulseCalculationEngine()

    for preset in ('unified_rhythm', 'layered_pulse', 'golden_pulse'):
        settings = DraftSettingsView(
            draft_id=uuid5(NAMESPACE_URL, f'seed:{preset}'),
            protocol_input_mode=None,
            weekly_target_total_mg=Decimal('700'),
            duration_weeks=8,
            preset_code=preset,
            max_injection_volume_ml=Decimal('1.5'),
            max_injections_per_week=4,
            planned_start_date=None,
            updated_at=datetime.now(timezone.utc),
        )
        result = engine.calculate(settings=settings, products=products)
        assert result.status in {'success', 'success_with_warnings', 'degraded_fallback'}
        assert result.entries
        assert result.summary_metrics is not None
        assert (result.summary_metrics or {}).get('guidance_coverage_score', 0) >= 50
