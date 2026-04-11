from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.reminders.schemas import SentMessageRef
from app.application.reminders.service import ReminderDeliveryGateway


class TelegramReminderDeliveryGateway(ReminderDeliveryGateway):
    def __init__(self, bot):
        self.bot = bot

    async def send_reminder(
        self,
        *,
        user_id: str,
        text: str,
        callback_prefix: str,
    ) -> SentMessageRef:
        chat_id = _chat_id_from_user_id(user_id)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Done", callback_data=f"{callback_prefix}:done"
                    ),
                    InlineKeyboardButton(
                        text="Snooze", callback_data=f"{callback_prefix}:snooze"
                    ),
                    InlineKeyboardButton(
                        text="Skip", callback_data=f"{callback_prefix}:skip"
                    ),
                ]
            ]
        )
        msg = await self.bot.send_message(
            chat_id=chat_id, text=text, reply_markup=keyboard
        )
        return SentMessageRef(chat_id=str(msg.chat.id), message_id=str(msg.message_id))

    async def cleanup_message(
        self, *, chat_id: str, message_id: str, text: str
    ) -> None:
        await self.bot.edit_message_text(
            chat_id=int(chat_id),
            message_id=int(message_id),
            text=text,
            reply_markup=None,
        )


def _chat_id_from_user_id(user_id: str) -> int:
    if user_id.startswith("tg:"):
        return int(user_id.split(":", 1)[1])
    return int(user_id)
