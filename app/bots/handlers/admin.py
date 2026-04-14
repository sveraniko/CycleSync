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
    await callback.answer("Режим отладки включён" if effective_debug else "Режим отладки выключен")


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
        await callback.answer("Сервис синхронизации каталога недоступен", show_alert=True)
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
        await callback.answer("Сервис синхронизации каталога недоступен", show_alert=True)
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
        await callback.answer("Сервис синхронизации каталога недоступен", show_alert=True)
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
        await callback.answer("Сервис синхронизации каталога недоступен", show_alert=True)
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

    notice = "✅ Медиа добавлено в карточку." if added else "⚠️ Такая ссылка уже существует, дубликат не добавлен."

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
        "<b>💳 Коммерция и доступ</b>\n"
        f"• Коммерческий режим: <b>{'ВКЛ' if commerce_enabled else 'ВЫКЛ'}</b>\n"
        f"• Экран оплаты: <b>{'доступен' if commerce_enabled else 'скрыт'}</b>\n"
        "• Активация ключа: <b>всегда доступна</b> (не зависит от оплаты)\n"
        f"• Что меняется: {'появляются кнопки оплаты и демо-оплаты' if commerce_enabled else 'кнопки оплаты скрыты и недоступны'}"
    )
    debug_block = (
        "<b>🧪 Отладка</b>\n"
        f"• Отладка: <b>{'ВКЛ' if debug_enabled else 'ВЫКЛ'}</b>\n"
        f"• Тестовые действия оплаты: <b>{'только для админа' if debug_enabled else 'выключены'}</b>\n"
        f"• Демо-сценарии: <b>{'доступны администратору' if debug_enabled else 'недоступны'}</b>"
    )
    nav_block = (
        "<b>🧭 Навигация</b>\n"
        "• Состояние рантайма — этот экран\n"
        "• Синхронизация каталога — импорт и обновление каталога\n"
        "• Политика медиа/источников — в карточках поиска (для админа)\n"
        "• Входы в доступ и оплату — в «Настройках»"
    )
    return (
        "<b>🔧 Панель администратора</b>\n\n"
        f"{runtime_block}\n\n"
        f"{commerce_block}\n\n"
        f"{debug_block}\n\n"
        f"<b>👤 ID администраторов:</b> <code>{ids_label}</code>\n\n"
        f"{nav_block}\n\n"
        "<i>Изменения флагов применяются сразу в текущем процессе бота.</i>"
    )


def _render_runtime_status_block(admin_config: AdminRuntimeConfig | None, debug_enabled: bool) -> str:
    commerce = admin_config.commerce_enabled if admin_config else False
    pulse_version = admin_config.pulse_engine_version if admin_config else "—"
    app_env = admin_config.app_env if admin_config else "—"
    catalog_status = _render_runtime_catalog_status(admin_config.last_catalog_operation if admin_config else None)
    return (
        "<b>📡 Состояние рантайма</b>\n"
        f"• Коммерческий режим: <b>{'ВКЛ' if commerce else 'ВЫКЛ'}</b>\n"
        f"• Отладка: <b>{'ВКЛ' if debug_enabled else 'ВЫКЛ'}</b>\n"
        f"• Версия Pulse Engine: <code>{pulse_version}</code>\n"
        f"• Контур запуска: <code>{app_env}</code>\n"
        f"• Синхронизация каталога: {catalog_status}"
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
    commerce_toggle_text = "💳 Выключить коммерческий режим" if commerce_enabled else "💳 Включить коммерческий режим"
    debug_toggle_text = "🧪 Выключить отладку" if debug_enabled else "🧪 Включить отладку"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=commerce_toggle_text, callback_data="admin:commerce:toggle")],
            [InlineKeyboardButton(text=debug_toggle_text, callback_data="admin:debug:toggle")],
            [InlineKeyboardButton(text="📦 Синхронизация каталога", callback_data="admin:catalog:panel")],
            [InlineKeyboardButton(text="🏠 Главная", callback_data="nav:home")],
        ]
    )


def _build_catalog_sync_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Проверить файл (dry-run)", callback_data="admin:catalog:xlsx:validate")],
            [InlineKeyboardButton(text="🚀 Применить XLSX импорт", callback_data="admin:catalog:xlsx:apply")],
            [InlineKeyboardButton(text="☁️ Синхронизировать Google Sheets", callback_data="admin:catalog:gsheets:apply")],
            [InlineKeyboardButton(text="🔎 Пересобрать поиск", callback_data="admin:catalog:search:rebuild")],
            [InlineKeyboardButton(text="↩️ Назад в админку", callback_data="admin:panel")],
        ]
    )


def _render_catalog_sync_panel(
    catalog_admin_service: CatalogAdminSyncService | None,
    admin_config: AdminRuntimeConfig | None,
) -> str:
    xlsx_path = catalog_admin_service.get_default_workbook_path() if catalog_admin_service else "—"
    gsheets_ok, gsheets_note = (
        catalog_admin_service.gsheets_is_configured() if catalog_admin_service else (False, "Сервис синхронизации каталога недоступен.")
    )
    gsheets_label = "✅ Готово" if gsheets_ok else "⚠️ Не настроено"
    last_run = _render_last_catalog_run(admin_config.last_catalog_operation if admin_config else None)
    return (
        "<b>📦 Синхронизация каталога</b>\n\n"
        "<b>Режимы:</b>\n"
        "• Проверка файла (dry-run) — без записи в БД\n"
        "• Применить XLSX-импорт — вносит изменения в каталог\n"
        "• Синхронизировать Google Sheets — загрузка из таблиц\n"
        "• Пересобрать поиск — обновляет поисковую проекцию\n\n"
        f"Файл по умолчанию: <code>{xlsx_path}</code>\n"
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
        return "<b>Последний запуск:</b> <i>ещё не запускали</i>"
    counts = last_operation.get("counts")
    counts_lines = []
    if isinstance(counts, dict):
        for key, value in counts.items():
            counts_lines.append(f"• {key}: <b>{value}</b>")
    counts_block = "\n".join(counts_lines) if counts_lines else "• без счётчиков"
    return (
        "<b>Последний запуск:</b>\n"
        f"• Источник: <code>{last_operation.get('source_type', '—')}</code>\n"
        f"• Режим: <code>{last_operation.get('mode', '—')}</code>\n"
        f"• Статус: <b>{last_operation.get('status', '—')}</b>\n"
        f"• Время: <code>{last_operation.get('timestamp', '—')}</code>\n"
        f"• Примечание: {last_operation.get('message', '—')}\n"
        f"{counts_block}"
    )


def _render_catalog_result(summary: CatalogAdminRunSummary) -> str:
    counts = "\n".join(f"• {key}: <b>{value}</b>" for key, value in summary.counts.items()) or "• без счётчиков"
    return (
        "<b>📦 Результат синхронизации</b>\n\n"
        f"Источник: <code>{summary.source_type}</code>\n"
        f"Режим: <code>{summary.mode}</code>\n"
        f"Статус: <b>{summary.status}</b>\n"
        f"Время: <code>{summary.timestamp}</code>\n"
        f"Сообщение: {summary.message}\n\n"
        "<b>Сводка:</b>\n"
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
                [InlineKeyboardButton(text="⬅️ К синхронизации каталога", callback_data="admin:catalog:panel")],
                [InlineKeyboardButton(text="🏠 Главная", callback_data="nav:home")],
            ]
        ),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Готово")
