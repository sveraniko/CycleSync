from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.expert_cases import SpecialistCaseAccessError, SpecialistCaseAssemblyService, SpecialistCaseError
from app.application.labs import (
    LabEntryInput,
    LabsApplicationService,
    LabsTriageAccessError,
    LabsTriageError,
    LabsTriageService,
    LabsValidationError,
)
from app.bots.core.flow import delete_user_input_message, safe_edit_or_send
from app.bots.core.formatting import compact_status_label, escape_html_text, format_decimal_human, mask_human_id
from app.bots.core.permissions import has_role

router = Router(name="labs")


class LabsEntryState(StatesGroup):
    report_date = State()
    source_name = State()
    marker_value = State()
    marker_unit = State()
    reference_min = State()
    reference_max = State()
    specialist_note = State()
    specialist_answer = State()


@router.message(F.text.func(lambda value: (value or "").strip().lower() == "labs"))
async def labs_entrypoint(message: Message, state: FSMContext) -> None:
    await _show_labs_root(source_message=message, state=state)


@router.callback_query(F.data == "labs:root")
async def on_labs_root(callback: CallbackQuery, state: FSMContext) -> None:
    await _show_labs_root(source_message=callback.message, state=state)
    await callback.answer()


@router.callback_query(F.data == "labs:new")
async def on_new_report(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(report_id=None, panel_id=None, panel_queue=[], panel_index=0)
    await state.set_state(LabsEntryState.report_date)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_labs_root_panel(notice="🆕 Введите дату отчета в формате <code>YYYY-MM-DD</code>."),
        reply_markup=build_labs_root_actions(_can_access_operator(await state.get_data())),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(LabsEntryState.report_date)
async def on_report_date(message: Message, state: FSMContext) -> None:
    parsed = _parse_date(message.text)
    if parsed is None:
        await safe_edit_or_send(
            state=state,
            source_message=message,
            text=_render_labs_root_panel(notice="Неверная дата. Пример: <code>2026-04-11</code>."),
            reply_markup=build_labs_root_actions(_can_access_operator(await state.get_data())),
            parse_mode=ParseMode.HTML,
        )
        await delete_user_input_message(message)
        return
    await state.update_data(report_date=parsed.isoformat())
    await state.set_state(LabsEntryState.source_name)
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=_render_labs_root_panel(notice="Введите название лаборатории или <code>-</code> чтобы пропустить."),
        reply_markup=build_labs_root_actions(_can_access_operator(await state.get_data())),
        parse_mode=ParseMode.HTML,
    )
    await delete_user_input_message(message)


@router.message(LabsEntryState.source_name)
async def on_report_source(message: Message, state: FSMContext, labs_service: LabsApplicationService) -> None:
    raw = (message.text or "").strip()
    source_name = None if raw in {"", "-"} else raw
    data = await state.get_data()
    report = await labs_service.create_report(
        user_id=_resolve_user_id(message.from_user.id if message.from_user else None),
        report_date=date.fromisoformat(data["report_date"]),
        source_lab_name=source_name,
        notes=None,
    )
    await state.update_data(report_id=str(report.report_id), current_report_date=report.report_date.isoformat())
    await state.set_state(None)
    await _show_report_entry_panel(
        source_message=message,
        state=state,
        notice=f"Отчет создан: <b>{report.report_date.isoformat()}</b>.",
    )
    await delete_user_input_message(message)


@router.callback_query(F.data == "labs:history")
async def on_history(callback: CallbackQuery, state: FSMContext, labs_service: LabsApplicationService) -> None:
    await _show_history_panel(source_message=callback.message, state=state, labs_service=labs_service)
    await callback.answer()


@router.callback_query(F.data.startswith("labs:history:open:"))
async def on_history_open(callback: CallbackQuery, state: FSMContext, labs_service: LabsApplicationService) -> None:
    report_id = UUID(callback.data.split(":")[-1])
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    details = await labs_service.get_report(user_id=user_id, report_id=report_id)
    if details is None:
        await _show_history_panel(
            source_message=callback.message,
            state=state,
            labs_service=labs_service,
            notice="Отчет не найден или недоступен.",
        )
        await callback.answer()
        return
    await state.update_data(report_id=str(details.report.report_id), current_report_date=details.report.report_date.isoformat())
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_report_details_panel(details),
        reply_markup=build_report_details_actions(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "labs:entry")
async def on_report_entry(callback: CallbackQuery, state: FSMContext) -> None:
    await _show_report_entry_panel(source_message=callback.message, state=state)
    await callback.answer()


