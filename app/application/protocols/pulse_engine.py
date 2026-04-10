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
                allocation_mode=None,
                guidance_coverage_score=None,
                calculation_quality_flags=[],
                allocation_details=None,
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

        allocation_context = self._resolve_allocation(products, settings.weekly_target_total_mg or Decimal("0"))
        plans = self._build_plan_products(settings, products, strategy, allocation_context["per_product_mg"])
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
            "allocation_mode": allocation_context["allocation_mode"],
            "per_product_weekly_target_mg": {k: float(v) for k, v in allocation_context["per_product_mg"].items()},
            "guidance_coverage_score": float(allocation_context["guidance_coverage_score"]),
            "allocation_warning_flags": allocation_context["quality_flags"],
            "warning_flags": warning_flags,
            "degraded_fallback": degraded_fallback,
        }
        warning_flags = sorted(set(warning_flags + allocation_context["quality_flags"]))

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
            allocation_mode=allocation_context["allocation_mode"],
            guidance_coverage_score=allocation_context["guidance_coverage_score"],
            calculation_quality_flags=allocation_context["quality_flags"],
            allocation_details=allocation_context["allocation_details"],
            entries=entries,
            validation_issues=[],
        )

    def _build_plan_products(
        self,
        settings: DraftSettingsView,
        products: list[PulseProductProfile],
        strategy: str,
        weekly_mg_by_product: dict[str, Decimal],
    ) -> list[_PlanProduct]:
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
                        weekly_mg=weekly_mg_by_product.get(str(product.product_id), Decimal("0")),
                        injections_per_week=injections,
                        day_interval=day_interval,
                        phase=phase,
                    )
            )
        return output

    def _resolve_allocation(self, products: list[PulseProductProfile], weekly_target_total_mg: Decimal) -> dict:
        sorted_products = sorted(products, key=lambda p: str(p.product_id))
        has_driver = any(any(i.is_pulse_driver for i in product.ingredients) for product in sorted_products)
        half_life_values = [
            self._effective_half_life(product)
            for product in sorted_products
            if any(i.half_life_days and i.half_life_days > 0 for i in product.ingredients)
        ]
        guidance_present = []
        fallback_count = 0
        weighted_inputs: dict[str, Decimal] = {}
        mode = "equal_fallback"

        typical_values: dict[str, Decimal] = {}
        range_values: dict[str, Decimal] = {}
        for product in sorted_products:
            product_key = str(product.product_id)
            typical_total = sum(
                (i.dose_guidance_typical_mg_week or Decimal("0"))
                for i in product.ingredients
                if i.dose_guidance_typical_mg_week and i.dose_guidance_typical_mg_week > 0
            )
            range_mid_total = sum(
                ((i.dose_guidance_min_mg_week or Decimal("0")) + (i.dose_guidance_max_mg_week or Decimal("0"))) / Decimal("2")
                for i in product.ingredients
                if i.dose_guidance_min_mg_week and i.dose_guidance_max_mg_week and i.dose_guidance_min_mg_week > 0 and i.dose_guidance_max_mg_week > 0
            )
            if typical_total > 0:
                typical_values[product_key] = typical_total
                guidance_present.append(True)
            elif range_mid_total > 0:
                range_values[product_key] = range_mid_total
                guidance_present.append(True)
            else:
                guidance_present.append(False)

        if len(typical_values) == len(sorted_products):
            weighted_inputs = typical_values
            mode = "guidance_weighted"
        elif len(typical_values) + len(range_values) > 0:
            mode = "guidance_range_weighted"
            for product in sorted_products:
                key = str(product.product_id)
                if key in typical_values:
                    weighted_inputs[key] = typical_values[key]
                elif key in range_values:
                    weighted_inputs[key] = range_values[key]
                else:
                    fallback_count += 1
                    weighted_inputs[key] = self._driver_half_life_weight(product, has_driver)
        elif has_driver or half_life_values:
            mode = "driver_biased"
            for product in sorted_products:
                weighted_inputs[str(product.product_id)] = self._driver_half_life_weight(product, has_driver)
        else:
            mode = "equal_fallback"
            for product in sorted_products:
                weighted_inputs[str(product.product_id)] = Decimal("1")
            fallback_count = len(sorted_products)

        total_weight = sum(weighted_inputs.values()) or Decimal("1")
        per_product_mg: dict[str, Decimal] = {}
        for idx, product in enumerate(sorted_products):
            key = str(product.product_id)
            if idx == len(sorted_products) - 1:
                allocated = weekly_target_total_mg - sum(per_product_mg.values())
            else:
                allocated = ((weekly_target_total_mg * weighted_inputs[key]) / total_weight).quantize(Decimal("0.0001"))
            per_product_mg[key] = max(Decimal("0"), allocated)

        guidance_coverage = Decimal(str(sum(1 for x in guidance_present if x) / max(len(sorted_products), 1)))
        half_life_coverage = Decimal(
            str(
                sum(
                    1
                    for product in sorted_products
                    if any(i.half_life_days and i.half_life_days > 0 for i in product.ingredients)
                )
                / max(len(sorted_products), 1)
            )
        )
        score = (guidance_coverage * Decimal("0.65") + half_life_coverage * Decimal("0.35")) * Decimal("100")
        if mode == "equal_fallback":
            score -= Decimal("15")
        score = max(Decimal("0"), min(Decimal("100"), score)).quantize(Decimal("0.01"))

        quality_flags: list[str] = []
        if guidance_coverage < Decimal("1"):
            quality_flags.append("dose_guidance_missing_for_some_products")
        if mode == "equal_fallback":
            quality_flags.append("allocation_used_equal_fallback")
        if not has_driver:
            quality_flags.append("pulse_driver_missing")
        if half_life_values and (max(half_life_values) / max(min(half_life_values), Decimal("0.1"))) >= Decimal("6"):
            quality_flags.append("half_life_conflict_detected")

        return {
            "allocation_mode": mode,
            "per_product_mg": per_product_mg,
            "guidance_coverage_score": score,
            "quality_flags": quality_flags,
            "allocation_details": {
                "weights": {k: float(v) for k, v in weighted_inputs.items()},
                "mode": mode,
                "fallback_products_count": fallback_count,
            },
        }

    def _driver_half_life_weight(self, product: PulseProductProfile, has_driver: bool) -> Decimal:
        half_life = self._effective_half_life(product)
        inverse_half_life_component = Decimal("1") / max(half_life, Decimal("0.5"))
        driver_multiplier = Decimal("1")
        if has_driver and any(i.is_pulse_driver for i in product.ingredients):
            driver_multiplier = Decimal("1.35")
        return (driver_multiplier + inverse_half_life_component).quantize(Decimal("0.0001"))

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
