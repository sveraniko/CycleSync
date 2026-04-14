from __future__ import annotations

from math import ceil
from typing import Any
from uuid import UUID

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.protocols import DraftApplicationService
from app.application.search.schemas import CardMediaItem, CardSourceLink, OpenCard, SearchResponse, SearchResultItem
from app.application.search.service import SearchApplicationService
from app.bots.core.flow import delete_user_input_message, safe_edit_or_send
from app.bots.core.formatting import escape_html_text
from app.bots.core.permissions import is_admin_user

router = Router(name="search")

SEARCH_STATE_KEY = "search_panel_state"
CARD_STATE_KEY = "search_card_state"
PAGE_SIZE = 5
MEDIA_DISPLAY_NONE = "none"
MEDIA_DISPLAY_ON_DEMAND = "on_demand"
MEDIA_DISPLAY_SHOW_COVER = "show_cover_on_open"
MEDIA_POLICY_IMPORT_ONLY = "import_only"
MEDIA_POLICY_MANUAL_ONLY = "manual_only"
MEDIA_POLICY_PREFER_MANUAL = "prefer_manual"
MEDIA_POLICY_MERGE = "merge"


@router.message(F.text)
async def search_entrypoint(
    message: Message,
    state: FSMContext,
    search_service: SearchApplicationService,
    draft_service: DraftApplicationService,
) -> None:
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    await _render_search_page(
        message=message,
        state=state,
        search_service=search_service,
        draft_service=draft_service,
        query=text,
        page=0,
    )
    await delete_user_input_message(message)


@router.callback_query(F.data.startswith("search:open:"))
async def on_open_card(
    callback: CallbackQuery,
    state: FSMContext,
    search_service: SearchApplicationService,
    admin_ids: tuple[int, ...] | None = None,
) -> None:
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
                "media_index": 0,
                "is_in_draft": False,  # updated by on_add_to_draft when item is added
                "show_admin_media_controls": False,
            }
        }
    )

    uid = callback.from_user.id if callback.from_user else None
    await _render_card(callback.message, state, card, is_admin=is_admin_user(uid, admin_ids))
    await callback.answer()


@router.callback_query(F.data.startswith("search:page:"))
async def on_search_page(
    callback: CallbackQuery,
    state: FSMContext,
    search_service: SearchApplicationService,
    draft_service: DraftApplicationService,
) -> None:
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
        draft_service=draft_service,
        query=str(query),
        page=page,
    )
    await callback.answer()


@router.callback_query(F.data == "search:back")
async def on_back_to_results(
    callback: CallbackQuery,
    state: FSMContext,
    draft_service: DraftApplicationService,
) -> None:
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
    draft_product_ids = await _get_draft_product_ids(draft_service, callback.from_user.id if callback.from_user else None)
    rendered = _render_search_panel(query=str(query), total=int(total), page=int(page), items=items)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=rendered,
        reply_markup=build_results_actions(items=items, page=int(page), total=int(total), draft_product_ids=draft_product_ids),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("search:toggle:"))
async def on_toggle_section(
    callback: CallbackQuery,
    state: FSMContext,
    search_service: SearchApplicationService,
    admin_ids: tuple[int, ...] | None = None,
) -> None:
    section = callback.data.split(":", 2)[2]
    if section not in {"auth", "media", "sources", "admin_media"}:
        await callback.answer("Неизвестный раздел", show_alert=True)
        return

    data = await state.get_data()
    card_state = dict(data.get(CARD_STATE_KEY) or {})
    product_id = card_state.get("product_id")
    if not product_id:
        await callback.answer("Карточка не активна", show_alert=True)
        return

    if section == "admin_media":
        uid = callback.from_user.id if callback.from_user else None
        if not is_admin_user(uid, admin_ids):
            await callback.answer("Нет доступа", show_alert=True)
            return
        card_state["show_admin_media_controls"] = not bool(card_state.get("show_admin_media_controls", False))
        await state.update_data(**{CARD_STATE_KEY: card_state})

        card = await search_service.open_card(UUID(str(product_id)))
        if card is None:
            await callback.answer("Карточка не найдена", show_alert=True)
            return
        await _render_card(callback.message, state, card, is_admin=True)
        await callback.answer()
        return

    state_key = {
        "auth": "show_auth",
        "media": "show_media",
        "sources": "show_sources",
    }[section]
    card_state[state_key] = not bool(card_state.get(state_key, False))
    if section == "media" and not card_state[state_key]:
        card_state["media_index"] = 0
    await state.update_data(**{CARD_STATE_KEY: card_state})

    card = await search_service.open_card(UUID(str(product_id)))
    if card is None:
        await callback.answer("Карточка не найдена", show_alert=True)
        return

    uid = callback.from_user.id if callback.from_user else None
    await _render_card(callback.message, state, card, is_admin=is_admin_user(uid, admin_ids))
    await callback.answer()


