from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.bots.core.flow import remember_container, safe_edit_or_send

router = Router(name="start")

_HOME_TEXT = (
    "<b>CycleSync</b>\n"
    "\n"
    "Управление протоколами приёма.\n"
    "\n"
    "Используй кнопки ниже или введи название препарата для поиска."
)


def _build_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Draft", callback_data="draft:open"),
                InlineKeyboardButton(text="🧪 Labs", callback_data="labs:root"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings:open"),
            ],
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    sent = await message.answer(
        text=_HOME_TEXT,
        reply_markup=_build_home_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await remember_container(state, sent.message_id)


@router.callback_query(F.data == "nav:home")
async def on_nav_home(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_HOME_TEXT,
        reply_markup=_build_home_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()
