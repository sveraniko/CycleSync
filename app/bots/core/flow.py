from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup

CONTAINER_MESSAGE_ID_KEY = "ui_container_message_id"


async def remember_container(state: FSMContext, message_id: int) -> None:
    await state.update_data(**{CONTAINER_MESSAGE_ID_KEY: message_id})


async def get_container_message_id(state: FSMContext) -> int | None:
    data = await state.get_data()
    message_id = data.get(CONTAINER_MESSAGE_ID_KEY)
    if isinstance(message_id, int):
        return message_id
    return None


async def reset_container(state: FSMContext) -> None:
    data = await state.get_data()
    if CONTAINER_MESSAGE_ID_KEY not in data:
        return
    next_data = dict(data)
    next_data.pop(CONTAINER_MESSAGE_ID_KEY, None)
    await state.set_data(next_data)


async def send_or_edit(
    *,
    state: FSMContext,
    source_message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    container_message_id = await get_container_message_id(state)
    if container_message_id is None:
        sent = await source_message.answer(text, reply_markup=reply_markup)
        await remember_container(state, sent.message_id)
        return sent

    edited = await source_message.bot.edit_message_text(
        chat_id=source_message.chat.id,
        message_id=container_message_id,
        text=text,
        reply_markup=reply_markup,
    )
    if isinstance(edited, Message):
        return edited
    return source_message


async def safe_edit_or_send(
    *,
    state: FSMContext,
    source_message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    try:
        return await send_or_edit(
            state=state,
            source_message=source_message,
            text=text,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest:
        sent = await source_message.answer(text, reply_markup=reply_markup)
        await remember_container(state, sent.message_id)
        return sent


async def delete_user_input_message(message: Message | None) -> None:
    if message is None:
        return
    try:
        await message.delete()
    except TelegramBadRequest:
        return
