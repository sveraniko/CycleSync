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
        items=(CheckoutItemCreate(offer_code="expert_case_access", qty=1),),
    )
    await message.answer(_render_checkout(checkout), reply_markup=build_checkout_actions(checkout.checkout.checkout_id))


@router.message(Command("apply_coupon"))
async def apply_coupon(message: Message, checkout_service: CheckoutService) -> None:
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Usage: /apply_coupon <checkout_id> <coupon_code>")
        return
    try:
        checkout_id = UUID(parts[1])
    except ValueError:
        await message.answer("Invalid checkout_id format.")
        return
    coupon_code = parts[2]
    user_id = f"tg:{message.from_user.id}" if message.from_user else "tg:unknown"
    result = await checkout_service.apply_coupon_to_checkout(checkout_id=checkout_id, user_id=user_id, coupon_code=coupon_code)
    if result.status in {"applied", "already_applied"}:
        discount = result.redemption.discount_amount if result.redemption else result.checkout.checkout.discount_amount
        suffix = " (already applied)" if result.status == "already_applied" else ""
        await message.answer(
            f"Coupon {coupon_code.upper()} accepted{suffix}. Discount={discount} {result.checkout.checkout.currency}. "
            f"New total={result.checkout.checkout.total_amount} {result.checkout.checkout.currency}.",
            reply_markup=build_checkout_actions(result.checkout.checkout.checkout_id),
        )
        return
    await message.answer(
        f"Coupon rejected: {result.reason_code}. Total remains {result.checkout.checkout.total_amount} {result.checkout.checkout.currency}.",
        reply_markup=build_checkout_actions(result.checkout.checkout.checkout_id),
    )


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


@router.callback_query(F.data.startswith("checkout:gift:"))
async def settle_gift_coupon(callback: CallbackQuery, checkout_service: CheckoutService) -> None:
    checkout_id = UUID(callback.data.split(":")[-1])
    try:
        state = await checkout_service.settle_free_checkout(checkout_id=checkout_id, reason_code="gift_coupon")
    except CommerceError as exc:
        await callback.message.answer(f"Gift settlement failed: {exc}")
        await callback.answer()
        return
    await callback.message.answer(_render_checkout(state))
    await callback.answer()


@router.callback_query(F.data.startswith("checkout:coupon:ask:"))
async def coupon_prompt(callback: CallbackQuery) -> None:
    checkout_id = callback.data.split(":")[-1]
    await callback.message.answer(f"Apply coupon with command:\n/apply_coupon {checkout_id} YOUR_CODE")
    await callback.answer()


@router.callback_query(F.data.startswith("checkout:status:"))
async def show_status(callback: CallbackQuery, checkout_service: CheckoutService) -> None:
    checkout_id = UUID(callback.data.split(":")[-1])
    state = await checkout_service.get_checkout(checkout_id=checkout_id)
    await callback.message.answer(_render_checkout(state), reply_markup=build_checkout_actions(checkout_id))
    await callback.answer()


@router.message(Command("offers"))
async def list_offers(message: Message, checkout_service: CheckoutService) -> None:
    offers = await checkout_service.list_offers()
    if not offers:
        await message.answer("No active offers available.")
        return
    lines = ["Active offers:"]
    for offer in offers:
        lines.append(f"- {offer.offer_code}: {offer.title} — {offer.default_amount} {offer.currency}")
    await message.answer("\n".join(lines))


def build_checkout_actions(checkout_id) -> InlineKeyboardMarkup:
    checkout_id = str(checkout_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Apply coupon", callback_data=f"checkout:coupon:ask:{checkout_id}")],
            [InlineKeyboardButton(text="Pay with Stars", callback_data=f"checkout:provider:init:stars:{checkout_id}")],
            [InlineKeyboardButton(text="Confirm Stars paid", callback_data=f"checkout:provider:confirm:stars:{checkout_id}")],
            [InlineKeyboardButton(text="Complete gift checkout", callback_data=f"checkout:gift:{checkout_id}")],
            [InlineKeyboardButton(text="Refresh checkout status", callback_data=f"checkout:status:{checkout_id}")],
        ]
    )


