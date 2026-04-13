import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.application.catalog.schemas import CatalogProductInput
from app.application.catalog.v2_ingest import build_v2_inputs, read_workbook_v2
from app.application.protocols.pulse_engine import PulseCalculationEngine
from app.application.protocols.schemas import (
    DraftSettingsView,
    InventoryConstraintView,
    PulseIngredientProfile,
    PulseProductProfile,
    StackInputTargetView,
)
from app.application.search.normalization import tokenize_for_search
from app.application.search.projection import CompoundSearchProjectionBuilder
from app.application.search.schemas import CatalogIngredientRow, CatalogProjectionRow

STATUS_SEVERITY = {
    "failed_validation": 4,
    "degraded_fallback": 3,
    "success_with_warnings": 2,
    "warning": 2,
    "success": 1,
}

SCENARIO_PRODUCTS: dict[str, list[str]] = {
    "PKV2-A1": ["pharma_bold_300"],
    "PKV2-S1": ["pharmacom_mix1_vial", "pharma_dro_e_200"],
    "PKV2-T1": ["pharmacom_mix1_vial", "pharma_bold_300", "pharma_tren_h_mix"],
    "PKV2-I1": ["pharma_sust_250_ampules", "oxandrolonos"],
    "PKV2-M1": ["pharma_sust_250_ampules"],
}

SCENARIO_TOTAL_TARGETS_MG: dict[str, Decimal] = {
    "PKV2-T1": Decimal("900"),
}

SCENARIO_STACK_TARGETS_MG: dict[str, dict[str, Decimal]] = {
    "PKV2-S1": {
        "pharmacom_mix1_vial": Decimal("500"),
        "pharma_dro_e_200": Decimal("300"),
    }
}

SCENARIO_INVENTORY_COUNTS: dict[str, dict[str, Decimal]] = {
    "PKV2-I1": {
        "pharma_sust_250_ampules": Decimal("3"),
        "oxandrolonos": Decimal("1"),
    }
}


def _row_is_data(row: dict[str, str]) -> bool:
    scenario_id = (row.get("scenario_id") or "").strip().lower()
    return bool(scenario_id) and not scenario_id.startswith("hint:")


def _to_pulse_profile(product: CatalogProductInput) -> PulseProductProfile:
    concentration_value = None
    max_volume = None
    if product.concentration_basis == "per_ml" and product.ingredients:
        concentration_value = sum((item.amount_per_ml_mg or Decimal("0")) for item in product.ingredients)
        max_volume = Decimal("1")

    return PulseProductProfile(
        product_id=uuid5(NAMESPACE_URL, f"cyclesync:{product.source_row_key}"),
        product_name=product.trade_name,
        concentration_mg_ml=concentration_value,
        max_injection_volume_ml=max_volume,
        package_kind=product.package_kind,
        units_per_package=product.units_per_package,
        volume_per_package_ml=product.volume_per_package_ml,
        unit_strength_mg=product.unit_strength_mg,
        ingredients=[
            PulseIngredientProfile(
                ingredient_name=ingredient.ingredient_name,
                half_life_days=ingredient.half_life_days,
                amount_mg=ingredient.amount,
                is_pulse_driver=ingredient.is_pulse_driver,
                dose_guidance_min_mg_week=ingredient.dose_guidance_min_mg_week,
                dose_guidance_max_mg_week=ingredient.dose_guidance_max_mg_week,
                dose_guidance_typical_mg_week=ingredient.dose_guidance_typical_mg_week,
                parent_substance=ingredient.parent_substance,
                ester_name=ingredient.ester_name,
                basis=ingredient.basis,
                amount_per_ml_mg=ingredient.amount_per_ml_mg,
                amount_per_unit_mg=ingredient.amount_per_unit_mg,
                active_fraction=ingredient.active_fraction,
                tmax_hours=ingredient.tmax_hours,
                release_model=ingredient.release_model,
            )
            for ingredient in product.ingredients
        ],
    )