@router.callback_query(F.data == "labs:entry:panels")
async def on_entry_panels(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_report_entry_panels_panel(),
        reply_markup=build_report_panel_actions(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "labs:entry:ai")
async def on_entry_ai(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_report_entry_ai_panel(),
        reply_markup=build_report_ai_actions(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "labs:entry:actions")
async def on_entry_actions(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_report_entry_actions_panel(),
        reply_markup=build_report_action_actions(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("labs:panel:"))
async def on_panel_selected(callback: CallbackQuery, state: FSMContext, labs_service: LabsApplicationService) -> None:
    panel_code = callback.data.split(":", 2)[2]
    if panel_code in {"skip", "finish"}:
        return
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if report_id_raw is None:
        await _show_report_entry_panel(
            source_message=callback.message,
            state=state,
            notice="Сначала создайте отчет в разделе New report.",
        )
        await callback.answer()
        return
    panels = await labs_service.list_panels()
    panel = next((item for item in panels if item.panel_code == panel_code), None)
    if panel is None:
        await _show_report_entry_panel(
            source_message=callback.message,
            state=state,
            notice="Панель недоступна.",
        )
        await callback.answer()
        return

    markers = await labs_service.list_panel_markers(panel.panel_id)
    if not markers:
        await _show_report_entry_panel(
            source_message=callback.message,
            state=state,
            notice="В этой панели пока нет маркеров.",
        )
        await callback.answer()
        return

    await labs_service.mark_panel_started(
        user_id=_resolve_user_id(callback.from_user.id if callback.from_user else None),
        report_id=UUID(report_id_raw),
        panel_id=panel.panel_id,
    )
    await state.update_data(
        panel_id=str(panel.panel_id),
        panel_name=panel.display_name,
        panel_queue=[str(m.marker_id) for m in markers],
        panel_index=0,
    )
    await _ask_next_marker(callback.message, state, labs_service)
    await callback.answer()


@router.callback_query(F.data == "labs:panel:skip")
async def on_panel_skip(callback: CallbackQuery, state: FSMContext, labs_service: LabsApplicationService) -> None:
    data = await state.get_data()
    idx = int(data.get("panel_index", 0)) + 1
    await state.update_data(panel_index=idx)
    await _ask_next_marker(callback.message, state, labs_service, notice="Маркер пропущен.")
    await callback.answer()


@router.callback_query(F.data == "labs:panel:finish")
async def on_panel_finish(callback: CallbackQuery, state: FSMContext, labs_service: LabsApplicationService) -> None:
    data = await state.get_data()
    panel_id = data.get("panel_id")
    report_id = data.get("report_id")
    if panel_id and report_id:
        await labs_service.mark_panel_completed(
            user_id=_resolve_user_id(callback.from_user.id if callback.from_user else None),
            report_id=UUID(report_id),
            panel_id=UUID(panel_id),
        )
    await state.update_data(panel_queue=[], panel_index=0, current_marker_id=None)
    await _show_report_entry_panel(source_message=callback.message, state=state, notice="Панель завершена.")
    await callback.answer()


@router.message(LabsEntryState.marker_value)
async def on_marker_value(message: Message, state: FSMContext, labs_service: LabsApplicationService) -> None:
    data = await state.get_data()
    marker_id = data.get("current_marker_id")
    if marker_id is None:
        await _show_report_entry_panel(source_message=message, state=state, notice="Маркер не выбран.")
        await delete_user_input_message(message)
        return
    parsed = _parse_decimal(message.text)
    if parsed is None:
        await _render_marker_step(message, state, labs_service, notice="Введите числовое значение, например <code>5.4</code>.")
        await delete_user_input_message(message)
        return
    await state.update_data(current_value=str(parsed))
    await state.set_state(LabsEntryState.marker_unit)
    await _render_marker_step(message, state, labs_service, notice="Теперь введите единицу измерения (как в бланке).")
    await delete_user_input_message(message)


@router.message(LabsEntryState.marker_unit)
async def on_marker_unit(message: Message, state: FSMContext, labs_service: LabsApplicationService) -> None:
    token = (message.text or "").strip()
    if not token:
        await _render_marker_step(message, state, labs_service, notice="Единица измерения обязательна.")
        await delete_user_input_message(message)
        return
    await state.update_data(current_unit=token)
    await state.set_state(LabsEntryState.reference_min)
    await _render_marker_step(
        message,
        state,
        labs_service,
        notice="Введите reference min или <code>-</code> чтобы пропустить.",
    )
    await delete_user_input_message(message)


@router.message(LabsEntryState.reference_min)
async def on_ref_min(message: Message, state: FSMContext, labs_service: LabsApplicationService) -> None:
    token = (message.text or "").strip()
    if token in {"", "-"}:
        await state.update_data(current_ref_min=None)
    else:
        parsed = _parse_decimal(token)
        if parsed is None:
            await _render_marker_step(
                message,
                state,
                labs_service,
                notice="Reference min должен быть числом или <code>-</code>.",
            )
            await delete_user_input_message(message)
            return
        await state.update_data(current_ref_min=str(parsed))
    await state.set_state(LabsEntryState.reference_max)
    await _render_marker_step(
        message,
        state,
        labs_service,
        notice="Введите reference max или <code>-</code> чтобы пропустить.",
    )
    await delete_user_input_message(message)


@router.message(LabsEntryState.reference_max)
async def on_ref_max(message: Message, state: FSMContext, labs_service: LabsApplicationService) -> None:
    token = (message.text or "").strip()
    ref_max = None
    if token not in {"", "-"}:
        ref_max = _parse_decimal(token)
        if ref_max is None:
            await _render_marker_step(
                message,
                state,
                labs_service,
                notice="Reference max должен быть числом или <code>-</code>.",
            )
            await delete_user_input_message(message)
            return

    data = await state.get_data()
    ref_min_raw = data.get("current_ref_min")
    ref_min = Decimal(ref_min_raw) if ref_min_raw is not None else None

    try:
        await labs_service.add_entry(
            user_id=_resolve_user_id(message.from_user.id if message.from_user else None),
            report_id=UUID(data["report_id"]),
            entry=LabEntryInput(
                marker_id=UUID(data["current_marker_id"]),
                value_text=data["current_value"],
                unit=data["current_unit"],
                reference_min=ref_min,
                reference_max=ref_max,
            ),
        )
    except LabsValidationError as exc:
        await _render_marker_step(message, state, labs_service, notice=f"Ошибка валидации: {escape_html_text(str(exc))}")
        await delete_user_input_message(message)
        return

    await state.update_data(panel_index=int(data.get("panel_index", 0)) + 1)
    await _ask_next_marker(message, state, labs_service, notice="Маркер сохранен ✅")
    await delete_user_input_message(message)


@router.callback_query(F.data == "labs:finish")
async def on_finish_report(callback: CallbackQuery, state: FSMContext, labs_service: LabsApplicationService) -> None:
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if not report_id_raw:
        await _show_report_entry_panel(source_message=callback.message, state=state, notice="Нет активного отчета.")
        await callback.answer()
        return
    await labs_service.finalize_report(
        user_id=_resolve_user_id(callback.from_user.id if callback.from_user else None), report_id=UUID(report_id_raw)
    )
    await state.update_data(report_id=None)
    await _show_labs_root(source_message=callback.message, state=state, notice="Отчет финализирован ✅")
    await callback.answer()


@router.callback_query(F.data == "labs:triage:run")
async def on_run_triage(
    callback: CallbackQuery, state: FSMContext, labs_triage_service: LabsTriageService
) -> None:
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if not report_id_raw:
        await _show_labs_root(source_message=callback.message, state=state, notice="Нет активного отчета для triage.")
        await callback.answer()
        return
    try:
        triage = await labs_triage_service.run_triage(
            user_id=_resolve_user_id(callback.from_user.id if callback.from_user else None),
            report_id=UUID(report_id_raw),
        )
    except LabsTriageAccessError as exc:
        await _show_report_entry_panel(source_message=callback.message, state=state, notice=escape_html_text(str(exc)))
        await callback.answer()
        return
    except LabsTriageError as exc:
        await _show_report_entry_panel(
            source_message=callback.message,
            state=state,
            notice=f"Triage не выполнен: {escape_html_text(str(exc))}",
        )
        await callback.answer()
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_format_triage_result(triage),
        reply_markup=build_report_ai_actions(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Готово")


@router.callback_query(F.data == "labs:triage:regenerate")
async def on_regenerate_triage(
    callback: CallbackQuery, state: FSMContext, labs_triage_service: LabsTriageService
) -> None:
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if not report_id_raw:
        await _show_report_entry_panel(source_message=callback.message, state=state, notice="Нет активного отчета.")
        await callback.answer()
        return
    try:
        triage = await labs_triage_service.run_triage(
            user_id=_resolve_user_id(callback.from_user.id if callback.from_user else None),
            report_id=UUID(report_id_raw),
            regenerate=True,
        )
    except LabsTriageAccessError as exc:
        await _show_report_entry_panel(source_message=callback.message, state=state, notice=escape_html_text(str(exc)))
        await callback.answer()
        return
    except LabsTriageError as exc:
        await _show_report_entry_panel(
            source_message=callback.message,
            state=state,
            notice=f"Regenerate не выполнен: {escape_html_text(str(exc))}",
        )
        await callback.answer()
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_format_triage_result(triage),
        reply_markup=build_report_ai_actions(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Готово")


@router.callback_query(F.data == "labs:triage:latest")
async def on_latest_triage(
    callback: CallbackQuery, state: FSMContext, labs_triage_service: LabsTriageService
) -> None:
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if not report_id_raw:
        await _show_report_entry_panel(source_message=callback.message, state=state, notice="Нет активного отчета.")
        await callback.answer()
        return
    triage = await labs_triage_service.get_latest_triage(
        user_id=_resolve_user_id(callback.from_user.id if callback.from_user else None),
        report_id=UUID(report_id_raw),
    )
    if triage is None:
        await _show_report_entry_panel(
            source_message=callback.message,
            state=state,
            notice="Для этого отчета triage пока не запускался.",
        )
        await callback.answer()
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_format_triage_result(triage),
        reply_markup=build_report_ai_actions(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "labs:case:consult")
async def on_consult_specialist(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if not report_id_raw:
        await _show_report_entry_panel(
            source_message=callback.message,
            state=state,
            notice="Нет активного отчета для консультации.",
        )
        await callback.answer()
        return
    await state.set_state(LabsEntryState.specialist_note)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_specialist_note_prompt(),
        reply_markup=build_case_prompt_actions(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(LabsEntryState.specialist_note)
async def on_specialist_note(
    message: Message,
    state: FSMContext,
    specialist_case_service: SpecialistCaseAssemblyService,
) -> None:
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if not report_id_raw:
        await _show_report_entry_panel(source_message=message, state=state, notice="Нет активного отчета.")
        await state.set_state(None)
        await delete_user_input_message(message)
        return

    note = (message.text or "").strip()
    if note == "-":
        note = ""

    try:
        opened = await specialist_case_service.open_case(
            user_id=_resolve_user_id(message.from_user.id if message.from_user else None),
            lab_report_id=UUID(report_id_raw),
            notes_from_user=note,
        )
    except SpecialistCaseAccessError:
        await _show_report_entry_panel(
            source_message=message,
            state=state,
            notice="Консультация специалиста недоступна для вашего доступа.",
        )
        await state.set_state(None)
        await delete_user_input_message(message)
        return
    except SpecialistCaseError as exc:
        await _show_report_entry_panel(
            source_message=message,
            state=state,
            notice=f"Не удалось открыть кейс: {escape_html_text(str(exc))}",
        )
        await state.set_state(None)
        await delete_user_input_message(message)
        return

    await state.set_state(None)
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=_render_specialist_case_opened(opened),
        reply_markup=build_case_actions(),
        parse_mode=ParseMode.HTML,
    )
    await delete_user_input_message(message)


@router.callback_query(F.data == "labs:case:list")
async def on_list_specialist_cases(
    callback: CallbackQuery,
    state: FSMContext,
    specialist_case_service: SpecialistCaseAssemblyService,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    items = await specialist_case_service.list_user_cases(user_id=user_id, limit=10)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_specialist_case_list_panel(items),
        reply_markup=build_case_actions(items),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "labs:case:latest")
async def on_latest_specialist_case(
    callback: CallbackQuery,
    state: FSMContext,
    specialist_case_service: SpecialistCaseAssemblyService,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    item = await specialist_case_service.get_latest_user_case(user_id=user_id)
    if item is None:
        await safe_edit_or_send(
            state=state,
            source_message=callback.message,
            text=_render_specialist_case_list_panel([]),
            reply_markup=build_case_actions(),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return
    detail = await specialist_case_service.get_user_case_detail(user_id=user_id, case_id=item.case_id)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_specialist_case_detail(item, detail),
        reply_markup=build_case_actions([item]),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("labs:case:open:"))
async def on_open_specialist_case(
    callback: CallbackQuery,
    state: FSMContext,
    specialist_case_service: SpecialistCaseAssemblyService,
) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    case_id = UUID(callback.data.split(":")[-1])
    detail = await specialist_case_service.get_user_case_detail(user_id=user_id, case_id=case_id)
    if detail is None:
        await callback.answer("Кейс не найден", show_alert=True)
        return
    item = await specialist_case_service.get_latest_user_case(user_id=user_id)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_specialist_case_detail(item, detail),
        reply_markup=build_case_actions(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "labs:ops:menu")
async def on_specialist_ops_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_operator_access(callback, state):
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text="<b>Operator / Specialist</b>\nСтатусы и обработка кейсов без лишнего шума.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Awaiting cases", callback_data="labs:ops:awaiting")],
                [InlineKeyboardButton(text="← Labs", callback_data="labs:root")],
            ]
        ),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "labs:ops:awaiting")
async def on_specialist_ops_awaiting(
    callback: CallbackQuery,
    state: FSMContext,
    specialist_case_service: SpecialistCaseAssemblyService,
) -> None:
    if not await _ensure_operator_access(callback, state):
        return
    items = await specialist_case_service.list_awaiting_cases(limit=10)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_awaiting_cases_panel(items),
        reply_markup=build_ops_awaiting_actions(items),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("labs:ops:open:"))
async def on_specialist_ops_open_case(
    callback: CallbackQuery,
    state: FSMContext,
    specialist_case_service: SpecialistCaseAssemblyService,
) -> None:
    if not await _ensure_operator_access(callback, state):
        return
    case_id = UUID(callback.data.split(":")[-1])
    detail = await specialist_case_service.get_case_detail(case_id=case_id)
    if detail is None:
        await callback.answer("Кейс не найден", show_alert=True)
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_ops_case_detail(detail),
        reply_markup=build_operator_actions(str(detail.case.case_id)),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("labs:ops:take:"))
