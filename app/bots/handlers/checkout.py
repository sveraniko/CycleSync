from uuid import UUID
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.commerce import CheckoutItemCreate, CheckoutService, CommerceError

router = Router(name="checkout")


@router.message(Command("checkout_demo"))
async def checkout_demo(message: Message, checkout_service: CheckoutService) -> None:
    user_id = f"tg:{message.from_user.id}" if message.from_user else "tg:unknown"
    checkout = await checkout_service.create_checkout(
        user_id=user_id,
        currency="USD",
        settlement_mode="internal",
        source_context="specialist_access",
        items=(CheckoutItemCreate(item_code="expert_case_access", title="Specialist consult access", qty=1, unit_amount=1500),),
    )
    await message.answer(_render_checkout(checkout), reply_markup=build_checkout_actions(checkout.checkout.checkout_id))


@router.callback_query(F.data.startswith("checkout:free:"))
async def settle_free(callback: CallbackQuery, checkout_service: CheckoutService) -> None:
    checkout_id = UUID(callback.data.split(":")[-1])
    try:
        state = await checkout_service.settle_free_checkout(checkout_id=checkout_id, reason_code="dev_mode")
    except CommerceError as exc:
        await callback.message.answer(f"Checkout failed: {exc}")
        await callback.answer()
        return
    await callback.message.answer(_render_checkout(state))
    await callback.answer()


@router.callback_query(F.data.startswith("checkout:status:"))
async def show_status(callback: CallbackQuery, checkout_service: CheckoutService) -> None:
    checkout_id = UUID(callback.data.split(":")[-1])
    state = await checkout_service.get_checkout(checkout_id=checkout_id)
    await callback.message.answer(_render_checkout(state))
    await callback.answer()


def build_checkout_actions(checkout_id) -> InlineKeyboardMarkup:
    checkout_id = str(checkout_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Settle free (test)", callback_data=f"checkout:free:{checkout_id}")],
            [InlineKeyboardButton(text="Refresh checkout status", callback_data=f"checkout:status:{checkout_id}")],
        ]
    )


def _render_checkout(state) -> str:
    item_lines = [f"- {item.title}: {item.qty} x {item.unit_amount} = {item.line_total}" for item in state.items]
    return (
        "Checkout\n"
        f"id={state.checkout.checkout_id}\n"
        f"status={state.checkout.checkout_status}\n"
        f"total={state.checkout.total_amount} {state.checkout.currency}\n"
        f"mode={state.checkout.settlement_mode}\n"
        + "\n".join(item_lines)
    )
