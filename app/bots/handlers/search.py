from __future__ import annotations

from math import ceil
from typing import Any
from uuid import UUID

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.search.schemas import OpenCard, SearchResponse, SearchResultItem
from app.application.search.service import SearchApplicationService
from app.bots.core.flow import delete_user_input_message, safe_edit_or_send
from app.bots.core.formatting import escape_html_text

router = Router(name="search")

SEARCH_STATE_KEY = "search_panel_state"
CARD_STATE_KEY = "search_card_state"
PAGE_SIZE = 5


@router.message(F.text)
async def search_entrypoint(message: Message, state: FSMContext, search_service: SearchApplicationService) -> None:
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    await _render_search_page(
        message=message,
        state=state,
        search_service=search_service,
        query=text,
        page=0,
    )
    await delete_user_input_message(message)


@router.callback_query(F.data.startswith("search:open:"))
async def on_open_card(callback: CallbackQuery, state: FSMContext, search_service: SearchApplicationService) -> None:
    product_id = callback.data.split(":", 2)[2]
    card = await search_service.open_card(UUID(product_id))
    if card is None:
        await callback.answer("Карточка не найдена.", show_alert=True)
        return

    await state.update_data(
        **{
            CARD_STATE_KEY: {
                "product_id": product_id,
                "show_auth": False,
                "show_media": False,
                "show_sources": False,
            }
        }
    )

    await _render_card(callback.message, state, card)
    await callback.answer()


@router.callback_query(F.data.startswith("search:page:"))
async def on_search_page(callback: CallbackQuery, state: FSMContext, search_service: SearchApplicationService) -> None:
    page = int(callback.data.split(":", 2)[2])
    data = await state.get_data()
    panel_state = data.get(SEARCH_STATE_KEY) or {}
    query = panel_state.get("query")
    if not query:
        await callback.answer("Сессия поиска истекла. Введите запрос еще раз.", show_alert=True)
        return

    await _render_search_page(
        message=callback.message,
        state=state,
        search_service=search_service,
        query=str(query),
        page=page,
    )
    await callback.answer()


@router.callback_query(F.data == "search:back")
async def on_back_to_results(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    panel_state = data.get(SEARCH_STATE_KEY) or {}
    items_raw = panel_state.get("items") or []
    query = panel_state.get("query")
    total = panel_state.get("total", 0)
    page = panel_state.get("page", 0)
    if not query or not items_raw:
        await callback.answer("Сессия поиска истекла. Введите запрос снова.", show_alert=True)
        return

    items = [_deserialize_item(raw) for raw in items_raw]
    rendered = _render_search_panel(query=str(query), total=int(total), page=int(page), items=items)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=rendered,
        reply_markup=build_results_actions(items=items, page=int(page), total=int(total)),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("search:toggle:"))
async def on_toggle_section(callback: CallbackQuery, state: FSMContext, search_service: SearchApplicationService) -> None:
    section = callback.data.split(":", 2)[2]
    if section not in {"auth", "media", "sources"}:
        await callback.answer("Неизвестный раздел", show_alert=True)
        return

    data = await state.get_data()
    card_state = dict(data.get(CARD_STATE_KEY) or {})
    product_id = card_state.get("product_id")
    if not product_id:
        await callback.answer("Карточка не активна", show_alert=True)
        return

    state_key = {
        "auth": "show_auth",
        "media": "show_media",
        "sources": "show_sources",
    }[section]
    card_state[state_key] = not bool(card_state.get(state_key, False))
    await state.update_data(**{CARD_STATE_KEY: card_state})

    card = await search_service.open_card(UUID(str(product_id)))
    if card is None:
        await callback.answer("Карточка не найдена", show_alert=True)
        return

    await _render_card(callback.message, state, card)
    await callback.answer()


async def _render_search_page(
    *,
    message: Message,
    state: FSMContext,
    search_service: SearchApplicationService,
    query: str,
    page: int,
) -> None:
    safe_page = max(0, page)
    response = await search_service.search_products(
        query=query,
        user_id=str(message.from_user.id) if message.from_user else None,
        limit=PAGE_SIZE,
        offset=safe_page * PAGE_SIZE,
    )

    if response.degraded:
        await safe_edit_or_send(
            state=state,
            source_message=message,
            text="Search временно недоступен. Попробуйте чуть позже.",
        )
        return

    if not response.results:
        await safe_edit_or_send(
            state=state,
            source_message=message,
            text="Ничего не найдено. Попробуйте уточнить название или состав.",
        )
        return

    await state.update_data(
        **{
            SEARCH_STATE_KEY: {
                "query": response.query,
                "total": response.total,
                "page": safe_page,
                "items": [_serialize_item(item) for item in response.results],
            }
        }
    )

    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=_render_search_panel(
            query=response.query,
            total=response.total,
            page=safe_page,
            items=response.results,
        ),
        reply_markup=build_results_actions(items=response.results, page=safe_page, total=response.total),
        parse_mode=ParseMode.HTML,
    )


