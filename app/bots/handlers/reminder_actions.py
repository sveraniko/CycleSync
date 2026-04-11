from uuid import UUID

from aiogram import F, Router
from aiogram.types.callback_query import CallbackQuery

from app.application.reminders import ReminderApplicationService
from app.infrastructure.reminders import TelegramReminderDeliveryGateway

router = Router(name="reminder_actions")


@router.callback_query(F.data.startswith("reminder:"))
async def on_reminder_action(
    callback: CallbackQuery, reminder_service: ReminderApplicationService
) -> None:
    raw = callback.data or ""
    parts = raw.split(":")
    if len(parts) != 3:
        await callback.answer("Invalid reminder action", show_alert=False)
        return

    _, reminder_id_raw, action_code = parts
    if action_code not in {"done", "snooze", "skip"}:
        await callback.answer("Unsupported action", show_alert=False)
        return

    try:
        reminder_id = UUID(reminder_id_raw)
    except ValueError:
        await callback.answer("Bad reminder id", show_alert=False)
        return

    gateway = TelegramReminderDeliveryGateway(callback.bot)
    result = await reminder_service.handle_reminder_action(
        reminder_id=reminder_id,
        action_code=action_code,
        delivery_gateway=gateway,
    )
    suffix = "(already processed)" if result.idempotent else ""
    await callback.answer(
        f"Reminder {result.status} {suffix}".strip(), show_alert=False
    )
