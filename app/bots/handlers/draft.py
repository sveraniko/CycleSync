from decimal import Decimal, InvalidOperation
from uuid import UUID

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.protocols import CourseEstimatorService, DraftApplicationService
from app.application.protocols.schemas import (
    ActiveProtocolView,
    CourseEstimate,
    DraftSettingsInput,
    DraftView,
    InventoryConstraintInput,
    PulsePlanPreviewView,
    StackInputTargetInput,
)
from app.application.access import AccessEvaluationService
from app.bots.core.flow import delete_user_input_message, safe_edit_or_send
from app.bots.core.formatting import compact_status_label, escape_html_text, format_decimal_human

router = Router(name="draft")
_DRAFT_CLEAR_CONFIRM_KEY = "draft_clear_confirm"

PRESET_LABELS = {
    "unified_rhythm": "Unified Rhythm",
    "layered_pulse": "Layered Pulse",
    "golden_pulse": "Golden Pulse / Conveyor",
}

STATUS_LABELS = {
    "success": "✅ success",
    "success_with_warnings": "⚠️ success_with_warnings",
    "degraded_fallback": "⚠️ degraded_fallback",
    "failed_validation": "❌ failed_validation",
}

INPUT_MODE_LABELS = {
    "auto_pulse": "Auto Pulse",
    "total_target": "Total Target",
    "stack_smoothing": "Stack Smoothing",
    "inventory_constrained": "Inventory Constrained",
}


class CalculationInputState(StatesGroup):
    mode = State()
    weekly_target_total_mg = State()
    duration_weeks = State()
    max_injection_volume_ml = State()
    max_injections_per_week = State()
    stack_product_target = State()
    inventory_product_count = State()


WIZARD_STEP_KEY = "calc_wizard_step"
WIZARD_HISTORY_KEY = "calc_wizard_history"
WIZARD_MODE_KEY = "calc_wizard_mode"


