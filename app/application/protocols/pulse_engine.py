from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import exp

from app.application.protocols.schemas import (
    DraftSettingsView,
    PulseCalculationResult,
    PulsePlanEntry,
    PulseProductProfile,
)

VALID_STATUSES = {"success", "success_with_warnings", "degraded_fallback", "failed_validation"}


@dataclass(slots=True)
class _PlanProduct:
    profile: PulseProductProfile
    weekly_mg: Decimal
    injections_per_week: int
    day_interval: int
    phase: int


class PulseCalculationEngine:
    def calculate(
        self,
        *,
        settings: DraftSettingsView | None,
        products: list[PulseProductProfile],
    ) -> PulseCalculationResult:
        validation_issues: list[str] = []
        if settings is None:
            validation_issues.append("settings_missing")
        if not products:
            validation_issues.append("products_missing")

        if settings and not settings.preset_code:
            validation_issues.append("preset_missing")
        if settings and (settings.duration_weeks is None or settings.duration_weeks <= 0):
            validation_issues.append("duration_invalid")
        if settings and (settings.weekly_target_total_mg is None or settings.weekly_target_total_mg <= 0):
            validation_issues.append("weekly_target_invalid")
        if settings and (settings.max_injections_per_week is None or settings.max_injections_per_week <= 0):
            validation_issues.append("max_injections_invalid")
        if settings and (settings.max_injection_volume_ml is None or settings.max_injection_volume_ml <= 0):
            validation_issues.append("max_volume_invalid")

        if validation_issues:
            return PulseCalculationResult(
                status="failed_validation",
                preset_requested=settings.preset_code if settings and settings.preset_code else "unified_rhythm",
                preset_applied=settings.preset_code if settings and settings.preset_code else "unified_rhythm",
                degraded_fallback=False,
                warning_flags=[],
                summary_metrics=None,
                entries=[],
                validation_issues=validation_issues,
                error_message="validation_failed",
            )

        assert settings is not None
        preset_requested = settings.preset_code or "unified_rhythm"
        warning_flags: list[str] = []
        degraded_fallback = False

        strategy = preset_requested
        if strategy == "golden_pulse" and (len(products) > 4 or settings.max_injections_per_week <= 1):
            strategy = "layered_pulse"
            degraded_fallback = True
            warning_flags.append("golden_pulse_fallback_to_layered")

        plans = self._build_plan_products(settings, products, strategy)
        if preset_requested == "golden_pulse" and strategy == "golden_pulse":
            self._optimize_phase_offsets(plans)

        entries, max_volume, estimated_injections = self._generate_entries(settings, plans)
        if max_volume > settings.max_injection_volume_ml:
            warning_flags.append("volume_cap_exceeded")

        if estimated_injections > settings.max_injections_per_week:
            warning_flags.append("injections_above_preference")

        flatness_score = self._calculate_flatness(settings, plans)
        if flatness_score < Decimal("65"):
            warning_flags.append("flatness_below_target")

        summary_metrics = {
            "flatness_stability_score": float(flatness_score),
            "estimated_injections_per_week": estimated_injections,
            "max_volume_per_event_ml": float(max_volume),
            "warning_flags": warning_flags,
            "degraded_fallback": degraded_fallback,
        }

        status = "success"
        if warning_flags:
            status = "success_with_warnings"
        if degraded_fallback:
            status = "degraded_fallback"

        return PulseCalculationResult(
            status=status,
            preset_requested=preset_requested,
            preset_applied=strategy,
            degraded_fallback=degraded_fallback,
            warning_flags=warning_flags,
            summary_metrics=summary_metrics,
            entries=entries,
            validation_issues=[],
        )

    def _build_plan_products(
        self,
        settings: DraftSettingsView,
        products: list[PulseProductProfile],
        strategy: str,
    ) -> list[_PlanProduct]:
        per_product_target = (settings.weekly_target_total_mg or Decimal("0")) / Decimal(max(len(products), 1))
        output: list[_PlanProduct] = []

        for idx, product in enumerate(sorted(products, key=lambda p: str(p.product_id))):
            half_life = self._effective_half_life(product)
            injections = 1
            if strategy == "unified_rhythm":
                anchor = max(self._effective_half_life(p) for p in products)
                injections = max(1, min(settings.max_injections_per_week or 1, int((Decimal("7") / (anchor * Decimal("0.65"))).to_integral_value(rounding=ROUND_HALF_UP))))
            elif strategy == "layered_pulse":
                injections = max(1, int((Decimal("7") / (half_life * Decimal("0.55"))).to_integral_value(rounding=ROUND_HALF_UP)))
                injections = min(injections, settings.max_injections_per_week or injections)
            elif strategy == "golden_pulse":
                injections = max(2, int((Decimal("7") / (half_life * Decimal("0.4"))).to_integral_value(rounding=ROUND_HALF_UP)))
                injections = min(injections, max(2, settings.max_injections_per_week or injections))

            injections = max(1, injections)
            day_interval = max(1, int(round(7 / injections)))
            phase = idx % max(day_interval, 1)

            output.append(
                _PlanProduct(
                    profile=product,
                    weekly_mg=per_product_target,
                    injections_per_week=injections,
                    day_interval=day_interval,
                    phase=phase,
                )
            )
        return output

    def _generate_entries(self, settings: DraftSettingsView, plans: list[_PlanProduct]) -> tuple[list[PulsePlanEntry], Decimal, int]:
        total_days = (settings.duration_weeks or 0) * 7
        entries: list[PulsePlanEntry] = []
        max_volume = Decimal("0")

        for plan in plans:
            mg_per_event = (plan.weekly_mg / Decimal(plan.injections_per_week)).quantize(Decimal("0.0001"))
            concentration = plan.profile.concentration_mg_ml or Decimal("100")
            volume_per_event = (mg_per_event / concentration).quantize(Decimal("0.0001"))
            max_volume = max(max_volume, volume_per_event)
            ingredient_context = ", ".join(i.ingredient_name for i in plan.profile.ingredients[:2]) or None

            for day in range(plan.phase, total_days, plan.day_interval):
                scheduled_day = None
                if settings.planned_start_date:
                    scheduled_day = settings.planned_start_date + timedelta(days=day)
                entries.append(
                    PulsePlanEntry(
                        day_offset=day,
                        scheduled_day=scheduled_day,
                        product_id=plan.profile.product_id,
                        ingredient_context=ingredient_context,
                        volume_ml=volume_per_event,
                        computed_mg=mg_per_event,
                        injection_event_key=f"evt_d{day}",
                        sequence_no=0,
                    )
                )

        entries.sort(key=lambda e: (e.day_offset, str(e.product_id)))
        per_day_counts: dict[int, int] = {}
        for entry in entries:
            count = per_day_counts.get(entry.day_offset, 0)
            entry.sequence_no = count
            per_day_counts[entry.day_offset] = count + 1

        estimated_injections = int(round(len(entries) / max(settings.duration_weeks or 1, 1), 0))
        return entries, max_volume, estimated_injections

    def _calculate_flatness(self, settings: DraftSettingsView, plans: list[_PlanProduct]) -> Decimal:
        days = max((settings.duration_weeks or 1) * 7, 1)
        series = [0.0 for _ in range(days)]
        for day in range(days):
            total = 0.0
            for plan in plans:
                decay = exp(-0.693 * (day % max(plan.day_interval, 1)) / float(self._effective_half_life(plan.profile)))
                total += float(plan.weekly_mg / Decimal("7")) * decay
            series[day] = total
        avg = sum(series) / len(series)
        if avg == 0:
            return Decimal("0")
        variance = sum((x - avg) ** 2 for x in series) / len(series)
        stddev = variance ** 0.5
        coeff = stddev / avg
        score = max(0.0, 100.0 - coeff * 100.0)
        return Decimal(str(score)).quantize(Decimal("0.01"))

    @staticmethod
    def _effective_half_life(product: PulseProductProfile) -> Decimal:
        values = [i.half_life_days for i in product.ingredients if i.half_life_days and i.half_life_days > 0]
        if not values:
            return Decimal("3")
        return sum(values) / Decimal(len(values))

    @staticmethod
    def _optimize_phase_offsets(plans: list[_PlanProduct]) -> None:
        for idx, plan in enumerate(plans):
            plan.phase = (idx * 2) % max(plan.day_interval, 1)