def _projection_documents(products: list[CatalogProductInput]) -> list[dict]:
    builder = CompoundSearchProjectionBuilder()
    docs = []
    for product in products:
        projection = CatalogProjectionRow(
            product_id=uuid5(NAMESPACE_URL, f"cyclesync:{product.source_row_key}"),
            product_name=product.display_name,
            trade_name=product.trade_name,
            brand_name=product.brand_name,
            release_form=product.release_form,
            concentration_raw=product.concentration_raw,
            aliases=product.aliases,
            ingredients=[
                CatalogIngredientRow(
                    ingredient_name=ing.ingredient_name,
                    amount=str(ing.amount) if ing.amount is not None else None,
                    unit=ing.unit,
                    qualifier=ing.qualifier,
                )
                for ing in product.ingredients
            ],
            official_url=product.official_url,
            authenticity_notes=product.authenticity_notes,
            media_refs=product.image_refs,
        )
        doc = asdict(builder.build_document(projection))
        docs.append(doc)
    return docs


def _query_hits(query: str, documents: list[dict]) -> list[str]:
    tokens = set(tokenize_for_search(query))
    hits: list[tuple[int, str]] = []
    for document in documents:
        pool = set(document["normalized_tokens"]) | set(document["ester_component_tokens"]) | set(document["concentration_tokens"]) | set(document["dosage_unit_tokens"])
        score = len(tokens & pool)
        if tokens and score > 0 and tokens.issubset(pool):
            hits.append((score, document["trade_name"]))
    hits.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in hits]


def _extract_derived_weekly_total(summary_metrics: dict | None) -> float | None:
    if not summary_metrics:
        return None
    per_product = summary_metrics.get("per_product_weekly_target_mg")
    if not isinstance(per_product, dict):
        return None
    return float(sum(float(value) for value in per_product.values()))


def _entry_signature(entry: dict) -> tuple:
    return (
        entry["day_offset"],
        entry["product_id"],
        entry["ingredient_context"],
        round(float(entry["volume_ml"]), 4),
        round(float(entry["computed_mg"]), 4),
    )


def _run_single_scenario(
    *,
    scenario_row: dict[str, str],
    products_by_key: dict[str, PulseProductProfile],
    pulse_engine_version: str,
) -> dict:
    scenario_id = str(scenario_row["scenario_id"])
    product_keys = SCENARIO_PRODUCTS.get(scenario_id, [])
    selected_products = [products_by_key[key] for key in product_keys if key in products_by_key]

    weekly_target_total_mg = SCENARIO_TOTAL_TARGETS_MG.get(scenario_id)
    settings = DraftSettingsView(
        draft_id=uuid5(NAMESPACE_URL, f"scenario:{scenario_id}:{pulse_engine_version}"),
        protocol_input_mode=str(scenario_row.get("input_mode") or "total_target"),
        weekly_target_total_mg=weekly_target_total_mg,
        duration_weeks=int(scenario_row.get("duration_weeks") or 8),
        preset_code=str(scenario_row.get("preset") or "unified_rhythm"),
        max_injection_volume_ml=Decimal(str(scenario_row.get("max_injection_volume_ml") or "1")),
        max_injections_per_week=int(scenario_row.get("max_injections_per_week") or 2),
        planned_start_date=None,
        updated_at=datetime.now(timezone.utc),
    )

    stack_targets = [
        StackInputTargetView(
            id=uuid5(NAMESPACE_URL, f"scenario:{scenario_id}:stack:{key}"),
            draft_id=settings.draft_id,
            product_id=uuid5(NAMESPACE_URL, f"cyclesync:{key}"),
            protocol_input_mode="stack_smoothing",
            desired_weekly_mg=value,
            created_at=settings.updated_at,
            updated_at=settings.updated_at,
        )
        for key, value in SCENARIO_STACK_TARGETS_MG.get(scenario_id, {}).items()
    ]

    inventory_constraints = [
        InventoryConstraintView(
            id=uuid5(NAMESPACE_URL, f"scenario:{scenario_id}:inventory:{key}"),
            draft_id=settings.draft_id,
            product_id=uuid5(NAMESPACE_URL, f"cyclesync:{key}"),
            protocol_input_mode="inventory_constrained",
            available_count=value,
            count_unit="packages",
            created_at=settings.updated_at,
            updated_at=settings.updated_at,
        )
        for key, value in SCENARIO_INVENTORY_COUNTS.get(scenario_id, {}).items()
    ]

    engine = PulseCalculationEngine(pulse_engine_version=pulse_engine_version)
    result = engine.calculate(
        settings=settings,
        products=selected_products,
        stack_targets=stack_targets,
        inventory_constraints=inventory_constraints,
    )

    entries = [
        {
            "day_offset": entry.day_offset,
            "product_id": str(entry.product_id),
            "ingredient_context": entry.ingredient_context,
            "volume_ml": float(entry.volume_ml),
            "computed_mg": float(entry.computed_mg),
        }
        for entry in result.entries
    ]

    return {
        "scenario_id": scenario_id,
        "scenario_input_mode": settings.protocol_input_mode,
        "scenario_preset": settings.preset_code,
        "scenario_product_keys": product_keys,
        "status": result.status,
        "expected_status": scenario_row.get("expected_status"),
        "preset_applied": result.preset_applied,
        "warning_flags": result.warning_flags,
        "allocation_mode": result.allocation_mode,
        "summary_metrics": result.summary_metrics,
        "entry_count": len(result.entries),
        "entries": entries,
        "flatness_stability_score": (result.summary_metrics or {}).get("flatness_stability_score"),
        "estimated_injections_per_week": (result.summary_metrics or {}).get("estimated_injections_per_week"),
        "max_volume_per_event_ml": (result.summary_metrics or {}).get("max_volume_per_event_ml"),
        "derived_total_weekly_mg": _extract_derived_weekly_total(result.summary_metrics),
        "pulse_engine_version_used": (result.summary_metrics or {}).get("pulse_engine_version_used"),
        "evaluation_source": (result.summary_metrics or {}).get("evaluation_source"),
        "validation_issues": result.validation_issues,
    }


