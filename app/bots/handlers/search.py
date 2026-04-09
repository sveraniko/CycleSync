from uuid import UUID

from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.search.service import SearchApplicationService

router = Router(name="search")


@router.message(F.text)
async def search_entrypoint(message: Message, search_service: SearchApplicationService) -> None:
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    response = await search_service.search_products(query=text, user_id=str(message.from_user.id) if message.from_user else None)

    if response.degraded:
        await message.answer("Search временно недоступен. Попробуйте чуть позже.")
        return

    if not response.results:
        await message.answer("Ничего не найдено. Попробуйте уточнить название или состав.")
        return

    for idx, item in enumerate(response.results, start=1):
        caption = f"{idx}. {item.product_name} — {item.brand}"
        if item.composition_summary:
            caption += f"\n{item.composition_summary}"
        if item.form_factor:
            caption += f"\nФорма: {item.form_factor}"
        await message.answer(caption, reply_markup=build_result_actions(item.document_id))


@router.callback_query(F.data.startswith("search:open:"))
async def on_open_card(callback: CallbackQuery, search_service: SearchApplicationService) -> None:
    product_id = callback.data.split(":", 2)[2]
    card = await search_service.open_card(UUID(product_id))
    if card is None:
        await callback.message.answer("Карточка не найдена.")
    else:
        text = (
            f"{card.product_name}\n"
            f"Бренд: {card.brand}\n"
            f"Состав: {card.composition_summary or '—'}\n"
            f"Форма: {card.form_factor or '—'}\n"
            f"Official: {card.official_url or '—'}\n"
            f"Authenticity: {card.authenticity_notes or '—'}"
        )
        if card.media_refs:
            text += "\nMedia: " + ", ".join(card.media_refs[:3])
        await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith("search:draft:"))
async def on_add_to_draft(callback: CallbackQuery) -> None:
    await callback.message.answer("`+Draft` hook готов. Persistence будет подключен в PR3.")
    await callback.answer()


def build_result_actions(product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Open", callback_data=f"search:open:{product_id}"),
                InlineKeyboardButton(text="+Draft", callback_data=f"search:draft:{product_id}"),
            ]
        ]
    )
