from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import escape
from uuid import UUID


def format_decimal_human(value: Decimal | int | float | str | None, precision: int = 2) -> str:
    if value is None:
        return "—"
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)

    quant = Decimal("1") if precision <= 0 else Decimal("1").scaleb(-precision)
    normalized = decimal_value.quantize(quant).normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def compact_status_label(status: str | None) -> str:
    if not status:
        return "Неизвестно"
    normalized = status.strip().lower().replace("-", "_")
    label_map = {
        "success": "Успешно",
        "ok": "Успешно",
        "completed": "Завершено",
        "active": "Активно",
        "inactive": "Неактивно",
        "enabled": "Включено",
        "disabled": "Выключено",
        "pending": "В ожидании",
        "failed": "Ошибка",
        "error": "Ошибка",
        "warning": "Предупреждение",
        "denied": "Доступ запрещён",
        "granted": "Доступ предоставлен",
        "not_configured": "Не настроено",
    }
    if normalized in label_map:
        return label_map[normalized]
    token = normalized.replace("_", " ").strip()
    return token[:1].upper() + token[1:]


def mask_human_id(value: str | UUID | None, prefix: int = 4, suffix: int = 4) -> str:
    if value is None:
        return "—"
    raw = str(value)
    if len(raw) <= prefix + suffix:
        return raw
    return f"{raw[:prefix]}…{raw[-suffix:]}"


def escape_html_text(value: str | None) -> str:
    return escape(value or "")