async def on_specialist_ops_take_case(
    callback: CallbackQuery,
    state: FSMContext,
    specialist_case_service: SpecialistCaseAssemblyService,
) -> None:
    if not await _ensure_operator_access(callback, state):
        return
    case_id = UUID(callback.data.split(":")[-1])
    specialist_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    try:
        detail = await specialist_case_service.take_case_in_review(case_id=case_id, specialist_id=specialist_id)
    except SpecialistCaseError as exc:
        await callback.answer(f"Ошибка: {exc}", show_alert=True)
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_ops_case_detail(detail, notice="Кейс взят в работу."),
        reply_markup=build_operator_actions(str(detail.case.case_id)),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("labs:ops:answer:"))
async def on_specialist_ops_answer_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_operator_access(callback, state):
        return
    case_id = callback.data.split(":")[-1]
    await state.update_data(specialist_answer_case_id=case_id)
    await state.set_state(LabsEntryState.specialist_answer)
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text="<b>Ответ специалиста</b>\nВведите текст ответа одним сообщением.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="← Awaiting", callback_data="labs:ops:awaiting")]]
        ),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(LabsEntryState.specialist_answer)
async def on_specialist_ops_answer_submit(
    message: Message,
    state: FSMContext,
    specialist_case_service: SpecialistCaseAssemblyService,
) -> None:
    data = await state.get_data()
    case_id_raw = data.get("specialist_answer_case_id")
    if not case_id_raw:
        await state.set_state(None)
        await delete_user_input_message(message)
        return
    specialist_id = _resolve_user_id(message.from_user.id if message.from_user else None)
    text = (message.text or "").strip()
    try:
        response = await specialist_case_service.submit_specialist_response(
            case_id=UUID(case_id_raw),
            specialist_id=specialist_id,
            response_text=text,
            response_summary=text[:120] if text else None,
            is_final=True,
        )
    except SpecialistCaseError as exc:
        await safe_edit_or_send(
            state=state,
            source_message=message,
            text=f"<b>Не удалось сохранить ответ</b>\n{escape_html_text(str(exc))}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Awaiting", callback_data="labs:ops:awaiting")]]
            ),
            parse_mode=ParseMode.HTML,
        )
        await state.set_state(None)
        await delete_user_input_message(message)
        return
    await state.set_state(None)
    await safe_edit_or_send(
        state=state,
        source_message=message,
        text=f"<b>Ответ сохранен</b>\nID: <code>{mask_human_id(response.response_id)}</code>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="← Awaiting", callback_data="labs:ops:awaiting")]]
        ),
        parse_mode=ParseMode.HTML,
    )
    await delete_user_input_message(message)


