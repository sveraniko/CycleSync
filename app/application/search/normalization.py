import re
import unicodedata

CYR_TO_LAT = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "c",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ы": "y",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)


NOISE_RE = re.compile(r"[^\w\s/.-]+", flags=re.UNICODE)
SPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_search_query(value: str) -> str:
    lowered = unicodedata.normalize("NFKC", value).strip().lower().translate(CYR_TO_LAT)
    cleaned = NOISE_RE.sub(" ", lowered)
    cleaned = cleaned.replace("мг", "mg").replace("мл", "ml")
    cleaned = cleaned.replace("миллиграм", "mg")
    cleaned = SPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def tokenize_for_search(value: str) -> list[str]:
    normalized = normalize_search_query(value)
    return TOKEN_RE.findall(normalized)


def normalize_token_set(*parts: str | None) -> list[str]:
    token_set: set[str] = set()
    for part in parts:
        if not part:
            continue
        token_set.update(tokenize_for_search(part))
    return sorted(token_set)
