from __future__ import annotations

from uuid import UUID

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.catalog.admin_sync import CatalogAdminRunSummary, CatalogAdminSyncService
from app.application.search.service import SearchApplicationService
from app.bots.core.admin_config import AdminRuntimeConfig
from app.bots.core.flow import delete_user_input_message, safe_edit_or_send
from app.bots.core.permissions import is_admin_user

router = Router(name="admin")


class AdminMediaUploadState(StatesGroup):
    waiting_input = State()


def _gate(user_id: int | None, admin_ids: tuple[int, ...] | None) -> bool:
    return is_admin_user(user_id, admin_ids)


# ── Admin panel ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:panel")
async def on_admin_panel(
    callback: CallbackQuery,
    state: FSMContext,
    admin_ids: tuple[int, ...] | None = None,
    admin_config: AdminRuntimeConfig | None = None,
    debug_enabled: bool = False,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not _gate(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_admin_panel(admin_config, debug_enabled, admin_ids),
        reply_markup=_build_admin_keyboard(admin_config),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "admin:commerce:toggle")
async def on_commerce_toggle(
    callback: CallbackQuery,
    state: FSMContext,
    admin_ids: tuple[int, ...] | None = None,
    admin_config: AdminRuntimeConfig | None = None,
    debug_enabled: bool = False,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not _gate(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if admin_config is not None:
        admin_config.commerce_enabled = not admin_config.commerce_enabled
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_admin_panel(admin_config, debug_enabled, admin_ids),
        reply_markup=_build_admin_keyboard(admin_config),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Изменено")


@router.callback_query(F.data == "admin:catalog:panel")
async def on_catalog_sync_panel(
    callback: CallbackQuery,
    state: FSMContext,
    admin_ids: tuple[int, ...] | None = None,
    admin_config: AdminRuntimeConfig | None = None,
    catalog_admin_service: CatalogAdminSyncService | None = None,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not _gate(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_catalog_sync_panel(catalog_admin_service, admin_config),
        reply_markup=_build_catalog_sync_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "admin:catalog:xlsx:validate")
async def on_catalog_xlsx_validate(
    callback: CallbackQuery,
    state: FSMContext,
    admin_ids: tuple[int, ...] | None = None,
    admin_config: AdminRuntimeConfig | None = None,
    catalog_admin_service: CatalogAdminSyncService | None = None,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not _gate(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if catalog_admin_service is None:
        await callback.answer("Catalog sync service недоступен", show_alert=True)
        return
    summary = catalog_admin_service.validate_workbook()
    _persist_last_catalog_operation(admin_config, summary)
    await _show_catalog_action_result(callback, state, summary)


@router.callback_query(F.data == "admin:catalog:xlsx:apply")
async def on_catalog_xlsx_apply(
    callback: CallbackQuery,
    state: FSMContext,
    admin_ids: tuple[int, ...] | None = None,
    admin_config: AdminRuntimeConfig | None = None,
    catalog_admin_service: CatalogAdminSyncService | None = None,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not _gate(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if catalog_admin_service is None:
        await callback.answer("Catalog sync service недоступен", show_alert=True)
        return
    summary = await catalog_admin_service.run_xlsx_ingest_apply()
    _persist_last_catalog_operation(admin_config, summary)
    await _show_catalog_action_result(callback, state, summary)


@router.callback_query(F.data == "admin:catalog:gsheets:apply")
async def on_catalog_gsheets_apply(
    callback: CallbackQuery,
    state: FSMContext,
    admin_ids: tuple[int, ...] | None = None,
    admin_config: AdminRuntimeConfig | None = None,
    catalog_admin_service: CatalogAdminSyncService | None = None,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not _gate(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if catalog_admin_service is None:
        await callback.answer("Catalog sync service недоступен", show_alert=True)
        return
    summary = await catalog_admin_service.run_gsheets_sync_apply()
    _persist_last_catalog_operation(admin_config, summary)
    await _show_catalog_action_result(callback, state, summary)


@router.callback_query(F.data == "admin:catalog:search:rebuild")
async def on_catalog_search_rebuild(
    callback: CallbackQuery,
    state: FSMContext,
    admin_ids: tuple[int, ...] | None = None,
    admin_config: AdminRuntimeConfig | None = None,
    catalog_admin_service: CatalogAdminSyncService | None = None,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not _gate(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if catalog_admin_service is None:
        await callback.answer("Catalog sync service недоступен", show_alert=True)
        return
    summary = await catalog_admin_service.rebuild_search()
    _persist_last_catalog_operation(admin_config, summary)
    await _show_catalog_action_result(callback, state, summary)


# ── Media upload ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin:media:start:"))
async def on_media_upload_start(
    callback: CallbackQuery,
    state: FSMContext,
    admin_ids: tuple[int, ...] | None = None,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not _gate(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    product_id = callback.data.split(":", 3)[3]
    await state.update_data(admin_media_product_id=product_id)
    await state.set_state(AdminMediaUploadState.waiting_input)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=(
            "<b>🖼️ Загрузка медиа</b>\n\n"
            "Отправь фото из галереи <b>или</b> вставь URL (http/https).\n\n"
            "Нажми Отмена для выхода."
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="✗ Отмена", callback_data="admin:media:cancel")]]
        ),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "admin:media:cancel")
async def on_media_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    admin_ids: tuple[int, ...] | None = None,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    if not _gate(uid, admin_ids):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text="Отмена. Вернись к карточке или открой главную.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🏠 Главная", callback_data="nav:home")]]
        ),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(AdminMediaUploadState.waiting_input)
async def on_media_input(
    message: Message,
    state: FSMContext,
    search_service: SearchApplicationService,
    admin_ids: tuple[int, ...] | None = None,
) -> None:
    uid = message.from_user.id if message.from_user else None
    if not _gate(uid, admin_ids):
        await delete_user_input_message(message)
        return

    data = await state.get_data()
    product_id_str = data.get("admin_media_product_id")
    if not product_id_str:
        await state.clear()
        await delete_user_input_message(message)
        return

    product_id = UUID(product_id_str)

    if message.photo:
        file_id = message.photo[-1].file_id
        ref_url = f"tg-photo:{file_id}"
        media_kind = "tg_photo"
    elif message.video:
        file_id = message.video.file_id
        ref_url = f"tg-video:{file_id}"
        media_kind = "tg_video"
    elif message.animation:
        file_id = message.animation.file_id
        ref_url = f"tg-animation:{file_id}"
        media_kind = "tg_animation"
    elif message.text and (
        message.text.startswith("http://") or message.text.startswith("https://")
    ):
        ref_url = message.text.strip()
        media_kind = "external"
    else:
        await safe_edit_or_send(
            state=state,
            source_message=message,
            text="Нужно фото, видео, GIF или URL (http/https). Попробуй ещё или нажми Отмена.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="✗ Отмена", callback_data="admin:media:cancel")]]
            ),
            parse_mode=ParseMode.HTML,
        )
        await delete_user_input_message(message)
        return

    added = await search_service.admin_add_media_ref(
        product_id=product_id, ref_url=ref_url, media_kind=media_kind
    )

    notice = "✅ Медиа добавлено в карточку." if added else "⚠️ Такой ref уже существует, дубликат не добавлен."

    # Edit the container FIRST (while state data still has ui_container_message_id),
    # then clean up FSM state. This prevents orphaned panel spam.
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=notice,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Открыть карточку снова", callback_data=f"search:open:{product_id}")],
                [InlineKeyboardButton(text="🏠 Главная", callback_data="nav:home")],
            ]
        ),
        parse_mode=ParseMode.HTML,
    )
    await delete_user_input_message(message)  # delete the user's photo/video/text
    # Clean up only the media-upload FSM keys, keep ui_container_message_id intact
    await state.set_state(None)
    await state.update_data(admin_media_product_id=None)


# ── Rendering ──────────────────────────────────────────────────────────────────

def _render_admin_panel(
    admin_config: AdminRuntimeConfig | None,
    debug_enabled: bool,
    admin_ids: tuple[int, ...] | None,
) -> str:
    commerce = admin_config.commerce_enabled if admin_config else False
    commerce_label = "✅ Включён" if commerce else "❌ Выключен"
    debug_label = "✅ Включён" if debug_enabled else "❌ Выключен"
    ids_label = ", ".join(str(i) for i in (admin_ids or [])) or "—"
    return (
        "<b>🔧 Панель администратора</b>\n\n"
        f"Коммерческий слой: <b>{commerce_label}</b>\n"
        f"Debug режим: <b>{debug_label}</b>\n"
        f"Admin IDs: <code>{ids_label}</code>\n\n"
        "<i>Изменения действуют до перезапуска бота.</i>"
    )


def _build_admin_keyboard(admin_config: AdminRuntimeConfig | None) -> InlineKeyboardMarkup:
    commerce_enabled = admin_config.commerce_enabled if admin_config else False
    toggle_text = "Выключить коммерцию" if commerce_enabled else "Включить коммерцию"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="admin:commerce:toggle")],
            [InlineKeyboardButton(text="📦 Catalog sync", callback_data="admin:catalog:panel")],
            [InlineKeyboardButton(text="🏠 Главная", callback_data="nav:home")],
        ]
    )