@router.callback_query(F.data.startswith("labs:ops:close:"))
async def on_specialist_ops_close_case(
    callback: CallbackQuery,
    state: FSMContext,
    specialist_case_service: SpecialistCaseAssemblyService,
) -> None:
    if not await _ensure_operator_access(callback, state):
        return
    case_id = UUID(callback.data.split(":")[-1])
    try:
        detail = await specialist_case_service.close_case(case_id=case_id)
    except SpecialistCaseError as exc:
        await callback.answer(f"Ошибка: {exc}", show_alert=True)
        return
    await safe_edit_or_send(
        state=state,
        source_message=callback.message,
        text=_render_ops_case_detail(detail, notice="Кейс закрыт."),
        reply_markup=build_operator_actions(str(detail.case.case_id)),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


async def _show_labs_root(source_message: Message, state: FSMContext, notice: str | None = None) -> None:
    data = await state.get_data()
    can_access_operator = _can_access_operator(data)
    await safe_edit_or_send(
        state=state,
        source_message=source_message,
        text=_render_labs_root_panel(notice=notice, active_report_date=data.get("current_report_date")),
        reply_markup=build_labs_root_actions(can_access_operator),
        parse_mode=ParseMode.HTML,
    )


async def _show_report_entry_panel(source_message: Message, state: FSMContext, notice: str | None = None) -> None:
    data = await state.get_data()
    await safe_edit_or_send(
        state=state,
        source_message=source_message,
        text=_render_report_entry_root_panel(data.get("current_report_date"), notice=notice),
        reply_markup=build_report_entry_actions(),
        parse_mode=ParseMode.HTML,
    )


async def _show_history_panel(
    source_message: Message,
    state: FSMContext,
    labs_service: LabsApplicationService,
    notice: str | None = None,
) -> None:
    user_id = _resolve_user_id(source_message.from_user.id if source_message.from_user else None)
    reports = await labs_service.list_history(user_id)
    details = []
    for report in reports[:8]:
        report_detail = await labs_service.get_report(user_id=user_id, report_id=report.report_id)
        marker_count = len(report_detail.entries) if report_detail else 0
        details.append((report, marker_count))
    await safe_edit_or_send(
        state=state,
        source_message=source_message,
        text=_render_history_panel(details, notice=notice),
        reply_markup=build_history_actions(details),
        parse_mode=ParseMode.HTML,
    )


async def _ask_next_marker(
    message: Message,
    state: FSMContext,
    labs_service: LabsApplicationService,
    notice: str | None = None,
) -> None:
    data = await state.get_data()
    queue = data.get("panel_queue", [])
    idx = int(data.get("panel_index", 0))
    if idx >= len(queue):
        panel_id_raw = data.get("panel_id")
        report_id_raw = data.get("report_id")
        if panel_id_raw and report_id_raw:
            await labs_service.mark_panel_completed(
                user_id=_resolve_user_id(message.from_user.id if message.from_user else None),
                report_id=UUID(report_id_raw),
                panel_id=UUID(panel_id_raw),
            )
        await state.set_state(None)
        await _show_report_entry_panel(source_message=message, state=state, notice="Маркеры панели заполнены.")
        return

    marker_id = UUID(queue[idx])
    marker = await labs_service.repository.get_marker(marker_id)
    if marker is None:
        await state.update_data(panel_index=idx + 1)
        await _ask_next_marker(message, state, labs_service, notice=notice)
        return

    await state.update_data(current_marker_id=str(marker.marker_id), current_marker_name=marker.display_name)
    await state.set_state(LabsEntryState.marker_value)
    await _render_marker_step(message, state, labs_service, notice=notice)


async def _render_marker_step(
    source_message: Message,
    state: FSMContext,
    labs_service: LabsApplicationService,
    notice: str | None,
) -> None:
    data = await state.get_data()
    marker_id = data.get("current_marker_id")
    marker = await labs_service.repository.get_marker(UUID(marker_id)) if marker_id else None
    idx = int(data.get("panel_index", 0))
    queue = data.get("panel_queue", [])
    await safe_edit_or_send(
        state=state,
        source_message=source_message,
        text=_render_marker_panel(
            marker=marker,
            panel_name=data.get("panel_name"),
            index=idx + 1,
            total=len(queue),
            state_name=str(await state.get_state() or ""),
            notice=notice,
        ),
        reply_markup=build_panel_marker_actions(),
        parse_mode=ParseMode.HTML,
    )


def build_labs_root_actions(can_access_operator: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🆕 New report", callback_data="labs:new")],
        [InlineKeyboardButton(text="📂 Report workspace", callback_data="labs:entry")],
        [InlineKeyboardButton(text="🕘 History", callback_data="labs:history")],
        [InlineKeyboardButton(text="🤖 Run AI triage", callback_data="labs:triage:run")],
        [InlineKeyboardButton(text="👩‍⚕️ Consult specialist", callback_data="labs:case:consult")],
        [InlineKeyboardButton(text="📨 My specialist cases", callback_data="labs:case:list")],
    ]
    if can_access_operator:
        rows.append([InlineKeyboardButton(text="🛠 Operator", callback_data="labs:ops:menu")])
    rows.append([InlineKeyboardButton(text="🏠 Главная", callback_data="nav:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_report_entry_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Panels", callback_data="labs:entry:panels")],
            [InlineKeyboardButton(text="AI", callback_data="labs:entry:ai")],
            [InlineKeyboardButton(text="Actions", callback_data="labs:entry:actions")],
            [InlineKeyboardButton(text="← Back to Labs", callback_data="labs:root")],
        ]
    )


