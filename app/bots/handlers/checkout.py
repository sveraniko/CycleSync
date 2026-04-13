from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.commerce import CheckoutItemCreate, CheckoutService, CommerceError
from app.bots.core.flow import delete_user_input_message, safe_edit_or_send
from app.bots.core.formatting import compact_status_label, format_decimal_human
from app.bots.core.permissions import can_view_debug

router = Router(name="checkout")


class CheckoutState(StatesGroup):
    waiting_coupon_code = State()


@router.message(Command("checkout_demo"))
async def checkout_demo(message: Message, state: FSMContext, checkout_service: CheckoutService) -> None:
    user_id = f"tg:{message.from_user.id}" if message.from_user else "tg:unknown"
    checkout = await checkout_service.create_checkout(
        user_id=user_id,
        currency="USD",
        settlement_mode="internal",
        source_context="specialist_access",
        items=(CheckoutItemCreate(offer_code="expert_case_access", qty=1),),
    )
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=_render_checkout(checkout),
        reply_markup=build_checkout_actions(checkout.checkout.checkout_id),
    )


@router.callback_query(F.data.startswith("checkout:free:"))
async def settle_free(
    callback: CallbackQuery,
    state: FSMContext,
    checkout_service: CheckoutService,
    admin_ids: tuple[int, ...] | None = None,
    debug_enabled: bool = False,
) -> None:
    if not _can_view_debug_actions(callback, admin_ids=admin_ids, debug_enabled=debug_enabled):
        await callback.answer("Недоступно", show_alert=True)
        return
    checkout_id = UUID(callback.data.split(":")[-1])
    try:
        checkout_state = await checkout_service.settle_free_checkout(
            checkout_id=checkout_id, reason_code="dev_mode"
        )
    except CommerceError as exc:
        await _show_checkout_panel(
            source_message=callback.message,
            state=state,
            checkout_service=checkout_service,
            checkout_id=checkout_id,
            notice=f"Не удалось завершить free settlement: {exc}",
            admin_ids=admin_ids,
            debug_enabled=debug_enabled,
        )
        await callback.answer()
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_checkout(checkout_state, notice="Checkout отмечен как бесплатный."),
        reply_markup=build_checkout_actions(checkout_id, show_debug_actions=True),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("checkout:gift:"))
async def settle_gift_coupon(
    callback: CallbackQuery,
    state: FSMContext,
    checkout_service: CheckoutService,
    admin_ids: tuple[int, ...] | None = None,
    debug_enabled: bool = False,
) -> None:
    if not _can_view_debug_actions(callback, admin_ids=admin_ids, debug_enabled=debug_enabled):
        await callback.answer("Недоступно", show_alert=True)
        return
    checkout_id = UUID(callback.data.split(":")[-1])
    try:
        checkout_state = await checkout_service.settle_free_checkout(
            checkout_id=checkout_id, reason_code="gift_coupon"
        )
    except CommerceError as exc:
        await _show_checkout_panel(
            source_message=callback.message,
            state=state,
            checkout_service=checkout_service,
            checkout_id=checkout_id,
            notice=f"Gift settlement отклонен: {exc}",
            admin_ids=admin_ids,
            debug_enabled=debug_enabled,
        )
        await callback.answer()
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_checkout(checkout_state, notice="Gift settlement применен."),
        reply_markup=build_checkout_actions(checkout_id, show_debug_actions=True),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("checkout:coupon:ask:"))
async def coupon_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    checkout_service: CheckoutService,
    admin_ids: tuple[int, ...] | None = None,
    debug_enabled: bool = False,
) -> None:
    checkout_id = UUID(callback.data.split(":")[-1])
    await state.set_state(CheckoutState.waiting_coupon_code)
    await state.update_data(checkout_coupon_checkout_id=str(checkout_id))
    checkout_state = await checkout_service.get_checkout(checkout_id=checkout_id)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_checkout(
            checkout_state,
            notice="Введите код купона отдельным сообщением. Мы применим его в этом же окне.",
        ),
        reply_markup=build_checkout_actions(
            checkout_id,
            show_debug_actions=_can_view_debug_actions(
                callback, admin_ids=admin_ids, debug_enabled=debug_enabled
            ),
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("checkout:status:"))
async def show_status(
    callback: CallbackQuery,
    state: FSMContext,
    checkout_service: CheckoutService,
    admin_ids: tuple[int, ...] | None = None,
    debug_enabled: bool = False,
) -> None:
    checkout_id = UUID(callback.data.split(":")[-1])
    await _show_checkout_panel(
        source_message=callback.message,
        state=state,
        checkout_service=checkout_service,
        checkout_id=checkout_id,
        notice="Статус обновлен.",
        admin_ids=admin_ids,
        debug_enabled=debug_enabled,
    )
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


