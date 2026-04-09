from decimal import Decimal, InvalidOperation
from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.protocols import DraftApplicationService
from app.application.protocols.schemas import DraftSettingsInput, DraftView

router = Router(name="draft")

PRESET_LABELS = {
    "unified_rhythm": "Unified Rhythm",
    "layered_pulse": "Layered Pulse",
    "golden_pulse": "Golden Pulse / Conveyor",
}


class CalculationInputState(StatesGroup):
    weekly_target_total_mg = State()
    duration_weeks = State()
    max_injection_volume_ml = State()
    max_injections_per_week = State()


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
async def on_continue_to_calculation(
    callback: CallbackQuery,
    state: FSMContext,
    draft_service: DraftApplicationService,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    draft = await draft_service.list_draft(user_id)
    if not draft.items:
        await callback.message.answer("Сначала добавьте хотя бы один продукт в Draft.")
        await callback.answer()
        return

    settings = await draft_service.get_draft_settings(user_id)
    current = settings.weekly_target_total_mg if settings else None
    await state.set_state(CalculationInputState.weekly_target_total_mg)
    await callback.message.answer(
        "Подготовка к расчету: укажите общий weekly target (mg)."
        + (f" Сейчас: {current}." if current is not None else ""),
    )
    await callback.answer()


@router.message(CalculationInputState.weekly_target_total_mg)
async def on_weekly_target_input(message: Message, state: FSMContext, draft_service: DraftApplicationService) -> None:
    value = _parse_decimal(message.text)
    if value is None or value <= Decimal("0"):
        await message.answer("Введите число больше 0, например `350`.")
        return

    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    await _save_settings_patch(draft_service, user_id, weekly_target_total_mg=value)
    await state.set_state(CalculationInputState.duration_weeks)
    await message.answer("Укажите длительность протокола в неделях (duration_weeks).")


@router.message(CalculationInputState.duration_weeks)
async def on_duration_input(message: Message, state: FSMContext, draft_service: DraftApplicationService) -> None:
    value = _parse_positive_int(message.text)
    if value is None:
        await message.answer("Введите целое число недель, например `12`.")
        return

    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    await _save_settings_patch(draft_service, user_id, duration_weeks=value)
    await state.clear()
    await message.answer(
        "Выберите preset стратегии.",
        reply_markup=build_preset_actions(),
    )


@router.callback_query(F.data.startswith("draft:calc:preset:"))
async def on_preset_selected(callback: CallbackQuery, state: FSMContext, draft_service: DraftApplicationService) -> None:
    preset_code = callback.data.split(":", 3)[3]
    if preset_code not in PRESET_LABELS:
        await callback.answer("Неизвестный preset", show_alert=True)
        return

    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    await _save_settings_patch(draft_service, user_id, preset_code=preset_code)
    await state.set_state(CalculationInputState.max_injection_volume_ml)
    await callback.message.answer("Введите max injection volume (ml), например `2.5`.")
    await callback.answer()


@router.message(CalculationInputState.max_injection_volume_ml)
async def on_max_volume_input(message: Message, state: FSMContext, draft_service: DraftApplicationService) -> None:
    value = _parse_decimal(message.text)
    if value is None or value <= Decimal("0"):
        await message.answer("Введите объем в ml больше 0, например `2`.")
        return

    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    await _save_settings_patch(draft_service, user_id, max_injection_volume_ml=value)
    await state.set_state(CalculationInputState.max_injections_per_week)
    await message.answer("Введите max injections per week (целое число).")


@router.message(CalculationInputState.max_injections_per_week)
async def on_max_injections_input(message: Message, state: FSMContext, draft_service: DraftApplicationService) -> None:
    value = _parse_positive_int(message.text)
    if value is None:
        await message.answer("Введите целое число больше 0, например `3`.")
        return

    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    await _save_settings_patch(draft_service, user_id, max_injections_per_week=value)
    readiness = await draft_service.get_draft_readiness(user_id)
    await state.clear()
    await message.answer(_render_readiness_summary(readiness), reply_markup=build_draft_shortcut())


def build_draft_shortcut() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Draft", callback_data="draft:open")]],
    )


def build_preset_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"draft:calc:preset:{code}")]
            for code, label in PRESET_LABELS.items()
        ]
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

    if draft.settings:
        lines.extend(
            [
                "\nПараметры подготовки:",
                f"- target mg/week: {draft.settings.weekly_target_total_mg or '—'}",
                f"- duration weeks: {draft.settings.duration_weeks or '—'}",
                f"- preset: {PRESET_LABELS.get(draft.settings.preset_code or '', '—')}",
                f"- max volume ml: {draft.settings.max_injection_volume_ml or '—'}",
                f"- max injections/week: {draft.settings.max_injections_per_week or '—'}",
            ]
        )

    lines.append("\nСледующий шаг: protocol preparation и readiness check перед pulse calculation.")
    return "\n".join(lines)


def _render_readiness_summary(readiness) -> str:
    lines = [readiness.summary]
    if not readiness.issues:
        lines.append("✅ Все обязательные input-параметры заполнены.")
        return "\n".join(lines)

    for issue in readiness.issues:
        prefix = "❌" if issue.severity == "error" else "⚠️"
        lines.append(f"{prefix} {issue.message}")
    return "\n".join(lines)


async def _save_settings_patch(draft_service: DraftApplicationService, user_id: str, **patch) -> None:
    current = await draft_service.get_draft_settings(user_id)
    payload = DraftSettingsInput(
        weekly_target_total_mg=patch.get(
            "weekly_target_total_mg", current.weekly_target_total_mg if current else None
        ),
        duration_weeks=patch.get("duration_weeks", current.duration_weeks if current else None),
        preset_code=patch.get("preset_code", current.preset_code if current else None),
        max_injection_volume_ml=patch.get(
            "max_injection_volume_ml", current.max_injection_volume_ml if current else None
        ),
        max_injections_per_week=patch.get(
            "max_injections_per_week", current.max_injections_per_week if current else None
        ),
        planned_start_date=patch.get("planned_start_date", current.planned_start_date if current else None),
    )
    await draft_service.save_draft_settings(user_id, payload)


def _resolve_user_id(telegram_user_id: int | None) -> str:
    if telegram_user_id is None:
        return "anonymous"
    return str(telegram_user_id)


def _parse_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    token = value.strip().replace(",", ".")
    try:
        return Decimal(token)
    except InvalidOperation:
        return None


def _parse_positive_int(value: str | None) -> int | None:
    if not value:
        return None
    token = value.strip()
    if not token.isdigit():
        return None
    parsed = int(token)
    if parsed <= 0:
        return None
    return parsed
