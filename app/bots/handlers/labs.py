from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types.callback_query import CallbackQuery

from app.application.expert_cases import SpecialistCaseAccessError, SpecialistCaseAssemblyService, SpecialistCaseError
from app.application.labs import (
    LabEntryInput,
    LabsApplicationService,
    LabsTriageError,
    LabsTriageService,
    LabsValidationError,
)

router = Router(name="labs")


class LabsEntryState(StatesGroup):
    report_date = State()
    source_name = State()
    marker_value = State()
    marker_unit = State()
    reference_min = State()
    reference_max = State()
    specialist_note = State()


@router.message(F.text.func(lambda value: (value or "").strip().lower() == "labs"))
async def labs_entrypoint(message: Message) -> None:
    await message.answer("Labs: structured manual input.", reply_markup=build_labs_root_actions())


@router.callback_query(F.data == "labs:new")
async def on_new_report(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(LabsEntryState.report_date)
    await callback.message.answer("Введите дату отчета в формате YYYY-MM-DD.")
    await callback.answer()


@router.message(LabsEntryState.report_date)
async def on_report_date(message: Message, state: FSMContext) -> None:
    parsed = _parse_date(message.text)
    if parsed is None:
        await message.answer("Неверная дата. Используйте YYYY-MM-DD, например 2026-04-11.")
        return
    await state.update_data(report_date=parsed.isoformat())
    await state.set_state(LabsEntryState.source_name)
    await message.answer("Название лаборатории (или '-' чтобы пропустить).")


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
    await state.update_data(report_id=str(report.report_id))
    await state.set_state(None)
    await message.answer(
        f"Отчет создан: {report.report_date.isoformat()}. Выберите panel shortcut.",
        reply_markup=build_report_entry_actions(),
    )


@router.callback_query(F.data == "labs:history")
async def on_history(callback: CallbackQuery, labs_service: LabsApplicationService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    reports = await labs_service.list_history(user_id)
    if not reports:
        await callback.message.answer("История пустая. Добавьте первый report через Labs -> New report.")
        await callback.answer()
        return
    lines = ["Lab history:"]
    for idx, report in enumerate(reports[:15], start=1):
        lines.append(f"{idx}. {report.report_date.isoformat()} | {report.source_lab_name or 'source: —'} | id={report.report_id}")
    await callback.message.answer("\n".join(lines))
    await callback.answer()


@router.callback_query(F.data.startswith("labs:panel:"))
async def on_panel_selected(callback: CallbackQuery, state: FSMContext, labs_service: LabsApplicationService) -> None:
    panel_code = callback.data.split(":", 2)[2]
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if report_id_raw is None:
        await callback.message.answer("Сначала создайте report через Labs -> New report.")
        await callback.answer()
        return
    panels = await labs_service.list_panels()
    panel = next((item for item in panels if item.panel_code == panel_code), None)
    if panel is None:
        await callback.message.answer("Panel недоступна.")
        await callback.answer()
        return

    markers = await labs_service.list_panel_markers(panel.panel_id)
    if not markers:
        await callback.message.answer("Для panel пока нет маркеров.")
        await callback.answer()
        return

    await labs_service.mark_panel_started(
        user_id=_resolve_user_id(callback.from_user.id if callback.from_user else None),
        report_id=UUID(report_id_raw),
        panel_id=panel.panel_id,
    )
    await state.update_data(panel_id=str(panel.panel_id), panel_queue=[str(m.marker_id) for m in markers], panel_index=0)
    await _ask_next_marker(callback.message, state, labs_service)
    await callback.answer()


@router.callback_query(F.data == "labs:panel:skip")
async def on_panel_skip(callback: CallbackQuery, state: FSMContext, labs_service: LabsApplicationService) -> None:
    data = await state.get_data()
    idx = int(data.get("panel_index", 0)) + 1
    await state.update_data(panel_index=idx)
    await _ask_next_marker(callback.message, state, labs_service)
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
    await callback.message.answer("Panel entry завершен.", reply_markup=build_report_entry_actions())
    await callback.answer()


@router.message(LabsEntryState.marker_value)
async def on_marker_value(message: Message, state: FSMContext, labs_service: LabsApplicationService) -> None:
    data = await state.get_data()
    marker_id = data.get("current_marker_id")
    if marker_id is None:
        await message.answer("Маркер не выбран. Откройте panel снова.")
        return
    if _parse_decimal(message.text) is None:
        await message.answer("Введите числовое значение, например 5.4")
        return
    await state.update_data(current_value=(message.text or "").strip())
    await state.set_state(LabsEntryState.marker_unit)
    await message.answer("Введите unit точно как в бланке.")


@router.message(LabsEntryState.marker_unit)
async def on_marker_unit(message: Message, state: FSMContext) -> None:
    token = (message.text or "").strip()
    if not token:
        await message.answer("Unit обязателен.")
        return
    await state.update_data(current_unit=token)
    await state.set_state(LabsEntryState.reference_min)
    await message.answer("Reference min (или '-' чтобы пропустить).")


@router.message(LabsEntryState.reference_min)
async def on_ref_min(message: Message, state: FSMContext) -> None:
    token = (message.text or "").strip()
    if token in {"", "-"}:
        await state.update_data(current_ref_min=None)
    else:
        parsed = _parse_decimal(token)
        if parsed is None:
            await message.answer("Reference min должен быть числом или '-'.")
            return
        await state.update_data(current_ref_min=str(parsed))
    await state.set_state(LabsEntryState.reference_max)
    await message.answer("Reference max (или '-' чтобы пропустить).")


@router.message(LabsEntryState.reference_max)
async def on_ref_max(message: Message, state: FSMContext, labs_service: LabsApplicationService) -> None:
    token = (message.text or "").strip()
    ref_max = None
    if token not in {"", "-"}:
        ref_max = _parse_decimal(token)
        if ref_max is None:
            await message.answer("Reference max должен быть числом или '-'.")
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
        await message.answer(f"Ошибка валидации: {exc}")
        return

    await message.answer("Entry сохранен.")
    await state.update_data(panel_index=int(data.get("panel_index", 0)) + 1)
    await _ask_next_marker(message, state, labs_service)


@router.callback_query(F.data == "labs:finish")
async def on_finish_report(callback: CallbackQuery, state: FSMContext, labs_service: LabsApplicationService) -> None:
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if not report_id_raw:
        await callback.message.answer("Нет активного report.")
        await callback.answer()
        return
    await labs_service.finalize_report(
        user_id=_resolve_user_id(callback.from_user.id if callback.from_user else None), report_id=UUID(report_id_raw)
    )
    await state.clear()
    await callback.message.answer("Report finalized ✅")
    await callback.answer()


@router.callback_query(F.data == "labs:triage:run")
async def on_run_triage(
    callback: CallbackQuery, state: FSMContext, labs_triage_service: LabsTriageService
) -> None:
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if not report_id_raw:
        await callback.message.answer("Нет активного report для triage.")
        await callback.answer()
        return
    await callback.message.answer("Запускаю AI pre-triage…")
    try:
        triage = await labs_triage_service.run_triage(
            user_id=_resolve_user_id(callback.from_user.id if callback.from_user else None),
            report_id=UUID(report_id_raw),
        )
    except LabsTriageError as exc:
        await callback.message.answer(f"Triage не выполнен: {exc}")
        await callback.answer()
        return
    await callback.message.answer(_format_triage_result(triage))
    await callback.answer()


@router.callback_query(F.data == "labs:triage:regenerate")
async def on_regenerate_triage(
    callback: CallbackQuery, state: FSMContext, labs_triage_service: LabsTriageService
) -> None:
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if not report_id_raw:
        await callback.message.answer("Нет активного report для regenerate.")
        await callback.answer()
        return
    await callback.message.answer("Перегенерирую triage…")
    try:
        triage = await labs_triage_service.run_triage(
            user_id=_resolve_user_id(callback.from_user.id if callback.from_user else None),
            report_id=UUID(report_id_raw),
            regenerate=True,
        )
    except LabsTriageError as exc:
        await callback.message.answer(f"Regenerate не выполнен: {exc}")
        await callback.answer()
        return
    await callback.message.answer(_format_triage_result(triage))
    await callback.answer()


@router.callback_query(F.data == "labs:triage:latest")
async def on_latest_triage(
    callback: CallbackQuery, state: FSMContext, labs_triage_service: LabsTriageService
) -> None:
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if not report_id_raw:
        await callback.message.answer("Нет активного report.")
        await callback.answer()
        return
    triage = await labs_triage_service.get_latest_triage(
        user_id=_resolve_user_id(callback.from_user.id if callback.from_user else None),
        report_id=UUID(report_id_raw),
    )
    if triage is None:
        await callback.message.answer("Для этого report triage пока не запускался.")
        await callback.answer()
        return
    await callback.message.answer(_format_triage_result(triage))
    await callback.answer()


@router.callback_query(F.data == "labs:case:consult")
async def on_consult_specialist(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    report_id_raw = data.get("report_id")
    if not report_id_raw:
        await callback.message.answer("Нет активного report для консультации.")
        await callback.answer()
        return
    await state.set_state(LabsEntryState.specialist_note)
    await callback.message.answer("Введите короткий вопрос для специалиста (или '-' чтобы пропустить).")
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
        await message.answer("Нет активного report для консультации.")
        await state.set_state(None)
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
        await message.answer("Consult specialist сейчас недоступен по access policy.")
        await state.set_state(None)
        return
    except SpecialistCaseError as exc:
        await message.answer(f"Не удалось открыть specialist case: {exc}")
        await state.set_state(None)
        return

    await state.set_state(None)
    await message.answer(
        "Specialist case создан\n"
        f"id={opened.case.case_id}\n"
        f"status={opened.case.case_status}\n"
        f"snapshot=v{opened.snapshot.snapshot_version}"
    )


@router.callback_query(F.data == "labs:case:list")
async def on_list_specialist_cases(callback: CallbackQuery, specialist_case_service: SpecialistCaseAssemblyService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    items = await specialist_case_service.list_user_cases(user_id=user_id, limit=10)
    if not items:
        await callback.message.answer("Specialist cases пока нет.")
        await callback.answer()
        return
    lines = ["Your specialist cases:"]
    for idx, item in enumerate(items, start=1):
        lines.append(
            f"{idx}. id={item.case_id} | status={item.case_status} | report_date={item.lab_report_date or '—'}"
        )
    await callback.message.answer("\n".join(lines), reply_markup=build_case_actions())
    await callback.answer()


@router.callback_query(F.data == "labs:case:latest")
async def on_latest_specialist_case(callback: CallbackQuery, specialist_case_service: SpecialistCaseAssemblyService) -> None:
    user_id = _resolve_user_id(callback.from_user.id if callback.from_user else None)
    item = await specialist_case_service.get_latest_user_case(user_id=user_id)
    if item is None:
        await callback.message.answer("Specialist case пока нет.")
        await callback.answer()
        return
    await callback.message.answer(
        "Latest specialist case:\n"
        f"id={item.case_id}\n"
        f"status={item.case_status}\n"
        f"opened_at={item.opened_at.isoformat()}\n"
        f"report_date={item.lab_report_date or '—'}"
    )
    await callback.answer()


async def _ask_next_marker(message: Message, state: FSMContext, labs_service: LabsApplicationService) -> None:
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
        await message.answer("Panel markers закончились.", reply_markup=build_report_entry_actions())
        return

    marker_id = UUID(queue[idx])
    marker = await labs_service.repository.get_marker(marker_id)
    if marker is None:
        await state.update_data(panel_index=idx + 1)
        await _ask_next_marker(message, state, labs_service)
        return

    await state.update_data(current_marker_id=str(marker.marker_id))
    await state.set_state(LabsEntryState.marker_value)
    await message.answer(
        f"{marker.display_name} ({', '.join(marker.accepted_units)}). Введите значение.",
        reply_markup=build_panel_marker_actions(),
    )


def build_labs_root_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="New report", callback_data="labs:new")],
            [InlineKeyboardButton(text="History", callback_data="labs:history")],
            [InlineKeyboardButton(text="My specialist cases", callback_data="labs:case:list")],
        ]
    )