@router.callback_query(F.data.startswith("a:p:mp:"))
async def on_admin_product_media_policy(
    callback: CallbackQuery,
    state: FSMContext,
    search_service: SearchApplicationService,
    admin_ids: tuple[int, ...] | None = None,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not is_admin_user(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    _, _, _, product_id, value = callback.data.split(":", 4)
    if value not in {MEDIA_POLICY_IMPORT_ONLY, MEDIA_POLICY_MANUAL_ONLY, MEDIA_POLICY_PREFER_MANUAL, MEDIA_POLICY_MERGE}:
        await callback.answer("Некорректная policy", show_alert=True)
        return
    updated = await search_service.admin_update_product_media_settings(UUID(product_id), media_policy=value)
    if not updated:
        await callback.answer("Карточка не найдена", show_alert=True)
        return
    card = await search_service.open_card(UUID(product_id))
    if card is None:
        await callback.answer("Карточка не найдена", show_alert=True)
        return
    await _render_card(callback.message, state, card, is_admin=True)
    await callback.answer("Политика медиа обновлена")


@router.callback_query(F.data.startswith("a:p:dm:"))
async def on_admin_product_display_mode(
    callback: CallbackQuery,
    state: FSMContext,
    search_service: SearchApplicationService,
    admin_ids: tuple[int, ...] | None = None,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not is_admin_user(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    _, _, _, product_id, value = callback.data.split(":", 4)
    mode_map = {"n": MEDIA_DISPLAY_NONE, "od": MEDIA_DISPLAY_ON_DEMAND, "sc": MEDIA_DISPLAY_SHOW_COVER}
    mode_value = mode_map.get(value)
    if mode_value is None:
        await callback.answer("Некорректный display mode", show_alert=True)
        return
    updated = await search_service.admin_update_product_media_settings(UUID(product_id), media_display_mode=mode_value)
    if not updated:
        await callback.answer("Карточка не найдена", show_alert=True)
        return
    card = await search_service.open_card(UUID(product_id))
    if card is None:
        await callback.answer("Карточка не найдена", show_alert=True)
        return
    await _render_card(callback.message, state, card, is_admin=True)
    await callback.answer("Display mode обновлён")


@router.callback_query(F.data.startswith("a:p:st:"))
async def on_admin_product_sync_toggle(
    callback: CallbackQuery,
    state: FSMContext,
    search_service: SearchApplicationService,
    admin_ids: tuple[int, ...] | None = None,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not is_admin_user(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    _, _, _, product_id, channel = callback.data.split(":", 4)
    card = await search_service.open_card(UUID(product_id))
    if card is None:
        await callback.answer("Карточка не найдена", show_alert=True)
        return
    kwargs: dict[str, bool] = {}
    if channel == "i":
        kwargs["sync_images"] = not bool(card.sync_images)
    elif channel == "v":
        kwargs["sync_videos"] = not bool(card.sync_videos)
    elif channel == "s":
        kwargs["sync_sources"] = not bool(card.sync_sources)
    else:
        await callback.answer("Некорректный sync-канал", show_alert=True)
        return

    updated = await search_service.admin_update_product_media_settings(UUID(product_id), **kwargs)
    if not updated:
        await callback.answer("Карточка не найдена", show_alert=True)
        return
    updated_card = await search_service.open_card(UUID(product_id))
    if updated_card is None:
        await callback.answer("Карточка не найдена", show_alert=True)
        return
    await _render_card(callback.message, state, updated_card, is_admin=True)
    await callback.answer("Sync-флаг обновлён")


@router.callback_query(F.data.startswith("search:media:"))
async def on_media_gallery_nav(
    callback: CallbackQuery,
    state: FSMContext,
    search_service: SearchApplicationService,
    admin_ids: tuple[int, ...] | None = None,
) -> None:
    action = callback.data.split(":", 2)[2]
    if action not in {"prev", "next"}:
        await callback.answer("Неизвестное действие", show_alert=True)
        return

    data = await state.get_data()
    card_state = dict(data.get(CARD_STATE_KEY) or {})
    product_id = card_state.get("product_id")
    if not product_id:
        await callback.answer("Карточка не активна", show_alert=True)
        return

    card = await search_service.open_card(UUID(str(product_id)))
    if card is None:
        await callback.answer("Карточка не найдена", show_alert=True)
        return

    gallery_items = _effective_media_gallery(card)
    if not gallery_items:
        await callback.answer("Медиа отсутствуют", show_alert=False)
        return

    current_index = int(card_state.get("media_index", 0))
    delta = -1 if action == "prev" else 1
    card_state["media_index"] = (current_index + delta) % len(gallery_items)
    card_state["show_media"] = True
    await state.update_data(**{CARD_STATE_KEY: card_state})

    uid = callback.from_user.id if callback.from_user else None
    await _render_card(callback.message, state, card, is_admin=is_admin_user(uid, admin_ids))
    await callback.answer()


async def _render_search_page(
    *,
    message: Message,
    state: FSMContext,
    search_service: SearchApplicationService,
    draft_service: DraftApplicationService,
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
            text="Поиск временно недоступен. Попробуйте позже.",
        )
        return

    if not response.results:
        await safe_edit_or_send(
            state=state,
            source_message=message,
            text="Ничего не найдено. Попробуйте уточнить название или состав.",
        )
        return

    draft_product_ids = await _get_draft_product_ids(draft_service, message.from_user.id if message.from_user else None)

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
        reply_markup=build_results_actions(
            items=response.results,
            page=safe_page,
            total=response.total,
            draft_product_ids=draft_product_ids,
        ),
        parse_mode=ParseMode.HTML,
    )


async def _render_card(message: Message, state: FSMContext, card: OpenCard, is_admin: bool = False) -> None:
    data = await state.get_data()
    card_state = data.get(CARD_STATE_KEY) or {}
    show_auth = bool(card_state.get("show_auth", False))
    show_media = bool(card_state.get("show_media", False))
    show_sources = bool(card_state.get("show_sources", False))
    media_index = int(card_state.get("media_index", 0))
    is_in_draft = bool(card_state.get("is_in_draft", False))

    text = _render_product_card(
        card,
        show_auth=show_auth,
        show_media=show_media,
        show_sources=show_sources,
        media_index=media_index,
        is_admin=is_admin,
        show_admin_media_controls=bool(card_state.get("show_admin_media_controls", False)),
    )
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=text,
        reply_markup=build_card_actions(
            card,
            show_auth=show_auth,
            show_media=show_media,
            show_sources=show_sources,
            is_admin=is_admin,
            is_in_draft=is_in_draft,
            show_admin_media_controls=bool(card_state.get("show_admin_media_controls", False)),
        ),
        parse_mode=ParseMode.HTML,
    )


def _render_search_panel(*, query: str, total: int, page: int, items: list[SearchResultItem]) -> str:
    total_pages = max(1, ceil(total / PAGE_SIZE))
    lines = [
        "<b>Поиск</b>",
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


def _resolve_media_display_mode(card: OpenCard) -> str:
    mode = (card.media_display_mode or "").strip().lower()
    if mode in {MEDIA_DISPLAY_NONE, MEDIA_DISPLAY_ON_DEMAND, MEDIA_DISPLAY_SHOW_COVER}:
        return mode
    return MEDIA_DISPLAY_ON_DEMAND


def _policy_allows_layer(policy: str, layer: str | None) -> bool:
    normalized_layer = (layer or "import").strip().lower()
    if policy == MEDIA_POLICY_IMPORT_ONLY:
        return normalized_layer != "manual"
    if policy == MEDIA_POLICY_MANUAL_ONLY:
        return normalized_layer == "manual"
    return True


def _effective_media_gallery(card: OpenCard) -> list[CardMediaItem]:
    policy = (card.media_policy or MEDIA_POLICY_MERGE).strip().lower()
    valid_policy = policy if policy in {
        MEDIA_POLICY_IMPORT_ONLY,
        MEDIA_POLICY_MANUAL_ONLY,
        MEDIA_POLICY_PREFER_MANUAL,
        MEDIA_POLICY_MERGE,
    } else MEDIA_POLICY_MERGE
    allowed = [item for item in card.media_items if item.is_active and _policy_allows_layer(valid_policy, item.source_layer)]
    ordered = sorted(allowed, key=lambda x: x.priority)
    if valid_policy == MEDIA_POLICY_PREFER_MANUAL:
        return sorted(ordered, key=lambda x: ((x.source_layer or "import") != "manual", x.priority))
    return ordered




def _effective_source_links(card: OpenCard) -> list[CardSourceLink]:
    policy = (card.media_policy or MEDIA_POLICY_MERGE).strip().lower()
    valid_policy = policy if policy in {
        MEDIA_POLICY_IMPORT_ONLY,
        MEDIA_POLICY_MANUAL_ONLY,
        MEDIA_POLICY_PREFER_MANUAL,
        MEDIA_POLICY_MERGE,
    } else MEDIA_POLICY_MERGE
    allowed = [item for item in card.source_links if item.is_active and _policy_allows_layer(valid_policy, item.source_layer)]
    ordered = sorted(allowed, key=lambda x: x.priority)
    if valid_policy == MEDIA_POLICY_PREFER_MANUAL:
        return sorted(ordered, key=lambda x: ((x.source_layer or "import") != "manual", x.priority))
    return ordered


def _sync_flag_label(value: bool | None) -> str:
    return "ВКЛ" if bool(value) else "ВЫКЛ"


def _render_admin_media_status(card: OpenCard) -> list[str]:
    effective_sources = _effective_source_links(card)
    manual_media = sum(1 for item in card.media_items if item.is_active and (item.source_layer or "import") == "manual")
    import_media = sum(1 for item in card.media_items if item.is_active and (item.source_layer or "import") != "manual")
    manual_sources = sum(1 for item in card.source_links if item.is_active and (item.source_layer or "import") == "manual")
    import_sources = sum(1 for item in card.source_links if item.is_active and (item.source_layer or "import") != "manual")

    return [
        "",
        "<b>Админ: политика медиа и источников</b>",
        f"Политика медиа: <code>{(card.media_policy or MEDIA_POLICY_MERGE)}</code>",
        f"Режим показа: <code>{_resolve_media_display_mode(card)}</code>",
        f"Синк изображений: <b>{_sync_flag_label(card.sync_images)}</b>",
        f"Синк видео: <b>{_sync_flag_label(card.sync_videos)}</b>",
        f"Синк источников: <b>{_sync_flag_label(card.sync_sources)}</b>",
        f"Медиа: ручные={manual_media}, импорт={import_media}",
        f"Источники: активные={len(effective_sources)}, ручные={manual_sources}, импорт={import_sources}",
        "«Официальный источник» — основная кнопка; «Источники» — ссылки; «Медиа» — галерея.",
    ]
def _resolve_primary_cover(card: OpenCard) -> CardMediaItem | None:
    gallery = _effective_media_gallery(card)
    if not gallery:
        return None
    manual_cover = next((item for item in gallery if item.is_cover and (item.source_layer or "").lower() == "manual"), None)
    if manual_cover:
        return manual_cover
    import_cover = next((item for item in gallery if item.is_cover and (item.source_layer or "").lower() != "manual"), None)
    if import_cover:
        return import_cover
    return gallery[0]


def _media_type_label(media_kind: str) -> str:
    kind = media_kind.lower()
    if kind in {"image", "photo", "tg_photo"}:
        return "Image"
    if kind in {"video", "tg_video"}:
        return "Video"
    if kind in {"animation", "gif", "tg_animation"}:
        return "Animation"
    return kind.capitalize()


def _render_product_card(
    card: OpenCard,
    *,
    show_auth: bool,
    show_media: bool,
    show_sources: bool,
    media_index: int = 0,
    is_admin: bool = False,
    show_admin_media_controls: bool = False,
) -> str:
    display_mode = _resolve_media_display_mode(card)
    gallery = _effective_media_gallery(card)
    cover = _resolve_primary_cover(card)
    lines = [
        f"<b>{escape_html_text(card.product_name)}</b>",
        f"Бренд: <b>{escape_html_text(card.brand) or '—'}</b>",
        f"Форма: {escape_html_text(card.form_factor) if card.form_factor else '—'}",
        "",
        "<b>Состав</b>",
        escape_html_text(card.composition_summary) if card.composition_summary else "—",
    ]
    if not gallery:
        lines.extend(["", "<b>Медиа</b>", "Нет медиа-файлов."])
    elif display_mode == MEDIA_DISPLAY_SHOW_COVER and cover is not None:
        cover_tag = "manual cover" if (cover.source_layer or "").lower() == "manual" and cover.is_cover else "cover"
        lines.extend([
            "",
            "<b>Медиа</b>",
            f"Обложка при открытии: {_media_type_label(cover.media_kind)} • {cover_tag}",
            f"Доступно медиа: {len(gallery)} (откройте «Показать медиа»).",
        ])
    elif display_mode == MEDIA_DISPLAY_NONE:
        lines.extend(["", "<b>Медиа</b>", f"Скрыто режимом показа ({MEDIA_DISPLAY_NONE})."])
    else:
        lines.extend(["", "<b>Медиа</b>", f"Доступно медиа: {len(gallery)} (по кнопке «Показать медиа»)."])

    if show_auth:
        lines.extend([
            "",
            "<b>Проверка подлинности</b>",
            escape_html_text(card.authenticity_notes) if card.authenticity_notes else "Нет данных.",
        ])

    if show_media:
        lines.extend(["", "<b>Галерея медиа</b>"])
        if gallery:
            image_count = sum(1 for item in gallery if _media_type_label(item.media_kind) == "Image")
            video_count = sum(1 for item in gallery if _media_type_label(item.media_kind) in {"Video", "Animation"})
            lines.append(f"Изображения: {image_count} • Видео/анимации: {video_count} • Всего: {len(gallery)}")
            if cover:
                lines.append(
                    f"Primary cover: {_media_type_label(cover.media_kind)}"
                    + (" (manual)" if (cover.source_layer or "").lower() == "manual" else " (import)")
                )
            idx = media_index % len(gallery)
            current = gallery[idx]
            marker = " • COVER" if current is cover else ""
            lines.append(
                f"Текущий [{idx + 1}/{len(gallery)}]: {_media_type_label(current.media_kind)}"
                f" • priority={current.priority}{marker}"
            )
            lines.append(f"Ref: {escape_html_text(_shorten(current.ref, limit=90))}")
        else:
            lines.append("Нет медиа-файлов.")

    if show_sources:
        lines.extend(["", "<b>Источники</b>"])
        if card.official_url or _effective_source_links(card):
            lines.append("Ссылки доступны кнопками ниже.")
        else:
            lines.append("Нет данных.")

    if is_admin and show_admin_media_controls:
        lines.extend(_render_admin_media_status(card))

    return "\n".join(lines)


def build_results_actions(
    *,
    items: list[SearchResultItem],
    page: int,
    total: int,
    draft_product_ids: set[str] | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    _in_draft = draft_product_ids or set()
    for item in items:
        pid = str(item.product_id)
        if pid in _in_draft:
            draft_btn = InlineKeyboardButton(text="✅", callback_data="draft:open")
        else:
            draft_btn = InlineKeyboardButton(text="+В черновик", callback_data=f"search:draft:{item.product_id}")
        rows.append(
            [
                InlineKeyboardButton(text=f"Открыть · {item.product_name[:20]}", callback_data=f"search:open:{item.product_id}"),
                draft_btn,
            ]
        )

    total_pages = max(1, ceil(total / PAGE_SIZE))
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="← Назад", callback_data=f"search:page:{page - 1}"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="Далее →", callback_data=f"search:page:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="🏠 Главная", callback_data="nav:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_card_actions(
    card: OpenCard,
    *,
    show_auth: bool,
    show_media: bool,
    show_sources: bool,
    is_admin: bool = False,
    is_in_draft: bool = False,
    show_admin_media_controls: bool = False,
) -> InlineKeyboardMarkup:
    gallery = _effective_media_gallery(card)
    draft_btn = (
        InlineKeyboardButton(text="✅ Уже в черновике — открыть", callback_data="draft:open")
        if is_in_draft
        else InlineKeyboardButton(text="+В черновик", callback_data=f"search:draft:{card.product_id}")
    )
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="← К результатам", callback_data="search:back")],
        [draft_btn],
        [
            InlineKeyboardButton(
                text=("Скрыть" if show_auth else "Показать") + " проверку",
                callback_data="search:toggle:auth",
            ),
            InlineKeyboardButton(
                text=("Скрыть" if show_media else "Показать") + " медиа",
                callback_data="search:toggle:media",
            ),
        ],
    ]
    if show_media and len(gallery) > 1:
        rows.append(
            [
                InlineKeyboardButton(text="◀️ Предыдущее медиа", callback_data="search:media:prev"),
                InlineKeyboardButton(text="Следующее медиа ▶️", callback_data="search:media:next"),
            ]
        )

    source_row = [
        InlineKeyboardButton(
            text=("Скрыть" if show_sources else "Показать") + " источники",
            callback_data="search:toggle:sources",
        )
    ]
    rows.append(source_row)

    link_buttons: list[InlineKeyboardButton] = []
    if card.official_url:
        link_buttons.append(InlineKeyboardButton(text="Официальный источник", url=card.official_url))
    for source in _effective_source_links(card):
        link_buttons.append(InlineKeyboardButton(text=source.label, url=source.url))

    for i in range(0, len(link_buttons), 2):
        rows.append(link_buttons[i : i + 2])

    if show_media and gallery:
        media_links: list[InlineKeyboardButton] = []
        for idx, media in enumerate(gallery, start=1):
            if media.ref.startswith("http://") or media.ref.startswith("https://"):
                media_links.append(
                    InlineKeyboardButton(text=f"{_media_type_label(media.media_kind)} {idx}", url=media.ref)
                )
            if len(media_links) >= 4:
                break
        for i in range(0, len(media_links), 2):
            rows.append(media_links[i : i + 2])

    if is_admin:
        rows.append([
            InlineKeyboardButton(
                text=("✖ Закрыть policy" if show_admin_media_controls else "🛠 Политика медиа/источников"),
                callback_data="search:toggle:admin_media",
            ),
            InlineKeyboardButton(text="🖼️ Добавить медиа", callback_data=f"admin:media:start:{card.product_id}"),
        ])
        if show_admin_media_controls:
            rows.extend([
                [
                    InlineKeyboardButton(text="Режим: только import", callback_data=f"a:p:mp:{card.product_id}:import_only"),
                    InlineKeyboardButton(text="Режим: только manual", callback_data=f"a:p:mp:{card.product_id}:manual_only"),
                ],
                [
                    InlineKeyboardButton(text="Режим: manual в приоритете", callback_data=f"a:p:mp:{card.product_id}:prefer_manual"),
                    InlineKeyboardButton(text="Режим: объединение", callback_data=f"a:p:mp:{card.product_id}:merge"),
                ],
                [
                    InlineKeyboardButton(text="Показ: none", callback_data=f"a:p:dm:{card.product_id}:n"),
                    InlineKeyboardButton(text="Показ: on_demand", callback_data=f"a:p:dm:{card.product_id}:od"),
                ],
                [
                    InlineKeyboardButton(text="Показ: cover при открытии", callback_data=f"a:p:dm:{card.product_id}:sc"),
                ],
                [
                    InlineKeyboardButton(text=f"Синк изображений: {_sync_flag_label(card.sync_images)}", callback_data=f"a:p:st:{card.product_id}:i"),
                    InlineKeyboardButton(text=f"Синк видео: {_sync_flag_label(card.sync_videos)}", callback_data=f"a:p:st:{card.product_id}:v"),
                ],
                [
                    InlineKeyboardButton(text=f"Синк источников: {_sync_flag_label(card.sync_sources)}", callback_data=f"a:p:st:{card.product_id}:s"),
                ],
            ])

    rows.append([InlineKeyboardButton(text="🏠 Главная", callback_data="nav:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_result_actions(product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Открыть", callback_data=f"search:open:{product_id}"),
                InlineKeyboardButton(text="+В черновик", callback_data=f"search:draft:{product_id}"),
            ]
        ]
    )


async def _get_draft_product_ids(
    draft_service: DraftApplicationService, telegram_user_id: int | None
) -> set[str]:
    """Return set of product_id strings currently in the user's draft."""
    if telegram_user_id is None:
        return set()
    user_id = str(telegram_user_id)
    draft = await draft_service.get_or_create_active_draft(user_id)
    return {str(item.product_id) for item in draft.items}


async def re_render_search_results(
    *,
    message: Message,
    state: FSMContext,
    draft_product_ids: set[str],
) -> bool:
    """Re-render the cached search results panel with updated draft checkmarks.

    Returns True if the panel was successfully re-rendered.
    """
    data = await state.get_data()
    panel_state = data.get(SEARCH_STATE_KEY) or {}
    items_raw = panel_state.get("items") or []
    query = panel_state.get("query")
    total = panel_state.get("total", 0)
    page = panel_state.get("page", 0)
    if not query or not items_raw:
        return False

    items = [_deserialize_item(raw) for raw in items_raw]
    rendered = _render_search_panel(query=str(query), total=int(total), page=int(page), items=items)
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=rendered,
        reply_markup=build_results_actions(
            items=items,
            page=int(page),
            total=int(total),
            draft_product_ids=draft_product_ids,
        ),
        parse_mode=ParseMode.HTML,
    )
    return True


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
