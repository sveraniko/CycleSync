from app.application.search.normalization import normalize_search_query, tokenize_for_search


def test_normalize_search_query_handles_cyrillic_and_noise() -> None:
    assert normalize_search_query("  Сустанон!! 250мг/мл ") == "sustanon 250mg/ml"


def test_tokenize_for_search_keeps_number_and_units() -> None:
    assert tokenize_for_search("pharma sust 500 mg") == ["pharma", "sust", "500", "mg"]
