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
        text=_render_admin_panel(admin_config, _effective_debug_enabled(admin_config, debug_enabled), admin_ids),
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
    commerce_enabled = admin_config.commerce_enabled if admin_config else False
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_admin_panel(admin_config, _effective_debug_enabled(admin_config, debug_enabled), admin_ids),
        reply_markup=_build_admin_keyboard(admin_config),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Коммерческий режим включён" if commerce_enabled else "Коммерческий режим выключен")


@router.callback_query(F.data == "admin:debug:toggle")
async def on_debug_toggle(
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
        admin_config.debug_enabled = not admin_config.debug_enabled
    effective_debug = _effective_debug_enabled(admin_config, debug_enabled)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_admin_panel(admin_config, effective_debug, admin_ids),
        reply_markup=_build_admin_keyboard(admin_config),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Debug режим включён" if effective_debug else "Debug режим выключен")


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
    await delete_user_input_message(message)
    await state.set_state(None)
    await state.update_data(admin_media_product_id=None)


def _render_admin_panel(
    admin_config: AdminRuntimeConfig | None,
    debug_enabled: bool,
    admin_ids: tuple[int, ...] | None,
) -> str:
    commerce_enabled = admin_config.commerce_enabled if admin_config else False
    ids_label = ", ".join(str(i) for i in (admin_ids or [])) or "—"
    runtime_block = _render_runtime_status_block(admin_config, debug_enabled)
    commerce_block = (
        "<b>💳 Commerce controls</b>\n"
        f"• commerce_enabled: <b>{'ON' if commerce_enabled else 'OFF'}</b>\n"
        f"• User checkout/demo entry: <b>{'доступен' if commerce_enabled else 'скрыт'}</b>\n"
        "• Access key activation: <b>всегда доступна</b> (не зависит от checkout)\n"
        f"• Что это меняет: {'видны checkout-энтрипойнты и команды оплаты' if commerce_enabled else 'checkout и коммерческие кнопки скрыты/заблокированы'}"
    )
    debug_block = (
        "<b>🧪 Debug controls</b>\n"
        f"• debug_enabled: <b>{'ON' if debug_enabled else 'OFF'}</b>\n"
        f"• Debug checkout actions: <b>{'активны только для админа' if debug_enabled else 'выключены'}</b>\n"
        f"• Demo/test paths: <b>{'доступны администратору' if debug_enabled else 'недоступны'}</b>"
    )
    nav_block = (
        "<b>🧭 Навигация</b>\n"
        "• Runtime status — этот экран\n"
        "• Catalog sync — импорт/синк каталога\n"
        "• Media/source policy — из карточек поиска (admin controls)\n"
        "• Access/commerce entrypoints — в Settings"
    )
    return (
        "<b>🔧 Панель администратора</b>\n\n"
        f"{runtime_block}\n\n"
        f"{commerce_block}\n\n"
        f"{debug_block}\n\n"
        f"<b>👤 Admin IDs:</b> <code>{ids_label}</code>\n\n"
        f"{nav_block}\n\n"
        "<i>Изменения runtime-флагов применяются сразу в текущем процессе бота.</i>"
    )


def _render_runtime_status_block(admin_config: AdminRuntimeConfig | None, debug_enabled: bool) -> str:
    commerce = admin_config.commerce_enabled if admin_config else False
    pulse_version = admin_config.pulse_engine_version if admin_config else "—"
    app_env = admin_config.app_env if admin_config else "—"
    catalog_status = _render_runtime_catalog_status(admin_config.last_catalog_operation if admin_config else None)
    return (
        "<b>📡 Runtime status</b>\n"
        f"• commerce_enabled: <b>{'ON' if commerce else 'OFF'}</b>\n"
        f"• debug_enabled: <b>{'ON' if debug_enabled else 'OFF'}</b>\n"
        f"• pulse_engine_version: <code>{pulse_version}</code>\n"
        f"• launch_mode: <code>{app_env}</code>\n"
        f"• catalog_sync: {catalog_status}"
    )


def _render_runtime_catalog_status(last_operation: dict[str, object] | None) -> str:
    if not last_operation:
        return "<i>ещё не запускали</i>"
    status = str(last_operation.get("status", "unknown"))
    ts = str(last_operation.get("timestamp", "—"))
    source = str(last_operation.get("source_type", "—"))
    return f"<b>{status}</b> ({source}, {ts})"


def _effective_debug_enabled(admin_config: AdminRuntimeConfig | None, debug_enabled: bool) -> bool:
    if admin_config is None:
        return debug_enabled
    return admin_config.debug_enabled


def _build_admin_keyboard(admin_config: AdminRuntimeConfig | None) -> InlineKeyboardMarkup:
    commerce_enabled = admin_config.commerce_enabled if admin_config else False
    debug_enabled = admin_config.debug_enabled if admin_config else False
    commerce_toggle_text = "💳 Выключить commerce" if commerce_enabled else "💳 Включить commerce"
    debug_toggle_text = "🧪 Выключить debug" if debug_enabled else "🧪 Включить debug"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=commerce_toggle_text, callback_data="admin:commerce:toggle")],
            [InlineKeyboardButton(text=debug_toggle_text, callback_data="admin:debug:toggle")],
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