def build_report_entry_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Male hormones", callback_data="labs:panel:male_hormones")],
            [InlineKeyboardButton(text="Hematology / blood thickness", callback_data="labs:panel:hematology")],
            [InlineKeyboardButton(text="Lipids", callback_data="labs:panel:lipids")],
            [InlineKeyboardButton(text="Liver", callback_data="labs:panel:liver")],
            [InlineKeyboardButton(text="Metabolic", callback_data="labs:panel:metabolic")],
            [InlineKeyboardButton(text="GH-related", callback_data="labs:panel:gh_related")],
            [InlineKeyboardButton(text="Run AI triage", callback_data="labs:triage:run")],
            [InlineKeyboardButton(text="Latest triage", callback_data="labs:triage:latest")],
            [InlineKeyboardButton(text="Regenerate triage", callback_data="labs:triage:regenerate")],
            [InlineKeyboardButton(text="Consult specialist", callback_data="labs:case:consult")],
            [InlineKeyboardButton(text="Finish report", callback_data="labs:finish")],
        ]
    )


def build_panel_marker_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Skip marker", callback_data="labs:panel:skip")],
            [InlineKeyboardButton(text="Finish panel", callback_data="labs:panel:finish")],
        ]
    )


def build_case_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Open latest case", callback_data="labs:case:latest")]]
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


def _format_triage_result(result) -> str:
    lines = [
        "AI pre-triage result:",
        f"Status: {result.run.triage_status}",
        f"Urgent: {'YES' if result.run.urgent_flag else 'no'}",
        f"Summary: {result.run.summary_text or '—'}",
        "Flags:",
    ]
    if not result.flags:
        lines.append("- none")
    for flag in result.flags[:10]:
        lines.append(f"- [{flag.severity}] {flag.title} ({flag.flag_code})")
    if len(result.flags) > 10:
        lines.append(f"... and {len(result.flags) - 10} more")
    return "\n".join(lines)
