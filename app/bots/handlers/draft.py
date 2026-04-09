from uuid import UUID

from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.protocols import DraftApplicationService
from app.application.protocols.schemas import DraftView

router = Router(name="draft")


@router.message(F.text.func(lambda value: (value or "").strip().lower() == "draft"))
async def draft_entrypoint(message: Message, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    draft = await draft_service.list_draft(user_id)
    await message.answer(_render_draft_summary(draft), reply_markup=build_draft_actions(draft))


@router.callback_query(F.data.startswith("search:draft:"))
async def on_add_to_draft(callback: CallbackQuery, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    product_id = UUID(callback.data.split(":", 2)[2])
    try:
        result = await draft_service.add_product_to_draft(user_id=user_id, product_id=product_id)
    except ValueError:
        await callback.message.answer("Не удалось добавить препарат: карточка недоступна в каталоге.")
        await callback.answer()
        return

    if result.added:
        await callback.message.answer(
            "Позиция добавлена в черновик протокола. "
            "Откройте `Draft`, чтобы продолжить подготовку к расчету.",
            reply_markup=build_draft_shortcut(),
        )
    else:
        await callback.message.answer(
            "Эта позиция уже есть в текущем черновике. "
            "Мы сохраняем по одной записи на продукт.",
            reply_markup=build_draft_shortcut(),
        )
    await callback.answer()


@router.callback_query(F.data == "draft:open")
async def on_open_draft(callback: CallbackQuery, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    draft = await draft_service.list_draft(user_id)
    await callback.message.answer(_render_draft_summary(draft), reply_markup=build_draft_actions(draft))
    await callback.answer()


@router.callback_query(F.data.startswith("draft:remove:"))
async def on_remove_item(callback: CallbackQuery, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    item_id = UUID(callback.data.split(":", 2)[2])
    draft = await draft_service.remove_item_from_draft(user_id=user_id, item_id=item_id)
    if draft is None:
        await callback.message.answer("Черновик не найден. Напишите `Draft`, чтобы создать новый.")
    else:
        await callback.message.answer("Позиция удалена из черновика.")
        await callback.message.answer(_render_draft_summary(draft), reply_markup=build_draft_actions(draft))
    await callback.answer()


@router.callback_query(F.data == "draft:clear:confirm")
async def on_clear_confirm(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "Очистить весь черновик протокола?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Да, очистить", callback_data="draft:clear:yes"),
                    InlineKeyboardButton(text="Отмена", callback_data="draft:open"),
                ]
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "draft:clear:yes")
async def on_clear_yes(callback: CallbackQuery, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    draft = await draft_service.clear_draft(user_id)
    if draft is None:
        await callback.message.answer("Активный черновик не найден.")
    else:
        await callback.message.answer("Черновик очищен.")
        await callback.message.answer(_render_draft_summary(draft), reply_markup=build_draft_actions(draft))
    await callback.answer()


@router.callback_query(F.data == "draft:calculate")
async def on_continue_to_calculation(callback: CallbackQuery, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    draft = await draft_service.mark_ready_for_calculation(user_id)
    await callback.message.answer(
        "Шаг расчета pulse engine будет добавлен в Wave 2. "
        f"Сейчас в черновике: {len(draft.items)} поз.",
    )
    await callback.answer()


def build_draft_shortcut() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Draft", callback_data="draft:open")]],
    )


def build_draft_actions(draft: DraftView) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    rows.append([InlineKeyboardButton(text="Обновить Draft", callback_data="draft:open")])

    for idx, item in enumerate(draft.items, start=1):
        title = item.selected_product_name or item.selected_brand or f"Позиция {idx}"
        rows.append([InlineKeyboardButton(text=f"Удалить: {title[:24]}", callback_data=f"draft:remove:{item.item_id}")])

    if draft.items:
        rows.append([InlineKeyboardButton(text="Очистить Draft", callback_data="draft:clear:confirm")])
        rows.append([InlineKeyboardButton(text="К расчету", callback_data="draft:calculate")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _render_draft_summary(draft: DraftView) -> str:
    if not draft.items:
        return "Черновик протокола пуст. Добавьте препараты из поиска через `+Draft`."

    lines = ["Черновик протокола:"]
    for idx, item in enumerate(draft.items, start=1):
        label = item.selected_product_name or "Без названия"
        brand = f" ({item.selected_brand})" if item.selected_brand else ""
        lines.append(f"{idx}. {label}{brand}")

    lines.append("\nСледующий шаг: переход к расчету (Wave 2).")
    return "\n".join(lines)


def _resolve_user_id(telegram_user_id: int | None) -> str:
    if telegram_user_id is None:
        return "anonymous"
    return str(telegram_user_id)
