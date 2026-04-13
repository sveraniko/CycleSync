from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bots.core.flow import remember_container

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    sent = await message.answer("Привет! Введи название препарата или компонент, и я найду подходящие позиции.")
    await remember_container(state, sent.message_id)