def _compare_pair(v1: dict, v2: dict) -> dict:
    v1_summary = v1.get("summary_metrics") or {}
    v2_summary = v2.get("summary_metrics") or {}
    v1_flags = set(v1.get("warning_flags") or [])
    v2_flags = set(v2.get("warning_flags") or [])
    status_v1 = str(v1.get("status"))
    status_v2 = str(v2.get("status"))

    return {
        "scenario_id": v1["scenario_id"],
        "engine_versions": ["v1", "v2"],
        "flatness_score_delta": (v2.get("flatness_stability_score") or 0) - (v1.get("flatness_stability_score") or 0),
        "peak_trough_spread_delta": (v2_summary.get("peak_trough_spread_pct") or 0) - (v1_summary.get("peak_trough_spread_pct") or 0),
        "warning_flags_added_in_v2": sorted(v2_flags - v1_flags),
        "warning_flags_removed_in_v2": sorted(v1_flags - v2_flags),
        "schedule_same_but_evaluation_changed": sorted(_entry_signature(e) for e in v1["entries"]) == sorted(_entry_signature(e) for e in v2["entries"]) and (
            v1.get("flatness_stability_score") != v2.get("flatness_stability_score") or v1_flags != v2_flags
        ),
        "strictness_change": (
            "more_strict"
            if STATUS_SEVERITY.get(status_v2, 0) > STATUS_SEVERITY.get(status_v1, 0)
            else "less_strict"
            if STATUS_SEVERITY.get(status_v2, 0) < STATUS_SEVERITY.get(status_v1, 0)
            else "same"
        ),
        "status_v1": status_v1,
        "status_v2": status_v2,
    }