@router.message(CheckoutState.waiting_coupon_code)
async def coupon_submit(
    message: Message,
    state: FSMContext,
    checkout_service: CheckoutService,
    admin_ids: tuple[int, ...] | None = None,
    debug_enabled: bool = False,
) -> None:
    payload = await state.get_data()
    checkout_id_raw = payload.get("checkout_coupon_checkout_id")
    if not checkout_id_raw:
        await state.clear()
        return
    checkout_id = UUID(str(checkout_id_raw))
    coupon_code = (message.text or "").strip()
    user_id = f"tg:{message.from_user.id}" if message.from_user else "tg:unknown"
    if not coupon_code:
        checkout = await checkout_service.get_checkout(checkout_id=checkout_id)
        await safe_edit_or_send(
            state=state,
            source_message=message,
            text=_render_checkout(checkout, notice="Код купона пустой. Введите корректный код."),
            reply_markup=build_checkout_actions(
                checkout_id,
                show_debug_actions=_can_view_debug_user(
                    message.from_user.id if message.from_user else None,
                    admin_ids=admin_ids,
                    debug_enabled=debug_enabled,
                ),
            ),
        )
        await delete_user_input_message(message)
        return
    result = await checkout_service.apply_coupon_to_checkout(
        checkout_id=checkout_id,
        user_id=user_id,
        coupon_code=coupon_code,
    )
    await state.set_state(None)
    if result.status in {"applied", "already_applied"}:
        suffix = " (уже был применен)" if result.status == "already_applied" else ""
        notice = (
            f"Купон {coupon_code.upper()} принят{suffix}. "
            f"Скидка: {format_decimal_human(result.checkout.checkout.discount_amount)} {result.checkout.checkout.currency}. "
            f"Итого: {format_decimal_human(result.checkout.checkout.total_amount)} {result.checkout.checkout.currency}."
        )
    else:
        notice = (
            f"Купон не принят: {compact_status_label(result.reason_code)}. "
            f"Итого без изменений: {format_decimal_human(result.checkout.checkout.total_amount)} {result.checkout.checkout.currency}."
        )
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=_render_checkout(result.checkout, notice=notice),
        reply_markup=build_checkout_actions(
            result.checkout.checkout.checkout_id,
            show_debug_actions=_can_view_debug_user(
                message.from_user.id if message.from_user else None,
                admin_ids=admin_ids,
                debug_enabled=debug_enabled,
            ),
        ),
    )
    await delete_user_input_message(message)


def build_checkout_actions(checkout_id, *, show_debug_actions: bool = False) -> InlineKeyboardMarkup:
    checkout_id = str(checkout_id)
    rows = [
        [InlineKeyboardButton(text="Apply coupon", callback_data=f"checkout:coupon:ask:{checkout_id}")],
        [InlineKeyboardButton(text="Pay with Stars", callback_data=f"checkout:provider:init:stars:{checkout_id}")],
        [InlineKeyboardButton(text="Confirm Stars paid", callback_data=f"checkout:provider:confirm:stars:{checkout_id}")],
        [InlineKeyboardButton(text="Refresh status", callback_data=f"checkout:status:{checkout_id}")],
    ]
    if show_debug_actions:
        rows.extend(
            [
                [InlineKeyboardButton(text="Debug: mark provider failed", callback_data=f"checkout:provider:fail:stars:{checkout_id}")],
                [InlineKeyboardButton(text="Debug: complete gift", callback_data=f"checkout:gift:{checkout_id}")],
                [InlineKeyboardButton(text="Debug: settle free", callback_data=f"checkout:free:{checkout_id}")],
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("checkout:provider:init:"))
async def init_provider_checkout(
    callback: CallbackQuery,
    state: FSMContext,
    checkout_service: CheckoutService,
    admin_ids: tuple[int, ...] | None = None,
    debug_enabled: bool = False,
) -> None:
    _, _, _, provider_code, checkout_id_text = callback.data.split(":")
    checkout_id = UUID(checkout_id_text)
    try:
        checkout_state = await checkout_service.initiate_payment(checkout_id=checkout_id, provider_code=provider_code)
    except CommerceError as exc:
        await _show_checkout_panel(
            source_message=callback.message,
            state=state,
            checkout_service=checkout_service,
            checkout_id=checkout_id,
            notice=f"Не удалось запустить оплату: {exc}",
            admin_ids=admin_ids,
            debug_enabled=debug_enabled,
        )
        await callback.answer()
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_checkout(checkout_state, notice=f"Сессия оплаты через {provider_code.upper()} создана."),
        reply_markup=build_checkout_actions(
            checkout_id,
            show_debug_actions=_can_view_debug_actions(
                callback,
                admin_ids=admin_ids,
                debug_enabled=debug_enabled,
            ),
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("checkout:provider:confirm:"))
async def confirm_provider_checkout(
    callback: CallbackQuery,
    state: FSMContext,
    checkout_service: CheckoutService,
    admin_ids: tuple[int, ...] | None = None,
    debug_enabled: bool = False,
) -> None:
    _, _, _, provider_code, checkout_id_text = callback.data.split(":")
    checkout_id = UUID(checkout_id_text)
    try:
        checkout_state = await checkout_service.confirm_provider_payment(
            checkout_id=checkout_id, provider_code=provider_code, outcome="succeeded"
        )
    except CommerceError as exc:
        await _show_checkout_panel(
            source_message=callback.message,
            state=state,
            checkout_service=checkout_service,
            checkout_id=checkout_id,
            notice=f"Подтверждение оплаты не удалось: {exc}",
            admin_ids=admin_ids,
            debug_enabled=debug_enabled,
        )
        await callback.answer()
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_checkout(checkout_state, notice="Оплата подтверждена."),
        reply_markup=build_checkout_actions(
            checkout_id,
            show_debug_actions=_can_view_debug_actions(
                callback,
                admin_ids=admin_ids,
                debug_enabled=debug_enabled,
            ),
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("checkout:provider:fail:"))
async def fail_provider_checkout(
    callback: CallbackQuery,
    state: FSMContext,
    checkout_service: CheckoutService,
    admin_ids: tuple[int, ...] | None = None,
    debug_enabled: bool = False,
) -> None:
    if not _can_view_debug_actions(callback, admin_ids=admin_ids, debug_enabled=debug_enabled):
        await callback.answer("Недоступно", show_alert=True)
        return
    _, _, _, provider_code, checkout_id_text = callback.data.split(":")
    checkout_id = UUID(checkout_id_text)
    try:
        checkout_state = await checkout_service.confirm_provider_payment(
            checkout_id=checkout_id,
            provider_code=provider_code,
            outcome="failed",
            metadata={"error_code": "telegram_stars_failed", "error_message": "Payment cancelled in Telegram"},
        )
    except CommerceError as exc:
        await _show_checkout_panel(
            source_message=callback.message,
            state=state,
            checkout_service=checkout_service,
            checkout_id=checkout_id,
            notice=f"Не удалось зафиксировать provider failure: {exc}",
            admin_ids=admin_ids,
            debug_enabled=debug_enabled,
        )
        await callback.answer()
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_checkout(checkout_state, notice="Провайдер помечен как failed (debug)."),
        reply_markup=build_checkout_actions(checkout_id, show_debug_actions=True),
    )
    await callback.answer()