def build_report_panel_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Male hormones", callback_data="labs:panel:male_hormones")],
            [InlineKeyboardButton(text="Hematology / blood thickness", callback_data="labs:panel:hematology")],
            [InlineKeyboardButton(text="Lipids", callback_data="labs:panel:lipids")],
            [InlineKeyboardButton(text="Liver", callback_data="labs:panel:liver")],
            [InlineKeyboardButton(text="Metabolic", callback_data="labs:panel:metabolic")],
            [InlineKeyboardButton(text="GH-related", callback_data="labs:panel:gh_related")],
            [InlineKeyboardButton(text="← Report workspace", callback_data="labs:entry")],
        ]
    )


def build_report_ai_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Run triage", callback_data="labs:triage:run")],
            [InlineKeyboardButton(text="Latest triage", callback_data="labs:triage:latest")],
            [InlineKeyboardButton(text="Regenerate", callback_data="labs:triage:regenerate")],
            [InlineKeyboardButton(text="← Report workspace", callback_data="labs:entry")],
        ]
    )


def build_report_action_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Finalize report", callback_data="labs:finish")],
            [InlineKeyboardButton(text="Consult specialist", callback_data="labs:case:consult")],
            [InlineKeyboardButton(text="← Report workspace", callback_data="labs:entry")],
        ]
    )


