from datetime import time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.reminders import ReminderApplicationService

router = Router(name="settings")


class ReminderSettingsState(StatesGroup):
    reminder_time = State()


@router.message(F.text.func(lambda value: (value or "").strip().lower() == "settings"))
async def settings_entrypoint(
    message: Message, reminder_service: ReminderApplicationService
) -> None:
    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    settings = await reminder_service.get_reminder_settings(user_id)
    await message.answer(
        _render_settings(settings),
        reply_markup=build_settings_actions(settings.reminders_enabled),
    )


@router.callback_query(F.data == "settings:reminders:on")
async def on_reminders_on(
    callback: CallbackQuery, reminder_service: ReminderApplicationService
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    current = await reminder_service.get_reminder_settings(user_id)
    updated = await reminder_service.update_reminder_settings(
        user_id=user_id,
        reminders_enabled=True,
        preferred_reminder_time_local=current.preferred_reminder_time_local,
        timezone_name=current.timezone_name,
    )
    await callback.message.answer("Reminders включены.")
    await callback.message.answer(
        _render_settings(updated),
        reply_markup=build_settings_actions(updated.reminders_enabled),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:reminders:off")
async def on_reminders_off(
    callback: CallbackQuery, reminder_service: ReminderApplicationService
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    current = await reminder_service.get_reminder_settings(user_id)
    updated = await reminder_service.update_reminder_settings(
        user_id=user_id,
        reminders_enabled=False,
        preferred_reminder_time_local=current.preferred_reminder_time_local,
        timezone_name=current.timezone_name,
    )
    await callback.message.answer(
        "Reminders выключены (opt-out, без breach semantics)."
    )
    await callback.message.answer(
        _render_settings(updated),
        reply_markup=build_settings_actions(updated.reminders_enabled),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:time:set")
async def on_set_time_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ReminderSettingsState.reminder_time)
    await callback.message.answer(
        "Введите reminder time в формате HH:MM (локальное время), например `09:30`."
    )
    await callback.answer()


@router.message(ReminderSettingsState.reminder_time)
async def on_set_time_input(
    message: Message, state: FSMContext, reminder_service: ReminderApplicationService
) -> None:
    parsed = _parse_time(message.text)
    if parsed is None:
        await message.answer("Неверный формат. Используйте HH:MM, например `08:45`.")
        return

    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    current = await reminder_service.get_reminder_settings(user_id)
    updated = await reminder_service.update_reminder_settings(
        user_id=user_id,
        reminders_enabled=current.reminders_enabled,
        preferred_reminder_time_local=parsed,
        timezone_name=current.timezone_name,
    )
    await state.clear()
    await message.answer(f"Reminder time обновлено: {parsed.strftime('%H:%M')}.")
    await message.answer(
        _render_settings(updated),
        reply_markup=build_settings_actions(updated.reminders_enabled),
    )


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
        ]
    )


def _render_settings(settings) -> str:
    return "\n".join(
        [
            "Settings / Reminder execution:",
            f"- reminders_enabled: {'on' if settings.reminders_enabled else 'off'}",
            f"- preferred_time_local: {settings.preferred_reminder_time_local.strftime('%H:%M') if settings.preferred_reminder_time_local else 'default'}",
            f"- timezone: {settings.timezone_name or 'default'}",
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