@router.message(F.text.func(lambda value: (value or "").strip().lower() == "draft"))
async def draft_entrypoint(message: Message, state: FSMContext, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    draft = await draft_service.list_draft(user_id)
    await _render_draft_panel(message=message, state=state, draft=draft)


@router.callback_query(F.data.startswith("search:draft:"))
async def on_add_to_draft(callback: CallbackQuery, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    product_id = UUID(callback.data.split(":", 2)[2])
    try:
        result = await draft_service.add_product_to_draft(user_id=user_id, product_id=product_id)
    except ValueError:
        await callback.answer("Карточка недоступна в каталоге.", show_alert=True)
        return

    await callback.answer(
        "Добавлено в Draft." if result.added else "Уже есть в Draft.",
        show_alert=False,
    )


@router.callback_query(F.data == "draft:open")
async def on_open_draft(callback: CallbackQuery, state: FSMContext, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    draft = await draft_service.list_draft(user_id)
    await state.update_data(**{_DRAFT_CLEAR_CONFIRM_KEY: False})
    await _render_draft_panel(message=callback.message, state=state, draft=draft)
    await callback.answer()


@router.callback_query(F.data.startswith("draft:remove:"))
async def on_remove_item(callback: CallbackQuery, state: FSMContext, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    item_id = UUID(callback.data.split(":", 2)[2])
    draft = await draft_service.remove_item_from_draft(user_id=user_id, item_id=item_id)
    if draft is None:
        await safe_edit_or_send(
            state=state,
            source_message=callback.message,
            text="Черновик не найден. Напишите <code>Draft</code>, чтобы создать новый.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await state.update_data(**{_DRAFT_CLEAR_CONFIRM_KEY: False})
        await _render_draft_panel(message=callback.message, state=state, draft=draft)
    await callback.answer()


@router.callback_query(F.data == "draft:clear:confirm")
async def on_clear_confirm(callback: CallbackQuery, state: FSMContext, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    draft = await draft_service.list_draft(user_id)
    await state.update_data(**{_DRAFT_CLEAR_CONFIRM_KEY: True})
    await _render_draft_panel(message=callback.message, state=state, draft=draft, clear_confirm=True)
    await callback.answer()


@router.callback_query(F.data == "draft:clear:yes")
async def on_clear_yes(callback: CallbackQuery, state: FSMContext, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    draft = await draft_service.clear_draft(user_id)
    if draft is None:
        await safe_edit_or_send(
            state=state,
            source_message=callback.message,
            text="Активный Draft не найден.",
        )
    else:
        await state.update_data(**{_DRAFT_CLEAR_CONFIRM_KEY: False})
        await _render_draft_panel(message=callback.message, state=state, draft=draft)
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
        await safe_edit_or_send(
            state=state,
            source_message=callback.message,
            text="Сначала добавьте хотя бы один продукт в Draft.",
            reply_markup=build_draft_shortcut(),
        )
        await callback.answer()
        return

    settings = await draft_service.get_draft_settings(user_id)
    await state.set_state(CalculationInputState.mode)
    await _goto_wizard_step(
        message=callback.message,
        state=state,
        draft_service=draft_service,
        access_service=None,
        user_id=user_id,
        step="mode",
        push_history=False,
        current_mode=settings.protocol_input_mode if settings else None,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("draft:calc:mode:"))
async def on_mode_selected(
    callback: CallbackQuery,
    state: FSMContext,
    draft_service: DraftApplicationService,
    access_service: AccessEvaluationService,
) -> None:
    selected_mode = callback.data.split(":", 3)[3]
    if selected_mode not in INPUT_MODE_LABELS:
        await callback.answer("Неизвестный input mode", show_alert=True)
        return

    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    await _save_settings_patch(draft_service, user_id, protocol_input_mode=selected_mode)
    await state.update_data(**{WIZARD_MODE_KEY: selected_mode})
    await callback.answer()
    await _goto_wizard_step(
        message=callback.message,
        state=state,
        draft_service=draft_service,
        access_service=access_service,
        user_id=user_id,
        step=_first_step_for_mode(selected_mode),
    )


@router.callback_query(F.data == "draft:stack:edit")
async def on_stack_edit(callback: CallbackQuery, state: FSMContext, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    await _save_settings_patch(draft_service, user_id, protocol_input_mode="stack_smoothing")
    await state.update_data(**{WIZARD_MODE_KEY: "stack_smoothing"})
    await _goto_wizard_step(
        message=callback.message,
        state=state,
        draft_service=draft_service,
        access_service=None,
        user_id=user_id,
        step="stack_target",
    )
    await callback.answer()


@router.callback_query(F.data == "draft:wizard:back")
async def on_wizard_back(
    callback: CallbackQuery,
    state: FSMContext,
    draft_service: DraftApplicationService,
    access_service: AccessEvaluationService,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    data = await state.get_data()
    current_step = data.get(WIZARD_STEP_KEY)

    if current_step == "stack_target":
        completed = list(data.get("stack_completed_product_ids", []))
        current_product_id = data.get("stack_current_product_id")
        pending = list(data.get("stack_pending_product_ids", []))
        if completed:
            previous_product_id = completed.pop()
            if current_product_id:
                pending.insert(0, current_product_id)
            await state.update_data(
                stack_current_product_id=previous_product_id,
                stack_pending_product_ids=pending,
                stack_completed_product_ids=completed,
            )
            await _goto_wizard_step(
                message=callback.message,
                state=state,
                draft_service=draft_service,
                access_service=access_service,
                user_id=user_id,
                step="stack_target",
                push_history=False,
            )
            await callback.answer()
            return

    if current_step == "inventory_count":
        completed = list(data.get("inventory_completed_product_ids", []))
        current_product_id = data.get("inventory_current_product_id")
        pending = list(data.get("inventory_pending_product_ids", []))
        if completed:
            previous_product_id = completed.pop()
            if current_product_id:
                pending.insert(0, current_product_id)
            await state.update_data(
                inventory_current_product_id=previous_product_id,
                inventory_pending_product_ids=pending,
                inventory_completed_product_ids=completed,
            )
            await _goto_wizard_step(
                message=callback.message,
                state=state,
                draft_service=draft_service,
                access_service=access_service,
                user_id=user_id,
                step="inventory_count",
                push_history=False,
            )
            await callback.answer()
            return

    history = list(data.get(WIZARD_HISTORY_KEY, []))
    if not history:
        await _cancel_wizard(callback.message, state, draft_service, user_id)
        await callback.answer()
        return
    previous_step = history.pop()
    await state.update_data(**{WIZARD_HISTORY_KEY: history})
    await _goto_wizard_step(
        message=callback.message,
        state=state,
        draft_service=draft_service,
        access_service=access_service,
        user_id=user_id,
        step=previous_step,
        push_history=False,
    )
    await callback.answer()


@router.callback_query(F.data == "draft:wizard:cancel")
async def on_wizard_cancel(callback: CallbackQuery, state: FSMContext, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    await _cancel_wizard(callback.message, state, draft_service, user_id)
    await callback.answer()


@router.callback_query(F.data == "draft:calculate:run")
async def on_run_pulse_calculation(
    callback: CallbackQuery,
    state: FSMContext,
    draft_service: DraftApplicationService,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    preview = await draft_service.generate_pulse_plan_preview(user_id)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_preview_summary(preview),
        reply_markup=build_preview_actions(preview.preview_id),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("draft:activate:prepare:"))
async def on_prepare_activation(
    callback: CallbackQuery,
    state: FSMContext,
    draft_service: DraftApplicationService,
    estimator_service: CourseEstimatorService,
) -> None:
    preview_id = UUID(callback.data.split(":", 3)[3])
    try:
        estimate = await estimator_service.estimate_from_preview(preview_id)
    except ValueError:
        await safe_edit_or_send(
            state=state,
            source_message=callback.message,
            text="Не удалось открыть pre-start оценку: preview недоступен.",
        )
        await callback.answer()
        return

    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_pre_start_estimate_snapshot(estimate),
        reply_markup=build_pre_start_actions(preview_id),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("draft:activate:confirm:"))
async def on_activate_latest_preview(callback: CallbackQuery, state: FSMContext, draft_service: DraftApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    try:
        active = await draft_service.confirm_latest_preview_activation(user_id)
    except ValueError:
        await safe_edit_or_send(
            state=state,
            source_message=callback.message,
            text="Нет готового preview для активации. Сначала запустите расчёт.",
        )
        await callback.answer()
        return

    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_active_protocol_summary(active),
        reply_markup=build_active_protocol_actions(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("draft:estimate:preview:"))
async def on_preview_estimate(
    callback: CallbackQuery,
    state: FSMContext,
    estimator_service: CourseEstimatorService,
) -> None:
    preview_id = UUID(callback.data.split(":", 3)[3])
    try:
        estimate = await estimator_service.estimate_from_preview(preview_id)
    except ValueError:
        await safe_edit_or_send(
            state=state,
            source_message=callback.message,
            text="Оценка курса недоступна: preview не найден.",
        )
        await callback.answer()
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_course_estimate(estimate),
        reply_markup=build_preview_actions(preview_id),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "draft:estimate:active:latest")
async def on_active_protocol_estimate(
    callback: CallbackQuery,
    state: FSMContext,
    draft_service: DraftApplicationService,
    estimator_service: CourseEstimatorService,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    protocol_id = await draft_service.get_latest_active_protocol_id(user_id)
    if protocol_id is None:
        await safe_edit_or_send(
            state=state,
            source_message=callback.message,
            text="Нет активного протокола. Сначала подтвердите старт из preview.",
        )
        await callback.answer()
        return
    try:
        estimate = await estimator_service.estimate_from_active_protocol(protocol_id)
    except ValueError:
        await safe_edit_or_send(
            state=state,
            source_message=callback.message,
            text="Оценка курса недоступна: активный протокол не найден.",
        )
        await callback.answer()
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_course_estimate(estimate),
        reply_markup=build_active_protocol_actions(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(CalculationInputState.weekly_target_total_mg)
async def on_weekly_target_input(message: Message, state: FSMContext, draft_service: DraftApplicationService) -> None:
    value = _parse_decimal(message.text)
    if value is None or value <= Decimal("0"):
        await delete_user_input_message(message)
        await _render_wizard_panel(
            message=message,
            state=state,
            text="Введите число больше 0, например <code>350</code>.",
            reply_markup=build_wizard_navigation_actions(step="weekly_target"),
        )
        return

    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    await _save_settings_patch(draft_service, user_id, weekly_target_total_mg=value)
    await delete_user_input_message(message)
    await _goto_wizard_step(
        message=message,
        state=state,
        draft_service=draft_service,
        access_service=None,
        user_id=user_id,
        step="duration",
    )


@router.message(CalculationInputState.duration_weeks)
async def on_duration_input(message: Message, state: FSMContext, draft_service: DraftApplicationService) -> None:
    value = _parse_positive_int(message.text)
    if value is None:
        await delete_user_input_message(message)
        await _render_wizard_panel(
            message=message,
            state=state,
            text="Введите целое число недель, например <code>12</code>.",
            reply_markup=build_wizard_navigation_actions(step="duration"),
        )
        return

    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    await _save_settings_patch(draft_service, user_id, duration_weeks=value)
    await delete_user_input_message(message)
    await _goto_wizard_step(
        message=message,
        state=state,
        draft_service=draft_service,
        access_service=None,
        user_id=user_id,
        step="preset",
    )


@router.callback_query(F.data.startswith("draft:calc:preset:"))
async def on_preset_selected(callback: CallbackQuery, state: FSMContext, draft_service: DraftApplicationService) -> None:
    preset_code = callback.data.split(":", 3)[3]
    if preset_code not in PRESET_LABELS:
        await callback.answer("Неизвестный preset", show_alert=True)
        return

    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    await _save_settings_patch(draft_service, user_id, preset_code=preset_code)
    await _goto_wizard_step(
        message=callback.message,
        state=state,
        draft_service=draft_service,
        access_service=None,
        user_id=user_id,
        step="max_volume",
    )
    await callback.answer()


@router.message(CalculationInputState.max_injection_volume_ml)
async def on_max_volume_input(message: Message, state: FSMContext, draft_service: DraftApplicationService) -> None:
    value = _parse_decimal(message.text)
    if value is None or value <= Decimal("0"):
        await delete_user_input_message(message)
        await _render_wizard_panel(
            message=message,
            state=state,
            text="Введите объем в ml больше 0, например <code>2</code>.",
            reply_markup=build_wizard_navigation_actions(step="max_volume"),
        )
        return

    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    await _save_settings_patch(draft_service, user_id, max_injection_volume_ml=value)
    await delete_user_input_message(message)
    await _goto_wizard_step(
        message=message,
        state=state,
        draft_service=draft_service,
        access_service=None,
        user_id=user_id,
        step="max_injections",
    )


@router.message(CalculationInputState.max_injections_per_week)
async def on_max_injections_input(message: Message, state: FSMContext, draft_service: DraftApplicationService) -> None:
    value = _parse_positive_int(message.text)
    if value is None:
        await delete_user_input_message(message)
        await _render_wizard_panel(
            message=message,
            state=state,
            text="Введите целое число больше 0, например <code>3</code>.",
            reply_markup=build_wizard_navigation_actions(step="max_injections"),
        )
        return

    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    await _save_settings_patch(draft_service, user_id, max_injections_per_week=value)
    await delete_user_input_message(message)
    await _goto_wizard_step(
        message=message,
        state=state,
        draft_service=draft_service,
        access_service=None,
        user_id=user_id,
        step="readiness",
    )


@router.message(CalculationInputState.stack_product_target)
async def on_stack_target_input(message: Message, state: FSMContext, draft_service: DraftApplicationService) -> None:
    value = _parse_decimal(message.text)
    if value is None or value <= Decimal("0"):
        await delete_user_input_message(message)
        await _render_wizard_panel(
            message=message,
            state=state,
            text="Введите desired weekly mg > 0, например <code>125</code>.",
            reply_markup=build_wizard_navigation_actions(step="stack_target"),
        )
        return

    data = await state.get_data()
    pending = list(data.get("stack_pending_product_ids", []))
    current_product_id = data.get("stack_current_product_id")
    if current_product_id is None:
        await _cancel_wizard(message, state, draft_service, _resolve_user_id(message.from_user.id if message.from_user else None))
        return

    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    await draft_service.save_stack_input_targets(
        user_id,
        [
            StackInputTargetInput(
                product_id=UUID(current_product_id),
                protocol_input_mode="stack_smoothing",
                desired_weekly_mg=value,
            ),
        ],
    )
    await delete_user_input_message(message)
    completed = list(data.get("stack_completed_product_ids", []))
    completed.append(current_product_id)
    if pending:
        next_product_id = pending.pop(0)
        await state.update_data(
            stack_pending_product_ids=pending,
            stack_current_product_id=next_product_id,
            stack_completed_product_ids=completed,
        )
        await _goto_wizard_step(
            message=message,
            state=state,
            draft_service=draft_service,
            access_service=None,
            user_id=user_id,
            step="stack_target",
            push_history=False,
        )
        return

    await _goto_wizard_step(
        message=message,
        state=state,
        draft_service=draft_service,
        access_service=None,
        user_id=user_id,
        step="duration",
    )


@router.message(CalculationInputState.inventory_product_count)
async def on_inventory_count_input(message: Message, state: FSMContext, draft_service: DraftApplicationService) -> None:
    parsed = _parse_inventory_input(message.text)
    if parsed is None:
        await delete_user_input_message(message)
        await _render_wizard_panel(
            message=message,
            state=state,
            text="Введите в формате <code>&lt;count&gt; &lt;unit&gt;</code>, например <code>20 vial</code>.",
            reply_markup=build_wizard_navigation_actions(step="inventory_count"),
        )
        return
    available_count, count_unit = parsed

    data = await state.get_data()
    pending = list(data.get("inventory_pending_product_ids", []))
    current_product_id = data.get("inventory_current_product_id")
    if current_product_id is None:
        await _cancel_wizard(message, state, draft_service, _resolve_user_id(message.from_user.id if message.from_user else None))
        return

    user_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    await draft_service.save_inventory_constraints(
        user_id,
        [
            InventoryConstraintInput(
                product_id=UUID(current_product_id),
                protocol_input_mode="inventory_constrained",
                available_count=available_count,
                count_unit=count_unit,
            ),
        ],
    )
    await delete_user_input_message(message)
    completed = list(data.get("inventory_completed_product_ids", []))
    completed.append(current_product_id)
    if pending:
        next_product_id = pending.pop(0)
        await state.update_data(
            inventory_pending_product_ids=pending,
            inventory_current_product_id=next_product_id,
            inventory_completed_product_ids=completed,
        )
        await _goto_wizard_step(
            message=message,
            state=state,
            draft_service=draft_service,
            access_service=None,
            user_id=user_id,
            step="inventory_count",
            push_history=False,
        )
        return

    await _goto_wizard_step(
        message=message,
        state=state,
        draft_service=draft_service,
        access_service=None,
        user_id=user_id,
        step="duration",
    )


def build_draft_shortcut() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Draft", callback_data="draft:open")]],
    )


def build_input_mode_actions() -> InlineKeyboardMarkup:
    rows = [
            [InlineKeyboardButton(text=INPUT_MODE_LABELS[mode], callback_data=f"draft:calc:mode:{mode}")]
            for mode in ("auto_pulse", "total_target", "stack_smoothing", "inventory_constrained")
        ]
    rows.append([InlineKeyboardButton(text="✖️ Отмена", callback_data="draft:wizard:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_preset_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"draft:calc:preset:{code}")]
            for code, label in PRESET_LABELS.items()
        ]
    )


def build_preset_actions_with_navigation() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=label, callback_data=f"draft:calc:preset:{code}")] for code, label in PRESET_LABELS.items()]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="draft:wizard:back")])
    rows.append([InlineKeyboardButton(text="✖️ Отмена", callback_data="draft:wizard:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_wizard_navigation_actions(step: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if step not in {"mode"}:
        rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="draft:wizard:back")])
    rows.append([InlineKeyboardButton(text="✖️ Отмена", callback_data="draft:wizard:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_readiness_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Рассчитать preview pulse plan", callback_data="draft:calculate:run")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="draft:wizard:back")],
            [InlineKeyboardButton(text="✖️ Отмена", callback_data="draft:wizard:cancel")],
            [InlineKeyboardButton(text="Сменить preset", callback_data="draft:calculate")],
            [InlineKeyboardButton(text="Draft", callback_data="draft:open")],
        ]
    )


def build_preview_actions(preview_id: UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пересчитать preview", callback_data="draft:calculate:run")],
            [InlineKeyboardButton(text="Course estimate", callback_data=f"draft:estimate:preview:{preview_id}")],
            [InlineKeyboardButton(text="Сменить preset", callback_data="draft:calculate")],
            [InlineKeyboardButton(text="Start protocol", callback_data=f"draft:activate:prepare:{preview_id}")],
            [InlineKeyboardButton(text="Draft", callback_data="draft:open")],
        ]
    )


def build_pre_start_actions(preview_id: UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Confirm start", callback_data=f"draft:activate:confirm:{preview_id}")],
            [InlineKeyboardButton(text="Course estimate", callback_data=f"draft:estimate:preview:{preview_id}")],
            [InlineKeyboardButton(text="Back to preview", callback_data="draft:calculate:run")],
            [InlineKeyboardButton(text="Draft", callback_data="draft:open")],
        ]
    )


def build_active_protocol_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Course estimate", callback_data="draft:estimate:active:latest")],
            [InlineKeyboardButton(text="Draft", callback_data="draft:open")],
        ]
    )


