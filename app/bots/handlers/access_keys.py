from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.application.access import AccessKeyService

router = Router(name="access_keys")


class AccessKeyRedeemState(StatesGroup):
    waiting_for_key = State()


@router.message(F.text.func(lambda value: (value or "").strip().lower() in {"activate", "redeem key", "активировать"}))
async def redeem_key_entrypoint(message: Message, state: FSMContext) -> None:
    await state.set_state(AccessKeyRedeemState.waiting_for_key)
    await message.answer("Введите activation key.")


@router.message(AccessKeyRedeemState.waiting_for_key)
async def redeem_key_submit(message: Message, state: FSMContext, access_key_service: AccessKeyService) -> None:
    raw = (message.text or "").strip()
    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    if not raw:
        await message.answer("Ключ пустой. Введите корректный activation key.")
        return
    result = await access_key_service.redeem_key(user_id=user_id, key_code=raw)
    await state.clear()
    if not result.ok:
        await message.answer(_render_failure(result.reason_code))
        return
    await message.answer(_render_success(result))


def _render_success(result) -> str:
    lines = ["Ключ активирован ✅", "Доступ предоставлен:"]
    for grant in result.granted_entitlements:
        expires = grant.expires_at.isoformat() if grant.expires_at else "без срока"
        lines.append(f"- {grant.entitlement_code} (до: {expires})")
    return "\n".join(lines)


def _render_failure(reason_code: str) -> str:
    messages = {
        "access_key_invalid": "Ключ не найден.",
        "access_key_disabled": "Ключ отключен.",
        "access_key_expired": "Срок действия ключа истек.",
        "access_key_exhausted": "Лимит активаций ключа исчерпан.",
        "access_key_already_redeemed_by_user": "Этот ключ уже активирован вашим аккаунтом.",
    }
    return messages.get(reason_code, f"Активация отклонена: {reason_code}")


def _resolve_user_id(telegram_user_id: int | None) -> str:
    if telegram_user_id is None:
        return "anonymous"
    return f"tg:{telegram_user_id}"
