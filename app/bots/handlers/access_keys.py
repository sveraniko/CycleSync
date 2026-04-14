from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.types.callback_query import CallbackQuery

from app.application.access import AccessKeyService
from app.bots.core.flow import delete_user_input_message, safe_edit_or_send
from app.bots.core.formatting import compact_status_label

router = Router(name="access_keys")


class AccessKeyRedeemState(StatesGroup):
    waiting_for_key = State()


@router.callback_query(F.data == "access:activate:start")
async def redeem_key_entrypoint_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AccessKeyRedeemState.waiting_for_key)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text="🔐 Активация доступа\n\nОтправьте activation key следующим сообщением.",
    )
    await callback.answer()


@router.message(F.text.func(lambda value: (value or "").strip().lower() in {"activate", "redeem key", "активировать"}))
async def redeem_key_entrypoint(message: Message, state: FSMContext) -> None:
    await state.set_state(AccessKeyRedeemState.waiting_for_key)
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text="🔐 Активация доступа\n\nОтправьте activation key следующим сообщением.",
    )


@router.message(AccessKeyRedeemState.waiting_for_key)
async def redeem_key_submit(message: Message, state: FSMContext, access_key_service: AccessKeyService) -> None:
    raw = (message.text or "").strip()
    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    if not raw:
        await safe_edit_or_send(
            state=state,
            source_message=message,
            text="🔐 Активация доступа\n\nКлюч пустой. Введите корректный activation key.",
        )
        await delete_user_input_message(message)
        return
    result = await access_key_service.redeem_key(user_id=user_id, key_code=raw)
    await state.set_state(None)
    if not result.ok:
        await safe_edit_or_send(
            state=state,
            source_message=message,
            text=_render_failure(result.reason_code),
        )
        await delete_user_input_message(message)
        return
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=_render_success(result),
    )
    await delete_user_input_message(message)


def _render_success(result) -> str:
    lines = ["✅ Ключ активирован", "Открыт доступ:"]
    for grant in result.granted_entitlements:
        expires = grant.expires_at.isoformat() if grant.expires_at else "без срока"
        lines.append(f"• {compact_status_label(grant.entitlement_code)} (до: {expires})")
    return "\n".join(lines)


def _render_failure(reason_code: str) -> str:
    messages = {
        "access_key_invalid": "❌ Ключ не найден. Проверьте код и попробуйте снова.",
        "access_key_disabled": "❌ Ключ отключен. Запросите новый у поддержки.",
        "access_key_expired": "❌ Срок действия ключа истек.",
        "access_key_exhausted": "❌ Лимит активаций для этого ключа исчерпан.",
        "access_key_already_redeemed_by_user": "ℹ️ Этот ключ уже активирован вашим аккаунтом.",
    }
    return messages.get(reason_code, f"❌ Активация отклонена: {compact_status_label(reason_code)}.")


def _resolve_user_id(telegram_user_id: int | None) -> str:
    if telegram_user_id is None:
        return "anonymous"
    return f"tg:{telegram_user_id}"