def build_draft_actions(draft: DraftView, *, clear_confirm: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    rows.append(
        [
            InlineKeyboardButton(text="К расчету", callback_data="draft:calculate"),
            InlineKeyboardButton(text="Обновить Draft", callback_data="draft:open"),
        ]
    )

    for idx, item in enumerate(draft.items, start=1):
        rows.append([InlineKeyboardButton(text=f"🗑 Удалить #{idx}", callback_data=f"draft:remove:{item.item_id}")])

    if draft.items:
        if clear_confirm:
            rows.append(
                [
                    InlineKeyboardButton(text="✅ Да, очистить", callback_data="draft:clear:yes"),
                    InlineKeyboardButton(text="↩️ Отмена", callback_data="draft:open"),
                ]
            )
        else:
            rows.append([InlineKeyboardButton(text="Очистить Draft", callback_data="draft:clear:confirm")])
    rows.append([InlineKeyboardButton(text="◀️ К поиску", callback_data="search:back")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _render_draft_summary(draft: DraftView) -> str:
    if not draft.items:
        return (
            "<b>Draft • Рабочая панель</b>\n"
            "Позиции: <b>0</b>\n\n"
            "Добавьте продукты через <b>+Draft</b> в карточке поиска.\n"
            "Следующий шаг: соберите состав и нажмите <b>К расчету</b>."
        )

    lines = ["<b>Draft • Рабочая панель</b>", f"Позиции: <b>{len(draft.items)}</b>", "", "<b>Состав</b>"]
    for idx, item in enumerate(draft.items, start=1):
        label = escape_html_text(item.selected_product_name or "Без названия")
        lines.append(f"{idx}. {label}")
        if item.selected_brand:
            lines.append(f"   ↳ {escape_html_text(item.selected_brand)}")

    if draft.settings:
        mode = INPUT_MODE_LABELS.get(draft.settings.protocol_input_mode or "", "—")
        preset = PRESET_LABELS.get(draft.settings.preset_code or "", "—")
        lines.extend(
            [
                "",
                "<b>Параметры</b>",
                f"• Режим ввода: {mode}",
                f"• Пресет: {preset}",
                f"• Длительность: {draft.settings.duration_weeks or '—'} нед.",
                f"• Цель, мг/нед: {format_decimal_human(draft.settings.weekly_target_total_mg)}",
                f"• Макс. объем инъекции: {format_decimal_human(draft.settings.max_injection_volume_ml)} мл",
                f"• Макс. инъекций/нед: {draft.settings.max_injections_per_week or '—'}",
            ]
        )

    lines.extend(["", "Следующий шаг: проверьте состав и нажмите <b>К расчету</b>."])
    return "\n".join(lines)


async def _render_draft_panel(
    *,
    message: Message,
    state: FSMContext,
    draft: DraftView,
    clear_confirm: bool = False,
) -> None:
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=_render_draft_summary(draft),
        reply_markup=build_draft_actions(draft, clear_confirm=clear_confirm),
        parse_mode=ParseMode.HTML,
    )


async def _render_wizard_panel(
    *,
    message: Message,
    state: FSMContext,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )


def _first_step_for_mode(mode: str) -> str:
    if mode == "auto_pulse":
        return "duration"
    if mode == "total_target":
        return "weekly_target"
    if mode == "stack_smoothing":
        return "stack_target"
    return "inventory_gate"


async def _cancel_wizard(message: Message, state: FSMContext, draft_service: DraftApplicationService, user_id: str) -> None:
    await state.set_state(None)
    await state.update_data(
        **{
            WIZARD_STEP_KEY: None,
            WIZARD_HISTORY_KEY: [],
            WIZARD_MODE_KEY: None,
            "stack_current_product_id": None,
            "stack_pending_product_ids": [],
            "stack_completed_product_ids": [],
            "inventory_current_product_id": None,
            "inventory_pending_product_ids": [],
            "inventory_completed_product_ids": [],
        }
    )
    draft = await draft_service.list_draft(user_id)
    await _render_draft_panel(message=message, state=state, draft=draft)


async def _goto_wizard_step(
    *,
    message: Message,
    state: FSMContext,
    draft_service: DraftApplicationService,
    access_service: AccessEvaluationService | None,
    user_id: str,
    step: str,
    push_history: bool = True,
    current_mode: str | None = None,
) -> None:
    data = await state.get_data()
    if push_history:
        current = data.get(WIZARD_STEP_KEY)
        history = list(data.get(WIZARD_HISTORY_KEY, []))
        if isinstance(current, str):
            history.append(current)
        await state.update_data(**{WIZARD_HISTORY_KEY: history})
    await state.update_data(**{WIZARD_STEP_KEY: step})

    settings = await draft_service.get_draft_settings(user_id)
    mode = current_mode or data.get(WIZARD_MODE_KEY) or (settings.protocol_input_mode if settings else None)

    if step == "mode":
        await state.set_state(CalculationInputState.mode)
        mode_hint = f"\nТекущий режим: <b>{INPUT_MODE_LABELS.get(mode, '—')}</b>." if mode else ""
        await _render_wizard_panel(
            message=message,
            state=state,
            text=f"<b>Calculation setup</b>\nВыберите protocol input mode.{mode_hint}",
            reply_markup=build_input_mode_actions(),
        )
        return

    if mode is None:
        await _goto_wizard_step(
            message=message,
            state=state,
            draft_service=draft_service,
            access_service=access_service,
            user_id=user_id,
            step="mode",
            push_history=False,
        )
        return
    await state.update_data(**{WIZARD_MODE_KEY: mode})

    if step == "inventory_gate":
        if access_service is None:
            await _render_wizard_panel(
                message=message,
                state=state,
                text="Inventory Constrained требует проверки доступа.",
                reply_markup=build_wizard_navigation_actions(step="inventory_gate"),
            )
            return
        decision = await access_service.evaluate(user_id=user_id, entitlement_code="inventory_constrained_access")
        if not decision.allowed:
            await _render_wizard_panel(
                message=message,
                state=state,
                text="Inventory Constrained — advanced paid mode.\nДоступ не активирован.",
                reply_markup=build_wizard_navigation_actions(step="inventory_gate"),
            )
            return
        await _goto_wizard_step(
            message=message,
            state=state,
            draft_service=draft_service,
            access_service=access_service,
            user_id=user_id,
            step="inventory_count",
            push_history=False,
        )
        return

    if step == "weekly_target":
        await state.set_state(CalculationInputState.weekly_target_total_mg)
        current = format_decimal_human(settings.weekly_target_total_mg if settings else None)
        await _render_wizard_panel(
            message=message,
            state=state,
            text=f"<b>Total Target</b>\nУкажите weekly target (mg).\nТекущее значение: <b>{current}</b>.",
            reply_markup=build_wizard_navigation_actions(step="weekly_target"),
        )
        return

    if step == "stack_target":
        await _start_stack_input_flow(message, state, draft_service, user_id)
        return

    if step == "inventory_count":
        await _start_inventory_input_flow(message, state, draft_service, user_id)
        return

    if step == "duration":
        await state.set_state(CalculationInputState.duration_weeks)
        current = settings.duration_weeks if settings else None
        await _render_wizard_panel(
            message=message,
            state=state,
            text=f"<b>{INPUT_MODE_LABELS.get(mode, mode)}</b>\nУкажите длительность (weeks).\nТекущее: <b>{current or '—'}</b>.",
            reply_markup=build_wizard_navigation_actions(step="duration"),
        )
        return

    if step == "preset":
        await state.set_state(CalculationInputState.mode)
        await _render_wizard_panel(
            message=message,
            state=state,
            text="<b>Preset</b>\nВыберите стратегию раскладки pulse plan.",
            reply_markup=build_preset_actions_with_navigation(),
        )
        return

    if step == "max_volume":
        await state.set_state(CalculationInputState.max_injection_volume_ml)
        current = format_decimal_human(settings.max_injection_volume_ml if settings else None)
        await _render_wizard_panel(
            message=message,
            state=state,
            text=f"<b>Ограничение объема</b>\nВведите max injection volume (ml).\nТекущее: <b>{current}</b>.",
            reply_markup=build_wizard_navigation_actions(step="max_volume"),
        )
        return

    if step == "max_injections":
        await state.set_state(CalculationInputState.max_injections_per_week)
        current = settings.max_injections_per_week if settings else None
        await _render_wizard_panel(
            message=message,
            state=state,
            text=f"<b>Ограничение частоты</b>\nВведите max injections per week.\nТекущее: <b>{current or '—'}</b>.",
            reply_markup=build_wizard_navigation_actions(step="max_injections"),
        )
        return

    readiness = await draft_service.get_draft_readiness(user_id)
    await state.set_state(CalculationInputState.mode)
    await _render_wizard_panel(
        message=message,
        state=state,
        text=_render_readiness_summary(readiness, settings=settings),
        reply_markup=build_readiness_actions(),
    )


def _render_readiness_summary(readiness, settings=None) -> str:
    mode = INPUT_MODE_LABELS.get(settings.protocol_input_mode or "", "—") if settings else "—"
    preset = PRESET_LABELS.get(settings.preset_code or "", "—") if settings else "—"
    lines = [
        "<b>Readiness</b>",
        f"Режим: <b>{mode}</b>",
        f"Preset: <b>{preset}</b>",
        readiness.summary,
    ]
    if settings:
        lines.append(f"Ограничения: {format_decimal_human(settings.max_injection_volume_ml)} ml / {settings.max_injections_per_week or '—'} inj/week")
    if not readiness.issues:
        lines.append("✅ Все обязательные параметры заполнены.")
        lines.append("Готово: можно запускать preview.")
        return "\n".join(lines)

    for issue in readiness.issues:
        prefix = "❌" if issue.severity == "error" else "⚠️"
        lines.append(f"{prefix} {issue.message}")
    return "\n".join(lines)


def _render_preview_summary(preview: PulsePlanPreviewView) -> str:
    per_product_weekly = preview.summary_metrics.get("per_product_weekly_target_mg") if preview.summary_metrics else {}
    per_product_weekly = per_product_weekly or {}
    product_aliases = {product_id: f"Продукт {idx}" for idx, product_id in enumerate(per_product_weekly.keys(), start=1)}
    if not product_aliases:
        for entry in preview.entries:
            product_aliases.setdefault(str(entry.product_id), f"Продукт {len(product_aliases) + 1}")

    source_metrics = preview.summary_metrics or {}
    flatness = format_decimal_human(source_metrics.get("flatness_stability_score"))
    injections = format_decimal_human(source_metrics.get("estimated_injections_per_week"))
    max_volume = format_decimal_human(source_metrics.get("max_volume_per_event_ml"))

    lines = [
        "<b>Preview • Pulse Plan</b>",
        f"Статус: <b>{STATUS_LABELS.get(preview.status, compact_status_label(preview.status))}</b>",
        f"Режим: <b>{INPUT_MODE_LABELS.get(preview.protocol_input_mode, preview.protocol_input_mode)}</b>",
        f"Пресет: <b>{PRESET_LABELS.get(preview.preset_applied, preview.preset_applied)}</b>",
        "",
        "<b>Параметры плана</b>",
        f"• Flatness: {flatness}",
        f"• Инъекций/нед: {injections}",
        f"• Макс. объём: {max_volume} мл",
    ]

    if preview.degraded_fallback:
        lines.append("⚠️ Golden Pulse автоматически переведён в Layered Pulse для стабильного расчёта.")

    if per_product_weekly:
        lines.extend(["", "<b>Сводка по продуктам (мг/нед)</b>"])
        for product_id, value in per_product_weekly.items():
            lines.append(f"• {product_aliases[product_id]}: {format_decimal_human(value)}")
    elif preview.entries:
        lines.extend(["", f"Событий в расписании: <b>{len(preview.entries)}</b>"])

    if preview.warning_flags:
        lines.extend(["", "<b>Важные предупреждения</b>"])
        lines.extend(f"• {compact_status_label(flag)}" for flag in preview.warning_flags[:3])

    if preview.entries:
        lines.extend(["", "<b>Schedule preview</b>"])
        for entry in preview.entries[:8]:
            mg = format_decimal_human(entry.computed_mg, precision=1)
            ml = format_decimal_human(entry.volume_ml, precision=2)
            label = product_aliases.get(str(entry.product_id), "Продукт")
            lines.append(f"• День +{entry.day_offset}: {label} — {mg} мг / {ml} мл")
        if len(preview.entries) > 8:
            lines.append(f"… ещё {len(preview.entries) - 8}")

    lines.append("\nЕсли план подходит — откройте оценку курса или запускайте протокол.")
    return "\n".join(lines)


def _render_active_protocol_summary(active: ActiveProtocolView) -> str:
    duration = active.settings_snapshot.get("duration_weeks")
    weekly_target = format_decimal_human(active.settings_snapshot.get("weekly_target_total_mg"))
    flatness = format_decimal_human((active.summary_metrics or {}).get("flatness_stability_score"))
    injections = format_decimal_human((active.summary_metrics or {}).get("estimated_injections_per_week"))
    lines = [
        "<b>✅ Протокол активирован</b>",
        f"Статус: <b>{compact_status_label(active.status)}</b>",
        f"Режим: <b>{INPUT_MODE_LABELS.get(active.protocol_input_mode or '', active.protocol_input_mode or '—')}</b>",
        f"Пресет: <b>{PRESET_LABELS.get(active.settings_snapshot.get('preset_code') or '', active.settings_snapshot.get('preset_code') or '—')}</b>",
        f"Длительность: <b>{duration or '—'} нед.</b>",
        f"Цель: <b>{weekly_target} мг/нед</b>",
        "",
        "<b>Ключевые метрики</b>",
        f"• Flatness: {flatness}",
        f"• Инъекций/нед: {injections}",
        "",
        "Протокол запущен. Можно оценить покрытие курса и вернуться в Draft при необходимости.",
    ]
    return "\n".join(lines)


def _render_pre_start_estimate_snapshot(estimate: CourseEstimate) -> str:
    source_label = "по preview" if estimate.source_type == "preview" else "по активному протоколу"
    lines = [
        "<b>Pre-start checkpoint</b>",
        f"Источник: <b>{source_label}</b>",
        f"Длительность: <b>{estimate.duration_weeks or '—'} нед.</b>",
        f"Продуктов в курсе: <b>{estimate.total_products_count}</b>",
    ]
    if estimate.has_inventory_comparison:
        insufficient = [line for line in estimate.lines if line.inventory_sufficiency_status == "insufficient"]
        if insufficient:
            lines.append("⚠️ Запаса не хватает на полный курс по части позиций.")
            lines.append("Проверьте детализацию в «Course estimate» перед стартом.")
        else:
            lines.append("✅ Текущего запаса достаточно на курс.")
    else:
        lines.append("ℹ️ Сравнение с инвентарём не задано.")
    lines.append("")
    lines.append("Старт не заблокирован — подтвердите запуск, когда будете готовы.")
    return "\n".join(lines)


def _render_course_estimate(estimate: CourseEstimate) -> str:
    insufficient_count = sum(1 for line in estimate.lines if line.inventory_sufficiency_status == "insufficient")
    sufficient_count = sum(1 for line in estimate.lines if line.inventory_sufficiency_status == "sufficient")
    unknown_inventory_count = sum(1 for line in estimate.lines if line.inventory_sufficiency_status == "unknown")
    unsupported_count = sum(1 for line in estimate.lines if line.estimation_status == "unsupported")
    source_label = "по preview" if estimate.source_type == "preview" else "по активному протоколу"
    mode = INPUT_MODE_LABELS.get(estimate.protocol_input_mode or "", "—")

    lines = [
        "<b>Course estimate</b>",
        f"Источник: <b>{source_label}</b>",
        f"Режим: <b>{mode}</b>",
        f"Длительность: <b>{estimate.duration_weeks or '—'} нед.</b>",
        f"Продуктов: <b>{estimate.total_products_count}</b>",
        f"Недостаточно запаса: <b>{insufficient_count}</b>",
        f"Оценка недоступна: <b>{unsupported_count}</b>",
    ]
    if estimate.has_inventory_comparison:
        lines.append(f"Покрывают курс: <b>{sufficient_count}</b>")
        lines.append(f"Не покрывают курс: <b>{insufficient_count}</b>")
        if unknown_inventory_count:
            lines.append(f"Нет данных по запасу: <b>{unknown_inventory_count}</b>")

    lines.extend(["", "<b>По продуктам</b>"])
    for line in estimate.lines:
        lines.append(f"• <b>{escape_html_text(line.product_name)}</b>")
        lines.append(f"  Нужно: {format_decimal_human(line.required_active_mg_total)} мг активного")
        required_form = (
            f"{format_decimal_human(line.required_volume_ml_total)} мл"
            if line.required_volume_ml_total is not None
            else (
                f"{format_decimal_human(line.required_unit_count_total)} ед."
                if line.required_unit_count_total is not None
                else "—"
            )
        )
        lines.append(f"  Форма: {required_form}")
        if line.package_count_required is None or line.package_count_required_rounded is None:
            lines.append("  Упаковки: оценка недоступна")
        else:
            lines.append(
                f"  Нужно упаковок: {format_decimal_human(line.package_count_required)} (~{line.package_count_required_rounded})"
            )
        if estimate.has_inventory_comparison:
            if line.available_package_count is None:
                lines.append("  В наличии: нет данных")
            else:
                lines.append(f"  В наличии: {format_decimal_human(line.available_package_count)} уп.")
            if line.inventory_sufficiency_status == "sufficient":
                lines.append("  Статус: покрывает курс")
            elif line.inventory_sufficiency_status == "insufficient":
                lines.append("  Статус: недостаточно на полный курс")
                shortage = (
                    format_decimal_human(line.shortfall_package_count)
                    if line.shortfall_package_count is not None
                    else "—"
                )
                lines.append(f"  Дефицит: {shortage} уп.")
            else:
                lines.append("  Статус: оценка недоступна")
        if line.estimation_warnings:
            warnings = ", ".join(compact_status_label(flag) for flag in line.estimation_warnings)
            lines.append(f"  Предупреждения: {warnings}")
    return "\n".join(lines)


async def _save_settings_patch(draft_service: DraftApplicationService, user_id: str, **patch) -> None:
    current = await draft_service.get_draft_settings(user_id)
    payload = DraftSettingsInput(
        protocol_input_mode=patch.get("protocol_input_mode", current.protocol_input_mode if current else None),
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


def _parse_inventory_input(value: str | None) -> tuple[Decimal, str] | None:
    if not value:
        return None
    parts = value.strip().split()
    if len(parts) != 2:
        return None
    count = _parse_decimal(parts[0])
    if count is None or count <= Decimal("0"):
        return None
    unit = parts[1].strip().lower()
    if not unit:
        return None
    return count, unit


async def _start_stack_input_flow(
    message: Message,
    state: FSMContext,
    draft_service: DraftApplicationService,
    user_id: str,
) -> None:
    data = await state.get_data()
    draft = await draft_service.list_draft(user_id)
    existing_targets = await draft_service.get_stack_input_targets(user_id, protocol_input_mode="stack_smoothing")
    existing_by_product = {str(target.product_id): target.desired_weekly_mg for target in existing_targets}
    product_names = {
        str(item.product_id): (item.selected_product_name or item.selected_brand or str(item.product_id)) for item in draft.items
    }

    ordered_ids = [str(item.product_id) for item in draft.items]
    pending = [product_id for product_id in ordered_ids if product_id not in existing_by_product]
    if pending:
        current = pending.pop(0)
        await state.set_state(CalculationInputState.stack_product_target)
        await state.update_data(
            stack_current_product_id=current,
            stack_pending_product_ids=pending,
            stack_completed_product_ids=list(data.get("stack_completed_product_ids", [])),
            stack_product_names=product_names,
        )
        await _render_wizard_panel(
            message=message,
            state=state,
            text=f"<b>Stack Smoothing</b>\n{_render_stack_composition(existing_by_product, product_names)}\n\n{_stack_target_prompt(product_names[current])}",
            reply_markup=build_wizard_navigation_actions(step="stack_target"),
        )
        return

    await _goto_wizard_step(
        message=message,
        state=state,
        draft_service=draft_service,
        access_service=None,
        user_id=user_id,
        step="duration",
        push_history=False,
    )


async def _start_inventory_input_flow(
    message: Message,
    state: FSMContext,
    draft_service: DraftApplicationService,
    user_id: str,
) -> None:
    data = await state.get_data()
    draft = await draft_service.list_draft(user_id)
    existing_constraints = await draft_service.get_inventory_constraints(user_id, protocol_input_mode="inventory_constrained")
    existing_by_product = {str(item.product_id): item for item in existing_constraints}
    product_names = {
        str(item.product_id): (item.selected_product_name or item.selected_brand or str(item.product_id)) for item in draft.items
    }
    ordered_ids = [str(item.product_id) for item in draft.items]
    pending = [product_id for product_id in ordered_ids if product_id not in existing_by_product]
    if pending:
        current = pending.pop(0)
        await state.set_state(CalculationInputState.inventory_product_count)
        await state.update_data(
            inventory_current_product_id=current,
            inventory_pending_product_ids=pending,
            inventory_completed_product_ids=list(data.get("inventory_completed_product_ids", [])),
            inventory_product_names=product_names,
        )
        await _render_wizard_panel(
            message=message,
            state=state,
            text=f"<b>Inventory Constrained</b>\n{_render_inventory_composition(existing_by_product, product_names)}\n\n{_inventory_prompt(product_names[current])}",
            reply_markup=build_wizard_navigation_actions(step="inventory_count"),
        )
        return

    await _goto_wizard_step(
        message=message,
        state=state,
        draft_service=draft_service,
        access_service=None,
        user_id=user_id,
        step="duration",
        push_history=False,
    )


def _stack_target_prompt(product_name: str) -> str:
    return f"Stack smoothing: укажите desired weekly mg для '{product_name}'."


def _render_stack_composition(existing_by_product: dict[str, Decimal], product_names: dict[str, str]) -> str:
    lines = ["Текущий stack composition (mg/week):"]
    total = Decimal("0")
    for product_id, product_name in product_names.items():
        value = existing_by_product.get(product_id)
        if value is None:
            lines.append(f"- {product_name}: —")
            continue
        lines.append(f"- {product_name}: {value}")
        total += value
    lines.append(f"Derived total weekly mg: {total}")
    return "\n".join(lines)


def _inventory_prompt(product_name: str) -> str:
    return f"Inventory constrained: укажите остаток для '{product_name}' в формате `<count> <unit>`."


def _render_inventory_composition(existing_by_product: dict[str, object], product_names: dict[str, str]) -> str:
    lines = ["Текущий inventory input:"]
    for product_id, product_name in product_names.items():
        item = existing_by_product.get(product_id)
        if item is None:
            lines.append(f"- {product_name}: —")
            continue
        lines.append(f"- {product_name}: {item.available_count} {item.count_unit}")
    lines.append("Режим best-effort: план будет ограничен доступным остатком.")
    return "\n".join(lines)