@router.callback_query(F.data.startswith("checkout:provider:init:"))
async def init_provider_checkout(callback: CallbackQuery, checkout_service: CheckoutService) -> None:
    _, _, _, provider_code, checkout_id_text = callback.data.split(":")
    checkout_id = UUID(checkout_id_text)
    try:
        state = await checkout_service.initiate_payment(checkout_id=checkout_id, provider_code=provider_code)
    except CommerceError as exc:
        await callback.message.answer(f"Provider init failed: {exc}")
        await callback.answer()
        return
    await callback.message.answer(_render_checkout(state), reply_markup=build_checkout_actions(checkout_id))
    await callback.answer()


@router.callback_query(F.data.startswith("checkout:provider:confirm:"))
async def confirm_provider_checkout(callback: CallbackQuery, checkout_service: CheckoutService) -> None:
    _, _, _, provider_code, checkout_id_text = callback.data.split(":")
    checkout_id = UUID(checkout_id_text)
    try:
        state = await checkout_service.confirm_provider_payment(checkout_id=checkout_id, provider_code=provider_code, outcome="succeeded")
    except CommerceError as exc:
        await callback.message.answer(f"Provider confirmation failed: {exc}")
        await callback.answer()
        return
    await callback.message.answer(_render_checkout(state), reply_markup=build_checkout_actions(checkout_id))
    await callback.answer()


@router.callback_query(F.data.startswith("checkout:provider:fail:"))
async def fail_provider_checkout(callback: CallbackQuery, checkout_service: CheckoutService) -> None:
    _, _, _, provider_code, checkout_id_text = callback.data.split(":")
    checkout_id = UUID(checkout_id_text)
    try:
        state = await checkout_service.confirm_provider_payment(
            checkout_id=checkout_id,
            provider_code=provider_code,
            outcome="failed",
            metadata={"error_code": "telegram_stars_failed", "error_message": "Payment cancelled in Telegram"},
        )
    except CommerceError as exc:
        await callback.message.answer(f"Provider failure update failed: {exc}")
        await callback.answer()
        return
    await callback.message.answer(_render_checkout(state), reply_markup=build_checkout_actions(checkout_id))
    await callback.answer()


def _render_checkout(state) -> str:
    item_lines = [f"- {item.title}: {item.qty} x {item.unit_amount} = {item.line_total}" for item in state.items]
    base = (
        "Checkout\n"
        f"id={state.checkout.checkout_id}\n"
        f"status={state.checkout.checkout_status}\n"
        f"subtotal={state.checkout.subtotal_amount} {state.checkout.currency}\n"
        f"discount={state.checkout.discount_amount} {state.checkout.currency}\n"
        f"total={state.checkout.total_amount} {state.checkout.currency}\n"
        f"mode={state.checkout.settlement_mode}\n"
        + "\n".join(item_lines)
    )
    if state.attempts:
        last_attempt = state.attempts[-1]
        base += (
            "\n\nPayment attempt\n"
            f"provider={last_attempt.provider_code}\n"
            f"attempt_status={last_attempt.attempt_status}\n"
            f"provider_reference={last_attempt.provider_reference}\n"
        )
    fulfillment = getattr(state, "fulfillment", None)
    if fulfillment is None:
        return base
    grants = (fulfillment.result_payload or {}).get("grants", [])
    grant_lines = [
        f"- {grant['offer_code']} -> {grant['entitlement_code']} (until {grant['expires_at'] or 'no expiry'})"
        for grant in grants
    ]
    return (
        base
        + "\n\nFulfillment\n"
        + f"status={fulfillment.fulfillment_status}\n"
        + f"fulfilled_at={fulfillment.fulfilled_at}\n"
        + ("Unlocked:\n" + "\n".join(grant_lines) if grant_lines else "Unlocked: none")
    )
