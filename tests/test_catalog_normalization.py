from decimal import Decimal

from app.application.catalog.normalization import normalize_concentration, normalize_lookup, split_list_field


def test_normalize_lookup_trims_spacing_and_case() -> None:
    assert normalize_lookup("  Pharma   Com  ") == "pharma com"


def test_split_list_field_handles_semicolon_and_comma() -> None:
    assert split_list_field("a; b, c") == ["a", "b", "c"]


def test_normalize_concentration_parses_mg_per_ml() -> None:
    value, unit, basis = normalize_concentration("250 mg/ml")
    assert value == Decimal("250")
    assert unit == "mg"
    assert basis == "ml"
