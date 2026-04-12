from decimal import Decimal

from app.application.protocols.draft_service import DraftReadinessValidator
from app.application.protocols.input_modes import LOCKED_PROTOCOL_INPUT_MODES
from app.application.protocols.repository import DraftRepository
from app.application.protocols.schemas import DraftReadinessIssue, DraftReadinessResult, DraftView


class ProtocolDraftReadinessService(DraftReadinessValidator):
    def __init__(self, repository: DraftRepository) -> None:
        self.repository = repository

    async def validate(self, draft: DraftView) -> DraftReadinessResult:
        issues: list[DraftReadinessIssue] = []

        settings = await self.repository.get_draft_settings(draft_id=draft.draft_id)
        products = await self.repository.list_calculation_products(draft_id=draft.draft_id)

        if not draft.items:
            issues.append(DraftReadinessIssue(code="draft.empty", severity="error", message="Добавьте минимум один продукт в Draft."))

        if settings is None:
            issues.append(
                DraftReadinessIssue(
                    code="settings.missing",
                    severity="error",
                    message="Не заполнены параметры подготовки к расчету.",
                )
            )
        else:
            selected_mode = settings.protocol_input_mode or "total_target"
            if selected_mode in LOCKED_PROTOCOL_INPUT_MODES:
                issues.append(
                    DraftReadinessIssue(
                        code=f"settings.{selected_mode}.not_available",
                        severity="error",
                        message=f"Режим {selected_mode} пока недоступен в полном расчете.",
                    )
                )
            if selected_mode == "total_target" and (
                settings.weekly_target_total_mg is None or settings.weekly_target_total_mg <= Decimal("0")
            ):
                issues.append(
                    DraftReadinessIssue(
                        code="settings.weekly_target_required",
                        severity="error",
                        message="Укажите weekly target total mg больше 0.",
                    )
                )
            if settings.duration_weeks is None or settings.duration_weeks <= 0:
                issues.append(
                    DraftReadinessIssue(
                        code="settings.duration_required",
                        severity="error",
                        message="Укажите duration в неделях больше 0.",
                    )
                )
            if not settings.preset_code:
                issues.append(
                    DraftReadinessIssue(
                        code="settings.preset_required",
                        severity="error",
                        message="Выберите preset для расчета.",
                    )
                )
            if settings.max_injection_volume_ml is None or settings.max_injection_volume_ml <= Decimal("0"):
                issues.append(
                    DraftReadinessIssue(
                        code="settings.max_volume_required",
                        severity="error",
                        message="Укажите max injection volume (ml) больше 0.",
                    )
                )
            if settings.max_injections_per_week is None or settings.max_injections_per_week <= 0:
                issues.append(
                    DraftReadinessIssue(
                        code="settings.max_injections_required",
                        severity="error",
                        message="Укажите max injections per week больше 0.",
                    )
                )

        for product in products:
            if not product.is_automatable:
                issues.append(
                    DraftReadinessIssue(
                        code="catalog.product_not_automatable",
                        severity="error",
                        message=f"Продукт '{product.product_name}' помечен как non-automatable.",
                        context={"product_id": str(product.product_id)},
                    )
                )
            if not product.has_half_life:
                issues.append(
                    DraftReadinessIssue(
                        code="catalog.half_life_missing",
                        severity="error",
                        message=f"Для '{product.product_name}' отсутствует half-life у ингредиентов.",
                        context={"product_id": str(product.product_id), "ingredients": product.ingredient_names},
                    )
                )

        if settings and settings.max_injections_per_week and settings.duration_weeks:
            if settings.max_injections_per_week > 14:
                issues.append(
                    DraftReadinessIssue(
                        code="constraints.max_injections_too_high",
                        severity="warning",
                        message="max injections per week выглядит слишком высоким для MVP-ограничений.",
                    )
                )

        has_errors = any(issue.severity == "error" for issue in issues)
        summary = "Draft готов к pulse calculation." if not has_errors else "Draft не готов к pulse calculation."
        return DraftReadinessResult(draft_id=draft.draft_id, ready=not has_errors, summary=summary, issues=issues)