def generate_validation_payload(workbook_path: str) -> dict:
    sheets = read_workbook_v2(workbook_path)
    products, ingest_issues = build_v2_inputs(sheets)

    issue_payload = [{"row_key": issue.row_key, "message": issue.message} for issue in ingest_issues]

    pulse_profiles = {product.source_row_key: _to_pulse_profile(product) for product in products}

    # We intentionally fetch regression sheets directly to keep production ingest scope stable.
    from app.infrastructure.catalog.xlsx_gateway import XlsxCatalogConfig, XlsxCatalogGateway
    import asyncio

    async def _load(sheet_name: str) -> list[dict[str, str]]:
        return await XlsxCatalogGateway(XlsxCatalogConfig(workbook_path=workbook_path, sheet_name=sheet_name)).fetch_rows()

    pulse_rows = [row for row in asyncio.run(_load("PulseScenarios")) if _row_is_data(row)]
    search_rows = asyncio.run(_load("SearchCases"))

    scenarios_by_engine = {"v1": [], "v2": []}
    for row in pulse_rows:
        for engine_version in ("v1", "v2"):
            scenarios_by_engine[engine_version].append(
                _run_single_scenario(
                    scenario_row=row,
                    products_by_key=pulse_profiles,
                    pulse_engine_version=engine_version,
                )
            )

    v1_by_id = {item["scenario_id"]: item for item in scenarios_by_engine["v1"]}
    comparisons = [_compare_pair(v1_by_id[item["scenario_id"]], item) for item in scenarios_by_engine["v2"]]

    search_documents = _projection_documents(products)
    search_results = []
    for row in search_rows:
        query = str(row.get("query") or "")
        expected_hit = str(row.get("expected_hit") or "")
        expected_primary = str(row.get("expected_primary_trade_name") or "")
        actual_hits = _query_hits(query, search_documents)
        matched = (bool(actual_hits) and expected_hit == "yes" and actual_hits[0] == expected_primary) or (
            not actual_hits and expected_hit == "no"
        )
        search_results.append(
            {
                "query": query,
                "expected_primary_trade_name": expected_primary,
                "expected_hit": expected_hit,
                "actual_hits": actual_hits,
                "matched": matched,
                "notes": row.get("notes"),
            }
        )

    return {
        "workbook_path": workbook_path,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "ingest_validation": {
            "status": "ok" if not issue_payload else "issues_detected",
            "issue_count": len(issue_payload),
            "issues": issue_payload,
            "sheet_counts": {
                "Products": len(sheets.products),
                "Ingredients": len(sheets.ingredients),
                "PulseScenarios": len(pulse_rows),
                "SearchCases": len(search_rows),
            },
        },
        "scenario_results": scenarios_by_engine,
        "comparisons": comparisons,
        "search_results": search_results,
    }


def build_summary_markdown(payload: dict) -> str:
    comparisons = payload["comparisons"]
    search_results = payload["search_results"]

    no_diff = [item["scenario_id"] for item in comparisons if abs(item["flatness_score_delta"]) < 0.01 and not item["warning_flags_added_in_v2"] and not item["warning_flags_removed_in_v2"]]
    high_flatness = [item for item in comparisons if abs(item["flatness_score_delta"]) >= 5]
    new_warnings = [item for item in comparisons if item["warning_flags_added_in_v2"]]
    mixed_focus = [item for item in comparisons if item["scenario_id"] in {"PKV2-S1", "PKV2-T1", "PKV2-M1", "PKV2-I1"}]

    lines = [
        "# Medical V2 Validation Summary",
        "",
        f"Generated at: `{payload['generated_at_utc']}`",
        "",
        "## Scenarios with no material difference",
        "",
    ]
    if no_diff:
        lines.extend([f"- `{scenario_id}`" for scenario_id in no_diff])
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Scenarios where V2 changed flatness significantly (|delta| >= 5)",
        "",
    ])
    if high_flatness:
        lines.extend([f"- `{item['scenario_id']}`: delta `{item['flatness_score_delta']:.2f}`" for item in high_flatness])
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Scenarios where V2 emitted new warnings",
        "",
    ])
    if new_warnings:
        lines.extend([f"- `{item['scenario_id']}`: +{', '.join(item['warning_flags_added_in_v2'])}" for item in new_warnings])
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Mixed products most affected by V2",
        "",
    ])
    for item in mixed_focus:
        lines.append(
            f"- `{item['scenario_id']}`: flatness delta `{item['flatness_score_delta']:.2f}`, strictness `{item['strictness_change']}`, schedule_same_eval_changed=`{item['schedule_same_but_evaluation_changed']}`"
        )

    matched = sum(1 for row in search_results if row["matched"])
    lines.extend([
        "",
        "## Search regression",
        "",
        f"- Matched cases: `{matched}/{len(search_results)}`",
    ])
    return "\n".join(lines) + "\n"


def main(workbook_path: str, output_path: str, summary_path: str) -> None:
    payload = generate_validation_payload(workbook_path)
    Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(summary_path).write_text(build_summary_markdown(payload), encoding="utf-8")
    print(output_path)
    print(summary_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run V2 workbook pulse/search regression and V1-vs-V2 comparison")
    parser.add_argument("workbook_path", nargs="?", default="docs/medical_v2.xlsx")
    parser.add_argument("--out", default="docs/medical_v2_validation_report.json")
    parser.add_argument("--summary", default="docs/medical_v2_validation_summary.md")
    args = parser.parse_args()
    main(args.workbook_path, args.out, args.summary)