def _build_catalog_sync_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Validate workbook (dry-run)", callback_data="admin:catalog:xlsx:validate")],
            [InlineKeyboardButton(text="🚀 Run XLSX ingest (apply)", callback_data="admin:catalog:xlsx:apply")],
            [InlineKeyboardButton(text="☁️ Run Google Sheets sync", callback_data="admin:catalog:gsheets:apply")],
            [InlineKeyboardButton(text="🔎 Rebuild search", callback_data="admin:catalog:search:rebuild")],
            [InlineKeyboardButton(text="↩️ Назад в админку", callback_data="admin:panel")],
        ]
    )


def _render_catalog_sync_panel(
    catalog_admin_service: CatalogAdminSyncService | None,
    admin_config: AdminRuntimeConfig | None,
) -> str:
    xlsx_path = catalog_admin_service.get_default_workbook_path() if catalog_admin_service else "—"
    gsheets_ok, gsheets_note = (
        catalog_admin_service.gsheets_is_configured() if catalog_admin_service else (False, "Catalog sync service недоступен.")
    )
    gsheets_label = "✅ Готово" if gsheets_ok else "⚠️ Не настроено"
    last_run = _render_last_catalog_run(admin_config.last_catalog_operation if admin_config else None)
    return (
        "<b>📦 Catalog sync</b>\n\n"
        "<b>Режимы:</b>\n"
        "• Validate workbook (dry-run) — без записи в БД\n"
        "• Run XLSX ingest (apply) — применяет изменения в каталог\n"
        "• Run Google Sheets sync — синхронизация из Google Sheets\n"
        "• Rebuild search — обновляет поисковую проекцию\n\n"
        f"Workbook (default): <code>{xlsx_path}</code>\n"
        f"Google Sheets: <b>{gsheets_label}</b>\n"
        f"<i>{gsheets_note}</i>\n\n"
        f"{last_run}"
    )


