import re
from decimal import Decimal, InvalidOperation

MULTISPACE_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    cleaned = MULTISPACE_RE.sub(" ", value.strip())
    return cleaned


def normalize_lookup(value: str) -> str:
    lowered = normalize_text(value).lower()
    return lowered


def split_list_field(value: str) -> list[str]:
    if not value.strip():
        return []
    parts = re.split(r"[;,]", value)
    return [normalize_text(item) for item in parts if normalize_text(item)]


def normalize_unit(value: str | None) -> str | None:
    if not value:
        return None
    token = normalize_lookup(value)
    aliases = {
        "milligram": "mg",
        "milligrams": "mg",
        "мг": "mg",
        "milliliter": "ml",
        "milliliters": "ml",
        "мл": "ml",
    }
    return aliases.get(token, token)


def parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    normalized = value.strip().replace(",", ".")
    if not normalized:
        return None
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    token = normalize_lookup(value)
    if not token:
        return None
    if token in {"1", "true", "yes", "y", "да", "on"}:
        return True
    if token in {"0", "false", "no", "n", "нет", "off"}:
        return False
    return None


def normalize_concentration(concentration_raw: str | None) -> tuple[Decimal | None, str | None, str | None]:
    if not concentration_raw:
        return None, None, None

    text = normalize_lookup(concentration_raw)
    # Examples: "250 mg/ml", "100mg per ml"
    match = re.search(r"([0-9]+(?:[\.,][0-9]+)?)\s*([a-zA-Zа-яА-Я]+)\s*(?:/|per\s+)([a-zA-Zа-яА-Я]+)", text)
    if not match:
        return parse_decimal(text), None, None

    value_raw, unit_raw, basis_raw = match.groups()
    return parse_decimal(value_raw), normalize_unit(unit_raw), normalize_unit(basis_raw)
