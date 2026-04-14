from datetime import time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.reminders import ReminderAccessError, ReminderApplicationService
from app.bots.core.admin_config import AdminRuntimeConfig
from app.bots.core.flow import delete_user_input_message, safe_edit_or_send
from app.bots.core.formatting import compact_status_label, format_decimal_human

router = Router(name="settings")


class ReminderSettingsState(StatesGroup):
    reminder_time = State()


@router.message(F.text.func(lambda value: (value or "").strip().lower() == "settings"))
async def settings_entrypoint(
    message: Message,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
    admin_config: AdminRuntimeConfig | None = None,
) -> None:
    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    settings = await reminder_service.get_reminder_settings(user_id)
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=_render_settings(settings),
        reply_markup=build_settings_actions(settings.reminders_enabled, commerce_enabled=_is_commerce_enabled(admin_config)),
    )


@router.callback_query(F.data == "settings:open")
async def on_settings_open(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
    admin_config: AdminRuntimeConfig | None = None,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    settings = await reminder_service.get_reminder_settings(user_id)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_settings(settings),
        reply_markup=build_settings_actions(settings.reminders_enabled, commerce_enabled=_is_commerce_enabled(admin_config)),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:reminders:on")
async def on_reminders_on(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
    admin_config: AdminRuntimeConfig | None = None,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    current = await reminder_service.get_reminder_settings(user_id)
    try:
        updated = await reminder_service.update_reminder_settings(
            user_id=user_id,
            reminders_enabled=True,
            preferred_reminder_time_local=current.preferred_reminder_time_local,
            timezone_name=current.timezone_name,
        )
    except ReminderAccessError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_settings(updated, notice="Напоминания включены."),
        reply_markup=build_settings_actions(updated.reminders_enabled, commerce_enabled=_is_commerce_enabled(admin_config)),
    )
    await callback.answer("Готово")


@router.callback_query(F.data == "settings:reminders:off")
async def on_reminders_off(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
    admin_config: AdminRuntimeConfig | None = None,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    current = await reminder_service.get_reminder_settings(user_id)
    updated = await reminder_service.update_reminder_settings(
        user_id=user_id,
        reminders_enabled=False,
        preferred_reminder_time_local=current.preferred_reminder_time_local,
        timezone_name=current.timezone_name,
    )
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_settings(
            updated,
            notice="Напоминания выключены.",
        ),
        reply_markup=build_settings_actions(updated.reminders_enabled, commerce_enabled=_is_commerce_enabled(admin_config)),
    )
    await callback.answer("Готово")


@router.callback_query(F.data == "settings:time:set")
async def on_set_time_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
    admin_config: AdminRuntimeConfig | None = None,
) -> None:
    await state.set_state(ReminderSettingsState.reminder_time)
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    settings = await reminder_service.get_reminder_settings(user_id)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_settings(
            settings,
            notice="Введите время напоминания в формате HH:MM, например 09:30.",
        ),
        reply_markup=build_settings_actions(settings.reminders_enabled, commerce_enabled=_is_commerce_enabled(admin_config)),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:protocol:status")
async def on_protocol_status(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
    admin_config: AdminRuntimeConfig | None = None,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    settings = await reminder_service.get_reminder_settings(user_id)
    status = await reminder_service.get_user_protocol_status(user_id)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_settings(settings, notice=_render_protocol_status(status)),
        reply_markup=build_settings_actions(settings.reminders_enabled, commerce_enabled=_is_commerce_enabled(admin_config)),
    )
    await callback.answer()


@router.message(ReminderSettingsState.reminder_time)
async def on_set_time_input(
    message: Message,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
    admin_config: AdminRuntimeConfig | None = None,
) -> None:
    parsed = _parse_time(message.text)
    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)

    if parsed is None:
        current = await reminder_service.get_reminder_settings(user_id)
        await safe_edit_or_send(
            state=state,
            source_message=message,
            text=_render_settings(
                current,
                notice="Неверный формат. Используйте HH:MM, например 08:45.",
            ),
            reply_markup=build_settings_actions(current.reminders_enabled, commerce_enabled=_is_commerce_enabled(admin_config)),
        )
        await delete_user_input_message(message)
        return

    current = await reminder_service.get_reminder_settings(user_id)
    updated = await reminder_service.update_reminder_settings(
        user_id=user_id,
        reminders_enabled=current.reminders_enabled,
        preferred_reminder_time_local=parsed,
        timezone_name=current.timezone_name,
    )
    await state.clear()
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=_render_settings(
            updated,
            notice=f"Время напоминания обновлено: {parsed.strftime('%H:%M')}.",
        ),
        reply_markup=build_settings_actions(updated.reminders_enabled, commerce_enabled=_is_commerce_enabled(admin_config)),
    )
    await delete_user_input_message(message)


def build_settings_actions(reminders_enabled: bool, *, commerce_enabled: bool = False) -> InlineKeyboardMarkup:
    toggle_button = InlineKeyboardButton(
        text="🔕 Выключить напоминания" if reminders_enabled else "🔔 Включить напоминания",
        callback_data=(
            "settings:reminders:off" if reminders_enabled else "settings:reminders:on"
        ),
    )
    rows = [
        [toggle_button],
        [InlineKeyboardButton(text="⏰ Время напоминания", callback_data="settings:time:set")],
        [InlineKeyboardButton(text="📋 Статус протокола", callback_data="settings:protocol:status")],
        [InlineKeyboardButton(text="🔐 Активировать ключ", callback_data="access:activate:start")],
    ]
    if commerce_enabled:
        rows.append([InlineKeyboardButton(text="🧾 Оплата доступа", callback_data="checkout:demo:start")])
    rows.append([InlineKeyboardButton(text="🏠 Главная", callback_data="nav:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _render_settings(settings, notice: str | None = None) -> str:
    lines = [
        "⚙️ Настройки напоминаний",
        f"• Напоминания: {'✅ включены' if settings.reminders_enabled else '❌ выключены'}",
        f"• Время: {settings.preferred_reminder_time_local.strftime('%H:%M') if settings.preferred_reminder_time_local else 'по умолчанию'}",
        f"• Часовой пояс: {settings.timezone_name or 'по умолчанию'}",
    ]
    if notice:
        lines.extend(["", notice])
    return "\n".join(lines)


def _render_protocol_status(status) -> str:
    if not status.has_active_protocol:
        return "Статус протокола:\n• активный протокол не найден"
    if status.summary is None:
        return "Статус протокола:\n• состояние стабильное\n• действий по соблюдению пока нет"
    s = status.summary
    misses = s.skipped_count + s.expired_count
    return "\n".join(
        [
            "Соблюдение протокола:",
            f"• Целостность: {compact_status_label(s.integrity_state)}",
            f"• Выполнение: {format_decimal_human(s.completion_rate * 100, precision=0)}%",
            f"• Пропуски: {misses} (пропущено: {s.skipped_count}, просрочено: {s.expired_count})",
            f"• Причина: {compact_status_label(s.integrity_reason_code)}",
        ]
    )


def _parse_time(raw: str | None) -> time | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        hh, mm = raw.split(":", 1)
        hour = int(hh)
        minute = int(mm)
    except (ValueError, TypeError):
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def _is_commerce_enabled(admin_config: AdminRuntimeConfig | None) -> bool:
    if admin_config is None:
        return False
    return admin_config.commerce_enabled


def _resolve_user_id(telegram_user_id: int | None) -> str:
    if telegram_user_id is None:
        return "anonymous"
    return f"tg:{telegram_user_id}"