def _persist_last_catalog_operation(
    admin_config: AdminRuntimeConfig | None,
    summary: CatalogAdminRunSummary,
) -> None:
    if admin_config is None:
        return
    admin_config.last_catalog_operation = {
        "source_type": summary.source_type,
        "mode": summary.mode,
        "status": summary.status,
        "timestamp": summary.timestamp,
        "message": summary.message,
        "counts": dict(summary.counts),
    }


def _render_last_catalog_run(last_operation: dict[str, object] | None) -> str:
    if not last_operation:
        return "<b>Last run:</b> <i>ещё не запускали</i>"
    counts = last_operation.get("counts")
    counts_lines = []
    if isinstance(counts, dict):
        for key, value in counts.items():
            counts_lines.append(f"• {key}: <b>{value}</b>")
    counts_block = "\n".join(counts_lines) if counts_lines else "• без счётчиков"
    return (
        "<b>Last run:</b>\n"
        f"• source: <code>{last_operation.get('source_type', '—')}</code>\n"
        f"• mode: <code>{last_operation.get('mode', '—')}</code>\n"
        f"• status: <b>{last_operation.get('status', '—')}</b>\n"
        f"• timestamp: <code>{last_operation.get('timestamp', '—')}</code>\n"
        f"• note: {last_operation.get('message', '—')}\n"
        f"{counts_block}"
    )


def _render_catalog_result(summary: CatalogAdminRunSummary) -> str:
    counts = "\n".join(f"• {key}: <b>{value}</b>" for key, value in summary.counts.items()) or "• без счётчиков"
    return (
        "<b>📦 Catalog sync result</b>\n\n"
        f"source: <code>{summary.source_type}</code>\n"
        f"mode: <code>{summary.mode}</code>\n"
        f"status: <b>{summary.status}</b>\n"
        f"timestamp: <code>{summary.timestamp}</code>\n"
        f"message: {summary.message}\n\n"
        "<b>Summary:</b>\n"
        f"{counts}\n\n"
        "<i>При ошибке смотри логи приложения для деталей.</i>"
    )


async def _show_catalog_action_result(
    callback: CallbackQuery,
    state: FSMContext,
    summary: CatalogAdminRunSummary,
) -> None:
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_catalog_result(summary),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Back to Catalog sync", callback_data="admin:catalog:panel")],
                [InlineKeyboardButton(text="🏠 Главная", callback_data="nav:home")],
            ]
        ),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Готово")
