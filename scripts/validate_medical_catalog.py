import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

from app.application.catalog.mapping import map_sheet_row
from app.application.protocols.pulse_engine import PulseCalculationEngine
from app.application.protocols.schemas import (
    DraftSettingsView,
    PulseIngredientProfile,
    PulseProductProfile,
)
from app.application.search.normalization import tokenize_for_search
from app.application.search.projection import CompoundSearchProjectionBuilder
from app.application.search.schemas import CatalogIngredientRow, CatalogProjectionRow
from app.infrastructure.catalog.xlsx_gateway import XlsxCatalogConfig, XlsxCatalogGateway


def _product_from_row(row: dict[str, str]) -> PulseProductProfile:
    product, issue = map_sheet_row(row=row, row_number=0)
    if issue is not None or product is None:
        raise RuntimeError(f"Invalid catalog row {row.get('row_key')}: {issue.message if issue else 'unknown issue'}")
    return PulseProductProfile(
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


def _projection_row(row: dict[str, str]) -> CatalogProjectionRow:
    product, issue = map_sheet_row(row=row, row_number=0)
    if issue is not None or product is None:
        raise RuntimeError(f"Invalid catalog row {row.get('row_key')}: {issue.message if issue else 'unknown issue'}")
    return CatalogProjectionRow(
        product_id=uuid5(NAMESPACE_URL, f"cyclesync:{product.source_row_key}"),
        product_name=product.display_name,
        trade_name=product.trade_name,
        brand_name=product.brand_name,
        release_form=product.release_form,
        concentration_raw=product.concentration_raw,
        aliases=product.aliases,
        ingredients=[
            CatalogIngredientRow(
                ingredient_name=ingredient.ingredient_name,
                amount=str(ingredient.amount) if ingredient.amount is not None else None,
                unit=ingredient.unit,
                qualifier=ingredient.qualifier,
            )
            for ingredient in product.ingredients
        ],
        official_url=product.official_url,
        authenticity_notes=product.authenticity_notes,
        media_refs=product.image_refs,
    )


def _query_hits(query: str, documents: list[dict]) -> list[str]:
    tokens = set(tokenize_for_search(query))
    hits: list[tuple[int, str]] = []
    for document in documents:
        pool = set(document['normalized_tokens']) | set(document['ester_component_tokens']) | set(document['concentration_tokens']) | set(document['dosage_unit_tokens'])
        score = len(tokens & pool)
        if score > 0 and tokens.issubset(pool):
            hits.append((score, document['trade_name']))
    hits.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in hits]


async def main(workbook_path: str, output_path: str) -> None:
    gateway = XlsxCatalogGateway(XlsxCatalogConfig(workbook_path=workbook_path, sheet_name='Catalog'))
    rows = await gateway.fetch_rows()
    products = [_product_from_row(row) for row in rows]
    engine = PulseCalculationEngine()

    scenarios_gateway = XlsxCatalogGateway(XlsxCatalogConfig(workbook_path=workbook_path, sheet_name='PulseScenarios'))
    scenario_rows = await scenarios_gateway.fetch_rows()
    scenario_results = []
    for row in scenario_rows:
        settings = DraftSettingsView(
            draft_id=uuid5(NAMESPACE_URL, f"scenario:{row['scenario_id']}"),
            protocol_input_mode=None,
            weekly_target_total_mg=Decimal(row['weekly_target_total_mg']),
            duration_weeks=int(row['duration_weeks']),
            preset_code=row['preset_code'],
            max_injection_volume_ml=Decimal(row['max_injection_volume_ml']),
            max_injections_per_week=int(row['max_injections_per_week']),
            planned_start_date=None,
            updated_at=datetime.now(timezone.utc),
        )
        result = engine.calculate(settings=settings, products=products)
        scenario_results.append({
            'scenario_id': row['scenario_id'],
            'preset': row['preset_code'],
            'status': result.status,
            'preset_applied': result.preset_applied,
            'warning_flags': result.warning_flags,
            'allocation_mode': result.allocation_mode,
            'summary_metrics': result.summary_metrics,
            'entry_count': len(result.entries),
            'first_entries': [
                {
                    'day_offset': entry.day_offset,
                    'product_id': str(entry.product_id),
                    'ingredient_context': entry.ingredient_context,
                    'volume_ml': float(entry.volume_ml),
                    'computed_mg': float(entry.computed_mg),
                }
                for entry in result.entries[:8]
            ],
        })

    projection_builder = CompoundSearchProjectionBuilder()
    documents = [asdict(projection_builder.build_document(_projection_row(row))) for row in rows]
    search_gateway = XlsxCatalogGateway(XlsxCatalogConfig(workbook_path=workbook_path, sheet_name='SearchCases'))
    search_rows = await search_gateway.fetch_rows()
    search_results = []
    for row in search_rows:
        hits = _query_hits(row['query'], documents)
        search_results.append({
            'query': row['query'],
            'expected_primary_trade_name': row['expected_primary_trade_name'],
            'expected_hit': row['expected_hit'],
            'actual_hits': hits,
            'matched': (bool(hits) and row['expected_hit'] == 'yes' and hits[0] == row['expected_primary_trade_name']) or (not hits and row['expected_hit'] == 'no'),
        })

    payload = {
        'workbook_path': workbook_path,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'scenario_results': scenario_results,
        'search_results': search_results,
    }
    Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run pulse and search regressions against docs/medical.xlsx')
    parser.add_argument('workbook_path', nargs='?', default='docs/medical.xlsx')
    parser.add_argument('--out', default='docs/medical_validation_report.json')
    args = parser.parse_args()
    import asyncio
    asyncio.run(main(args.workbook_path, args.out))
