from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.bots.core.flow import remember_container, safe_edit_or_send
from app.bots.core.permissions import is_admin_user

router = Router(name="start")

_HOME_TEXT = (
    "<b>CycleSync</b>\n"
    "\n"
    "Управление протоколами приёма.\n"
    "\n"
    "Используй кнопки ниже или введи название препарата для поиска."
)


def _build_home_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="📋 Черновик", callback_data="draft:open"),
            InlineKeyboardButton(text="🧪 Лабы", callback_data="labs:root"),
        ],
        [
            InlineKeyboardButton(text="🧬 Мой протокол", callback_data="protocol:view"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings:open"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🔧 Админ", callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    admin_ids: tuple[int, ...] | None = None,
) -> None:
    uid = message.from_user.id if message.from_user else None
    sent = await message.answer(
        text=_HOME_TEXT,
        reply_markup=_build_home_keyboard(is_admin=is_admin_user(uid, admin_ids)),
        parse_mode=ParseMode.HTML,
    )
    await remember_container(state, sent.message_id)


@router.callback_query(F.data == "nav:home")
async def on_nav_home(
    callback: CallbackQuery,
    state: FSMContext,
    admin_ids: tuple[int, ...] | None = None,
) -> None:
    uid = callback.from_user.id if callback.from_user else None
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_HOME_TEXT,
        reply_markup=_build_home_keyboard(is_admin=is_admin_user(uid, admin_ids)),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()