def build_report_details_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Open workspace", callback_data="labs:entry")],
            [InlineKeyboardButton(text="Run triage", callback_data="labs:triage:run")],
            [InlineKeyboardButton(text="← History", callback_data="labs:history")],
        ]
    )


def build_panel_marker_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Skip marker", callback_data="labs:panel:skip")],
            [InlineKeyboardButton(text="Finish panel", callback_data="labs:panel:finish")],
        ]
    )


def build_case_actions(items: list | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="Latest case", callback_data="labs:case:latest")]]
    for item in (items or [])[:5]:
        rows.append(
            [InlineKeyboardButton(text=f"Case {mask_human_id(item.case_id)}", callback_data=f"labs:case:open:{item.case_id}")]
        )
    rows.append([InlineKeyboardButton(text="← Labs", callback_data="labs:root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_case_prompt_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="← Back", callback_data="labs:entry:actions")]]
    )


def build_history_actions(items: list[tuple] | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for report, _ in (items or [])[:8]:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Open {report.report_date.isoformat()} · {mask_human_id(report.report_id)}",
                    callback_data=f"labs:history:open:{report.report_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="← Labs", callback_data="labs:root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_ops_awaiting_actions(items: list | None = None) -> InlineKeyboardMarkup:
    rows = []
    for item in (items or [])[:8]:
        rows.append([InlineKeyboardButton(text=f"Open {mask_human_id(item.case_id)}", callback_data=f"labs:ops:open:{item.case_id}")])
    rows.append([InlineKeyboardButton(text="← Operator", callback_data="labs:ops:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_operator_actions(case_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Take in review", callback_data=f"labs:ops:take:{case_id}")],
            [InlineKeyboardButton(text="Submit answer", callback_data=f"labs:ops:answer:{case_id}")],
            [InlineKeyboardButton(text="Close case", callback_data=f"labs:ops:close:{case_id}")],
            [InlineKeyboardButton(text="Back to awaiting", callback_data="labs:ops:awaiting")],
        ]
    )


def _resolve_user_id(telegram_user_id: int | None) -> str:
    if telegram_user_id is None:
        return "anonymous"
    return str(telegram_user_id)


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None


def _parse_decimal(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    token = raw.strip().replace(",", ".")
    if not token:
        return None
    try:
        return Decimal(token)
    except InvalidOperation:
        return None


def _render_labs_root_panel(notice: str | None = None, active_report_date: str | None = None) -> str:
    lines = ["<b>Labs</b>", "Единая панель для отчетов, triage и консультаций."]
    lines.append(f"Активный отчет: <b>{escape_html_text(active_report_date or 'нет')}</b>")
    if notice:
        lines.extend(["", notice])
    return "\n".join(lines)


def _render_report_entry_root_panel(report_date: str | None, notice: str | None = None) -> str:
    lines = [
        "<b>Report workspace</b>",
        f"Отчет: <b>{escape_html_text(report_date or 'не выбран')}</b>",
        "Выберите раздел: панели, AI или действия.",
    ]
    if notice:
        lines.extend(["", notice])
    return "\n".join(lines)


def _render_report_entry_panels_panel() -> str:
    return "<b>Panels</b>\nЗаполняйте маркеры по группам без спама в чате."


def _render_report_entry_ai_panel() -> str:
    return "<b>AI triage</b>\nЗапуск, просмотр и перегенерация triage для активного отчета."


def _render_report_entry_actions_panel() -> str:
    return "<b>Actions</b>\nФинализация отчета и передача кейса специалисту."


def _render_history_panel(items: list[tuple], notice: str | None = None) -> str:
    lines = ["<b>History</b>"]
    if not items:
        lines.append("История пустая. Добавьте первый отчет через New report.")
    else:
        for idx, (report, marker_count) in enumerate(items, start=1):
            protocol = f"protocol {mask_human_id(report.protocol_id)}" if report.protocol_id else "без protocol"
            lines.append(
                f"{idx}. <b>{report.report_date.isoformat()}</b> · {escape_html_text(report.source_lab_name or '—')} · "
                f"{marker_count} марк. · {protocol}"
            )
    if notice:
        lines.extend(["", notice])
    return "\n".join(lines)


def _render_report_details_panel(details) -> str:
    report = details.report
    lines = [
        "<b>Report card</b>",
        f"Дата: <b>{report.report_date.isoformat()}</b>",
        f"Лаборатория: {escape_html_text(report.source_lab_name or '—')}",
        f"Маркеров: <b>{len(details.entries)}</b>",
        f"Статус: {compact_status_label('finalized' if report.finalized_at else 'draft')}",
    ]
    if report.protocol_id:
        lines.append(f"Protocol: <code>{mask_human_id(report.protocol_id)}</code>")
    return "\n".join(lines)


def _render_marker_panel(marker, panel_name: str | None, index: int, total: int, state_name: str, notice: str | None = None) -> str:
    label = marker.display_name if marker else "Маркер"
    units = ", ".join(marker.accepted_units) if marker and marker.accepted_units else "—"
    step_hint = "значение"
    if state_name.endswith("marker_unit"):
        step_hint = "единицу"
    elif state_name.endswith("reference_min"):
        step_hint = "reference min"
    elif state_name.endswith("reference_max"):
        step_hint = "reference max"
    lines = [
        "<b>Panel input</b>",
        f"Панель: <b>{escape_html_text(panel_name or '—')}</b>",
        f"Шаг {index}/{total}: <b>{escape_html_text(label)}</b>",
        f"Единицы: {escape_html_text(units)}",
        f"Сейчас ожидаю: <b>{step_hint}</b>",
    ]
    if notice:
        lines.extend(["", notice])
    return "\n".join(lines)


def _render_specialist_note_prompt() -> str:
    return (
        "<b>Consult specialist</b>\n"
        "Напишите короткий вопрос к врачу или отправьте <code>-</code> без комментария."
    )


def _render_specialist_case_opened(opened) -> str:
    return "\n".join(
        [
            "<b>Кейс открыт ✅</b>",
            f"Case: <code>{mask_human_id(opened.case.case_id)}</code>",
            f"Статус: {compact_status_label(opened.case.case_status)}",
            f"Snapshot: v{opened.snapshot.snapshot_version}",
        ]
    )


def _render_specialist_case_list_panel(items: list) -> str:
    lines = ["<b>Мои кейсы специалиста</b>"]
    if not items:
        lines.append("Пока нет открытых кейсов.")
        return "\n".join(lines)
    for idx, item in enumerate(items[:10], start=1):
        summary = f" · {escape_html_text(item.latest_response_summary)}" if item.latest_response_summary else ""
        lines.append(
            f"{idx}. <code>{mask_human_id(item.case_id)}</code> · {compact_status_label(item.case_status)} · "
            f"{item.lab_report_date or '—'}{summary}"
        )
    return "\n".join(lines)


def _render_specialist_case_detail(item, detail) -> str:
    case = detail.case
    lines = [
        "<b>Case detail</b>",
        f"Case: <code>{mask_human_id(case.case_id)}</code>",
        f"Статус: <b>{compact_status_label(case.case_status)}</b>",
        f"Открыт: {case.opened_at.date().isoformat()}",
        f"Причина: {compact_status_label(case.opened_reason_code)}",
    ]
    if case.notes_from_user:
        lines.append(f"Вопрос: {escape_html_text(case.notes_from_user)}")
    if detail.latest_response:
        lines.extend(
            [
                "",
                "<b>Ответ специалиста</b>",
                escape_html_text(detail.latest_response.response_text),
            ]
        )
    return "\n".join(lines)


def _render_awaiting_cases_panel(items: list) -> str:
    lines = ["<b>Awaiting cases</b>"]
    if not items:
        lines.append("Нет кейсов в ожидании.")
    else:
        for idx, item in enumerate(items[:10], start=1):
            lines.append(f"{idx}. <code>{mask_human_id(item.case_id)}</code> · opened {item.opened_at.date().isoformat()}")
    return "\n".join(lines)


def _render_ops_case_detail(detail, notice: str | None = None) -> str:
    case = detail.case
    lines = [
        "<b>Operator case</b>",
        f"Case: <code>{mask_human_id(case.case_id)}</code>",
        f"Статус: <b>{compact_status_label(case.case_status)}</b>",
        f"Пациент: <code>{mask_human_id(case.user_id)}</code>",
        f"Назначен: {escape_html_text(case.assigned_specialist_id or '—')}",
        f"Комментарий: {escape_html_text(case.notes_from_user or '—')}",
    ]
    if notice:
        lines.extend(["", notice])
    return "\n".join(lines)


def _format_triage_result(result) -> str:
    urgent = "🔴 urgent" if result.run.urgent_flag else "🟢 no urgent"
    severity_order = {"urgent": 0, "warning": 1, "watch": 2}
    sorted_flags = sorted(result.flags, key=lambda flag: severity_order.get(flag.severity.lower(), 3))
    lines = [
        "<b>AI pre-triage</b>",
        f"Статус: <b>{compact_status_label(result.run.triage_status)}</b> · {urgent}",
        f"Summary: {escape_html_text(result.run.summary_text or '—')}",
        "",
        "<b>Flags</b>",
    ]
    if not sorted_flags:
        lines.append("• Нет критичных флагов.")
    for flag in sorted_flags[:8]:
        icon = "🔴" if flag.severity.lower() == "urgent" else "🟠" if flag.severity.lower() == "warning" else "🟡"
        lines.append(f"{icon} <b>{escape_html_text(flag.title)}</b> · {compact_status_label(flag.severity)}")
    if len(sorted_flags) > 8:
        lines.append(f"… и еще {len(sorted_flags) - 8}")
    return "\n".join(lines)


def _can_access_operator(data: dict) -> bool:
    roles = data.get("user_roles")
    return has_role("operator", roles) or has_role("specialist", roles)


async def _ensure_operator_access(callback: CallbackQuery, state: FSMContext) -> bool:
    if _can_access_operator(await state.get_data()):
        return True
    await callback.answer("Недостаточно прав", show_alert=True)
    return False
