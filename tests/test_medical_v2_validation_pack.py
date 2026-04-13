import json
from pathlib import Path

from scripts.validate_medical_v2_catalog import (
    SCENARIO_PRODUCTS,
    build_summary_markdown,
    generate_validation_payload,
    main,
)


def test_v2_workbook_validation_smoke() -> None:
    payload = generate_validation_payload("docs/medical_v2.xlsx")

    ingest = payload["ingest_validation"]
    assert ingest["status"] == "ok"
    assert ingest["sheet_counts"]["Products"] > 0
    assert ingest["sheet_counts"]["Ingredients"] > 0


def test_scenario_runner_smoke() -> None:
    payload = generate_validation_payload("docs/medical_v2.xlsx")

    assert payload["primary_engine_version"] == "v2"
    assert payload["rollback_engine_version"] == "v1"
    v1 = payload["scenario_results"]["v1"]
    v2 = payload["scenario_results"]["v2"]
    assert v1 and v2
    assert {row["scenario_id"] for row in v1} == {row["scenario_id"] for row in v2}


def test_comparison_output_contains_deltas_and_strictness() -> None:
    payload = generate_validation_payload("docs/medical_v2.xlsx")

    comparisons = payload["comparisons"]
    assert comparisons
    sample = comparisons[0]
    assert "flatness_score_delta" in sample
    assert "peak_trough_spread_delta" in sample
    assert sample["strictness_change"] in {"same", "more_strict", "less_strict"}


def test_mixed_product_comparison_coverage() -> None:
    payload = generate_validation_payload("docs/medical_v2.xlsx")

    scenario_ids = {row["scenario_id"] for row in payload["scenario_results"]["v2"]}
    assert {"PKV2-S1", "PKV2-T1", "PKV2-M1"}.issubset(scenario_ids)
    assert any("pharmacom_mix1_vial" in SCENARIO_PRODUCTS[item] for item in scenario_ids if item in SCENARIO_PRODUCTS)


def test_tablet_scenario_in_inventory_mode() -> None:
    payload = generate_validation_payload("docs/medical_v2.xlsx")

    case = next(row for row in payload["scenario_results"]["v2"] if row["scenario_id"] == "PKV2-I1")
    assert "oxandrolonos" in case["scenario_product_keys"]
    assert case["scenario_input_mode"] == "inventory_constrained"


def test_search_regression_runner() -> None:
    payload = generate_validation_payload("docs/medical_v2.xlsx")

    search_results = payload["search_results"]
    assert search_results
    assert any(row["expected_hit"] == "no" for row in search_results)
    assert any(row["expected_hit"] == "yes" for row in search_results)
    assert sum(1 for row in search_results if row["matched"]) >= 8


def test_engine_traceability_fields_present_in_reports(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    summary = tmp_path / "summary.md"

    main("docs/medical_v2.xlsx", str(output), str(summary))

    payload = json.loads(output.read_text(encoding="utf-8"))
    first = payload["scenario_results"]["v2"][0]
    assert first["pulse_engine_version_used"] == "v2"
    assert first["evaluation_source"] == "pk_v2_simulated"

    summary_body = summary.read_text(encoding="utf-8")
    assert "Scenarios where V2 emitted new warnings" in summary_body
    assert "Mixed products most affected by V2" in summary_body
    assert build_summary_markdown(payload).startswith("# Medical V2 Validation Summary")