async def _render_card(message: Message, state: FSMContext, card: OpenCard) -> None:
    data = await state.get_data()
    card_state = data.get(CARD_STATE_KEY) or {}
    show_auth = bool(card_state.get("show_auth", False))
    show_media = bool(card_state.get("show_media", False))
    show_sources = bool(card_state.get("show_sources", False))

    text = _render_product_card(card, show_auth=show_auth, show_media=show_media, show_sources=show_sources)
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=text,
        reply_markup=build_card_actions(card, show_auth=show_auth, show_media=show_media, show_sources=show_sources),
        parse_mode=ParseMode.HTML,
    )


def _render_search_panel(*, query: str, total: int, page: int, items: list[SearchResultItem]) -> str:
    total_pages = max(1, ceil(total / PAGE_SIZE))
    lines = [
        "<b>Search</b>",
        f"Запрос: <code>{escape_html_text(query)}</code>",
        f"Найдено: <b>{total}</b> • Страница <b>{page + 1}/{total_pages}</b>",
        "",
    ]
    for idx, item in enumerate(items, start=1 + page * PAGE_SIZE):
        lines.append(_format_result_line(idx, item))
    return "\n".join(lines)


def _format_result_line(idx: int, item: SearchResultItem) -> str:
    name = escape_html_text(item.product_name)
    brand = escape_html_text(item.brand) or "—"
    form = escape_html_text(item.form_factor) if item.form_factor else "—"
    comp = escape_html_text(_shorten(item.composition_summary, limit=70)) if item.composition_summary else "—"
    return f"<b>{idx}.</b> {name}\n   {brand} • {form}\n   {comp}"


def _render_product_card(card: OpenCard, *, show_auth: bool, show_media: bool, show_sources: bool) -> str:
    lines = [
        f"<b>{escape_html_text(card.product_name)}</b>",
        f"Бренд: <b>{escape_html_text(card.brand) or '—'}</b>",
        f"Форма: {escape_html_text(card.form_factor) if card.form_factor else '—'}",
        "",
        "<b>Состав</b>",
        escape_html_text(card.composition_summary) if card.composition_summary else "—",
    ]

    if show_auth:
        lines.extend([
            "",
            "<b>Authenticity</b>",
            escape_html_text(card.authenticity_notes) if card.authenticity_notes else "Нет данных.",
        ])

    if show_media:
        lines.extend(["", "<b>Media references</b>"])
        if card.media_refs:
            for i, ref in enumerate(card.media_refs[:5], start=1):
                lines.append(f"• ref #{i}")
        else:
            lines.append("Нет данных.")

    if show_sources:
        lines.extend([
            "",
            "<b>Источники</b>",
            "Ссылки доступны кнопками ниже.",
        ])

    return "\n".join(lines)


def build_results_actions(*, items: list[SearchResultItem], page: int, total: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        rows.append(
            [
                InlineKeyboardButton(text=f"Open · {item.product_name[:20]}", callback_data=f"search:open:{item.product_id}"),
                InlineKeyboardButton(text="+Draft", callback_data=f"search:draft:{item.product_id}"),
            ]
        )

    total_pages = max(1, ceil(total / PAGE_SIZE))
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="← Prev", callback_data=f"search:page:{page - 1}"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="Next →", callback_data=f"search:page:{page + 1}"))
    if nav:
        rows.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_card_actions(card: OpenCard, *, show_auth: bool, show_media: bool, show_sources: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="Back to results", callback_data="search:back")],
        [InlineKeyboardButton(text="+Draft", callback_data=f"search:draft:{card.product_id}")],
        [
            InlineKeyboardButton(
                text=("Hide" if show_auth else "Show") + " authenticity",
                callback_data="search:toggle:auth",
            ),
            InlineKeyboardButton(
                text=("Hide" if show_media else "Show") + " media",
                callback_data="search:toggle:media",
            ),
        ],
    ]

    source_row = [
        InlineKeyboardButton(
            text=("Hide" if show_sources else "Show") + " sources",
            callback_data="search:toggle:sources",
        )
    ]
    rows.append(source_row)

    link_buttons: list[InlineKeyboardButton] = []
    if card.official_url:
        link_buttons.append(InlineKeyboardButton(text="Official", url=card.official_url))
    for i, ref in enumerate(card.media_refs[:3], start=1):
        link_buttons.append(InlineKeyboardButton(text=f"Source {i}", url=ref))

    for i in range(0, len(link_buttons), 2):
        rows.append(link_buttons[i : i + 2])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_result_actions(product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Open", callback_data=f"search:open:{product_id}"),
                InlineKeyboardButton(text="+Draft", callback_data=f"search:draft:{product_id}"),
            ]
        ]
    )


def _shorten(value: str | None, *, limit: int) -> str:
    if not value:
        return ""
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _serialize_item(item: SearchResultItem) -> dict[str, Any]:
    return {
        "document_id": item.document_id,
        "product_id": str(item.product_id),
        "product_name": item.product_name,
        "brand": item.brand,
        "composition_summary": item.composition_summary,
        "form_factor": item.form_factor,
    }


def _deserialize_item(raw: dict[str, Any]) -> SearchResultItem:
    return SearchResultItem(
        document_id=str(raw.get("document_id", "")),
        product_id=UUID(str(raw.get("product_id"))),
        product_name=str(raw.get("product_name", "")),
        brand=str(raw.get("brand", "")),
        composition_summary=raw.get("composition_summary"),
        form_factor=raw.get("form_factor"),
    )