def _render_checkout(state, notice: str | None = None) -> str:
    item = state.items[0] if state.items else None
    title = item.title if item is not None else "Offer"
    base = [
        "🧾 Checkout",
        f"Товар: {title}",
        f"Статус: {compact_status_label(state.checkout.checkout_status)}",
        (
            "Сумма: "
            f"{format_decimal_human(state.checkout.subtotal_amount)} {state.checkout.currency}"
            f" • Скидка: {format_decimal_human(state.checkout.discount_amount)} {state.checkout.currency}"
            f" • Итого: {format_decimal_human(state.checkout.total_amount)} {state.checkout.currency}"
        ),
        f"Режим оплаты: {compact_status_label(state.checkout.settlement_mode)}",
    ]
    if state.attempts:
        last_attempt = state.attempts[-1]
        base.append(
            f"Провайдер: {last_attempt.provider_code.upper()} ({compact_status_label(last_attempt.attempt_status)})"
        )
        if last_attempt.provider_reference:
            base.append(f"Ссылка на оплату: {last_attempt.provider_reference}")
    fulfillment = getattr(state, "fulfillment", None)
    if fulfillment is not None:
        grants = (fulfillment.result_payload or {}).get("grants", [])
        if grants:
            unlocked = ", ".join(grant["entitlement_code"] for grant in grants)
        else:
            unlocked = "—"
        base.append(f"Доступ: {compact_status_label(fulfillment.fulfillment_status)} ({unlocked})")
    if notice:
        base.extend(["", f"ℹ️ {notice}"])
    return "\n".join(base)


async def _show_checkout_panel(
    *,
    source_message: Message,
    state: FSMContext,
    checkout_service: CheckoutService,
    checkout_id: UUID,
    notice: str | None,
    admin_ids: tuple[int, ...] | None,
    debug_enabled: bool,
) -> None:
    checkout_state = await checkout_service.get_checkout(checkout_id=checkout_id)
    await safe_edit_or_send(
        state=state,
        source_message=source_message,
        text=_render_checkout(checkout_state, notice=notice),
        reply_markup=build_checkout_actions(
            checkout_id,
            show_debug_actions=_can_view_debug_user(
                source_message.from_user.id if source_message.from_user else None,
                admin_ids=admin_ids,
                debug_enabled=debug_enabled,
            ),
        ),
    )


def _can_view_debug_actions(
    callback: CallbackQuery,
    *,
    admin_ids: tuple[int, ...] | None,
    debug_enabled: bool,
) -> bool:
    user_id = callback.from_user.id if callback.from_user else None
    return _can_view_debug_user(user_id, admin_ids=admin_ids, debug_enabled=debug_enabled)


def _can_view_debug_user(
    user_id: int | None,
    *,
    admin_ids: tuple[int, ...] | None,
    debug_enabled: bool,
) -> bool:
    return can_view_debug(user_id, admin_ids=admin_ids, debug_enabled=debug_enabled)
