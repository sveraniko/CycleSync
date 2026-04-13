from datetime import time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.reminders import ReminderAccessError, ReminderApplicationService
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
) -> None:
    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    settings = await reminder_service.get_reminder_settings(user_id)
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=_render_settings(settings),
        reply_markup=build_settings_actions(settings.reminders_enabled),
    )


@router.callback_query(F.data == "settings:reminders:on")
async def on_reminders_on(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
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
        text=_render_settings(updated, notice="Reminders включены."),
        reply_markup=build_settings_actions(updated.reminders_enabled),
    )
    await callback.answer("Готово")


@router.callback_query(F.data == "settings:reminders:off")
async def on_reminders_off(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
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
            notice="Reminders выключены (opt-out, без breach semantics).",
        ),
        reply_markup=build_settings_actions(updated.reminders_enabled),
    )
    await callback.answer("Готово")


@router.callback_query(F.data == "settings:time:set")
async def on_set_time_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
) -> None:
    await state.set_state(ReminderSettingsState.reminder_time)
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    settings = await reminder_service.get_reminder_settings(user_id)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_settings(
            settings,
            notice="Введите reminder time в формате HH:MM (локальное время), например 09:30.",
        ),
        reply_markup=build_settings_actions(settings.reminders_enabled),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:protocol:status")
async def on_protocol_status(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    settings = await reminder_service.get_reminder_settings(user_id)
    status = await reminder_service.get_user_protocol_status(user_id)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_settings(settings, notice=_render_protocol_status(status)),
        reply_markup=build_settings_actions(settings.reminders_enabled),
    )
    await callback.answer()


@router.message(ReminderSettingsState.reminder_time)
async def on_set_time_input(
    message: Message,
    state: FSMContext,
    reminder_service: ReminderApplicationService,
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
            reply_markup=build_settings_actions(current.reminders_enabled),
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
            notice=f"Reminder time обновлено: {parsed.strftime('%H:%M')}.",
        ),
        reply_markup=build_settings_actions(updated.reminders_enabled),
    )
    await delete_user_input_message(message)


def build_settings_actions(reminders_enabled: bool) -> InlineKeyboardMarkup:
    toggle_button = InlineKeyboardButton(
        text="Turn Off" if reminders_enabled else "Turn On",
        callback_data=(
            "settings:reminders:off" if reminders_enabled else "settings:reminders:on"
        ),
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle_button],
            [
                InlineKeyboardButton(
                    text="Set reminder time", callback_data="settings:time:set"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Protocol status", callback_data="settings:protocol:status"
                )
            ],
        ]
    )


def _render_settings(settings, notice: str | None = None) -> str:
    lines = [
        "Settings / Reminder execution:",
        f"- reminders_enabled: {'on' if settings.reminders_enabled else 'off'}",
        f"- preferred_time_local: {settings.preferred_reminder_time_local.strftime('%H:%M') if settings.preferred_reminder_time_local else 'default'}",
        f"- timezone: {settings.timezone_name or 'default'}",
    ]
    if notice:
        lines.extend(["", notice])
    return "\n".join(lines)


def _render_protocol_status(status) -> str:
    if not status.has_active_protocol:
        return "Protocol status:\n- no active protocol"
    if status.summary is None:
        return "Protocol status:\n- healthy\n- no adherence actions yet"
    s = status.summary
    misses = s.skipped_count + s.expired_count
    return "\n".join(
        [
            "Protocol adherence status:",
            f"- integrity: {compact_status_label(s.integrity_state)}",
            f"- completion_rate: {format_decimal_human(s.completion_rate * 100, precision=0)}%",
            f"- misses: {misses} (skip={s.skipped_count}, expired={s.expired_count})",
            f"- reason: {compact_status_label(s.integrity_reason_code)}",
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


def _resolve_user_id(telegram_user_id: int | None) -> str:
    if telegram_user_id is None:
        return "anonymous"
    return f"tg:{telegram_user_id}"
