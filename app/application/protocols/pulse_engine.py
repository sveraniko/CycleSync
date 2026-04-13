from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import exp

from app.application.protocols.pk_v2 import (
    FirstOrderPKEngineV2,
    IngredientPKProfile,
    ProductPKProfile,
    build_simulation_input_from_pulse_plan,
)
from app.application.protocols.schemas import (
    DraftSettingsView,
    InventoryConstraintView,
    PulseCalculationResult,
    PulsePlanEntry,
    PulseProductProfile,
    StackInputTargetView,
)
from app.application.protocols.input_modes import LOCKED_PROTOCOL_INPUT_MODES, is_valid_protocol_input_mode

VALID_STATUSES = {"success", "success_with_warnings", "degraded_fallback", "failed_validation"}


@dataclass(slots=True)
class _PlanProduct:
    profile: PulseProductProfile
    weekly_mg: Decimal
    injections_per_week: int
    day_interval: int
    phase: int


@dataclass(slots=True)
class _HalfLifeResolution:
    value: Decimal
    mode: str


class PulseCalculationEngine:
    def __init__(self, *, pulse_engine_version: str = "v2", pk_engine_v2: FirstOrderPKEngineV2 | None = None) -> None:
        self.pulse_engine_version = pulse_engine_version
        self.pk_engine_v2 = pk_engine_v2 or FirstOrderPKEngineV2()

    def calculate(
        self,
        *,
        settings: DraftSettingsView | None,
        products: list[PulseProductProfile],
        stack_targets: list[StackInputTargetView] | None = None,
        inventory_constraints: list[InventoryConstraintView] | None = None,
    ) -> PulseCalculationResult:
        validation_issues: list[str] = []
        protocol_input_mode = settings.protocol_input_mode if settings else None
        if protocol_input_mode is None:
            protocol_input_mode = "total_target"
        if not is_valid_protocol_input_mode(protocol_input_mode):
            validation_issues.append("protocol_input_mode_invalid")
        if settings is None:
            validation_issues.append("settings_missing")
        if not products:
            validation_issues.append("products_missing")

        if settings and not settings.preset_code:
            validation_issues.append("preset_missing")
        if settings and (settings.duration_weeks is None or settings.duration_weeks <= 0):
            validation_issues.append("duration_invalid")
        if protocol_input_mode == "total_target" and settings and (
            settings.weekly_target_total_mg is None or settings.weekly_target_total_mg <= 0
        ):
            validation_issues.append("weekly_target_invalid")
        if protocol_input_mode == "stack_smoothing":
            target_map = {target.product_id: target for target in (stack_targets or [])}
            if not stack_targets:
                validation_issues.append("stack_targets_missing")
            for product in products:
                target = target_map.get(product.product_id)
                if target is None:
                    validation_issues.append(f"stack_target_missing:{product.product_id}")
                elif target.desired_weekly_mg <= 0:
                    validation_issues.append(f"stack_target_invalid:{product.product_id}")
        if protocol_input_mode == "inventory_constrained":
            inventory_map = {constraint.product_id: constraint for constraint in (inventory_constraints or [])}
            if not inventory_constraints:
                validation_issues.append("inventory_missing_for_some_products")
            for product in products:
                constraint = inventory_map.get(product.product_id)
                if constraint is None:
                    validation_issues.append("inventory_missing_for_some_products")
                    continue
                if constraint.available_count <= 0:
                    validation_issues.append(f"inventory_available_count_invalid:{product.product_id}")
                derived = self._derive_available_active_mg(product, constraint.count_unit, constraint.available_count)
                if derived is None:
                    validation_issues.append(f"inventory_metadata_insufficient:{product.product_id}")
        if protocol_input_mode in LOCKED_PROTOCOL_INPUT_MODES:
            validation_issues.append(f"{protocol_input_mode}_not_yet_available")
        if settings and (settings.max_injections_per_week is None or settings.max_injections_per_week <= 0):
            validation_issues.append("max_injections_invalid")
        if settings and (settings.max_injection_volume_ml is None or settings.max_injection_volume_ml <= 0):
            validation_issues.append("max_volume_invalid")

        if validation_issues:
            return PulseCalculationResult(
                status="failed_validation",
                protocol_input_mode=protocol_input_mode,
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
        if protocol_input_mode == "auto_pulse":
            allocation_context = self._resolve_auto_pulse_allocation(products)
        if protocol_input_mode == "stack_smoothing":
            allocation_context = self._resolve_stack_smoothing_allocation(products, stack_targets or [])
        if protocol_input_mode == "inventory_constrained":
            allocation_context = self._resolve_inventory_constrained_allocation(
                products=products,
                settings=settings,
                inventory_constraints=inventory_constraints or [],
            )
            warning_flags.append("inventory_mode_best_effort")
        plans = self._build_plan_products(settings, products, strategy, allocation_context["per_product_mg"])

        optimization_applied = False
        optimization_gain = Decimal("0.00")
        optimization_before = None
        optimization_after = None
        if preset_requested == "golden_pulse" and strategy == "golden_pulse":
            optimization_before = self._calculate_flatness(settings, plans)
            optimized = self._optimize_phase_offsets(settings, plans)
            optimization_after = self._calculate_flatness(settings, plans)
            optimization_gain = (optimization_after - optimization_before).quantize(Decimal("0.01"))
            optimization_applied = optimized and optimization_gain > Decimal("0")

        entries, max_volume, estimated_injections = self._generate_entries(settings, plans)
        if max_volume > settings.max_injection_volume_ml:
            warning_flags.append("volume_cap_exceeded")

        if estimated_injections > settings.max_injections_per_week:
            warning_flags.append("injections_above_preference")

        flatness_score = self._calculate_flatness(settings, plans)
        simulated_metrics: dict[str, float] = {}
        if self.pulse_engine_version == "v2":
            pk_evaluation = self._evaluate_with_pk_v2(
                settings=settings,
                products=products,
                entries=entries,
                allocation_quality_flags=allocation_context["quality_flags"],
                planning_warning_flags=warning_flags,
            )
            flatness_score = pk_evaluation["flatness_stability_score"]
            simulated_metrics = pk_evaluation["simulated_metrics"]
            warning_flags.extend(pk_evaluation["warning_flags"])
            allocation_context["allocation_details"] = allocation_context.get("allocation_details") or {}
            allocation_context["allocation_details"]["pk_v2_evaluation"] = pk_evaluation["details"]

        if flatness_score < Decimal("65"):
            warning_flags.append("flatness_below_target")

        summary_metrics = {
            "flatness_stability_score": float(flatness_score),
            "pulse_engine_version_used": self.pulse_engine_version,
            "evaluation_source": "pk_v2_simulated" if self.pulse_engine_version == "v2" else "v1_heuristic",
            "estimated_injections_per_week": estimated_injections,
            "max_volume_per_event_ml": float(max_volume),
            "allocation_mode": allocation_context["allocation_mode"],
            "per_product_weekly_target_mg": {k: float(v) for k, v in allocation_context["per_product_mg"].items()},
            "guidance_coverage_score": float(allocation_context["guidance_coverage_score"]),
            "guidance_band_fit_score": float(allocation_context["guidance_band_fit_score"]),
            "effective_half_life_mode": allocation_context["effective_half_life_mode"],
            "half_life_resolution_quality": float(allocation_context["half_life_resolution_quality"]),
            "optimization_applied": optimization_applied,
            "optimization_gain": float(optimization_gain),
            "optimization_flatness_before": float(optimization_before) if optimization_before is not None else None,
            "optimization_flatness_after": float(optimization_after) if optimization_after is not None else None,
            "allocation_warning_flags": allocation_context["quality_flags"],
            "warning_flags": warning_flags,
            "degraded_fallback": degraded_fallback,
        }
        summary_metrics.update(simulated_metrics)
        if protocol_input_mode == "inventory_constrained":
            allocation_details = allocation_context.get("allocation_details") or {}
            summary_metrics["inventory_entered_counts_by_product"] = allocation_details.get("inventory_entered_counts", {})
            summary_metrics["inventory_derived_available_active_mg_by_product"] = allocation_details.get(
                "derived_available_active_mg_per_product", {}
            )
            summary_metrics["inventory_duration_fully_covered"] = allocation_details.get("duration_fully_covered")
            summary_metrics["inventory_feasibility_signal"] = allocation_details.get("feasibility_signal")
        warning_flags = sorted(set(warning_flags + allocation_context["quality_flags"]))

        status = "success"
        if warning_flags:
            status = "success_with_warnings"
        if degraded_fallback:
            status = "degraded_fallback"

        return PulseCalculationResult(
            status=status,
            protocol_input_mode=protocol_input_mode,
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

    def _evaluate_with_pk_v2(
        self,
        *,
        settings: DraftSettingsView,
        products: list[PulseProductProfile],
        entries: list[PulsePlanEntry],
        allocation_quality_flags: list[str],
        planning_warning_flags: list[str],
    ) -> dict:
        product_profiles = self._build_pk_product_profiles(products)
        simulation_input = build_simulation_input_from_pulse_plan(
            draft_id=settings.draft_id,
            planned_start_date=settings.planned_start_date,
            product_profiles=product_profiles,
            plan_entries=entries,
            horizon_days=max((settings.duration_weeks or 1) * 7 + 14, 14),
            resolution_hours=1,
            constraint_forced_longer_interval="injections_above_preference" in planning_warning_flags,
            inventory_forced_degradation="inventory_forced_degraded_layout" in allocation_quality_flags,
        )
        result = self.pk_engine_v2.calculate(simulation_input)
        metrics = result.metrics
        return {
            "flatness_stability_score": metrics.flatness_stability_score,
            "simulated_metrics": {
                "peak_concentration": float(metrics.peak_concentration),
                "trough_concentration": float(metrics.trough_concentration),
                "peak_trough_spread_pct": float(metrics.peak_trough_spread_pct),
                "variability_cv_pct": float(metrics.variability_cv_pct),
            },
            "warning_flags": result.warning_flags,
            "details": {
                "metrics": {
                    "flatness_stability_score": float(metrics.flatness_stability_score),
                    "peak_concentration": float(metrics.peak_concentration),
                    "trough_concentration": float(metrics.trough_concentration),
                    "peak_trough_spread_pct": float(metrics.peak_trough_spread_pct),
                    "variability_cv_pct": float(metrics.variability_cv_pct),
                },
                "warning_flags": result.warning_flags,
                "ingredient_curve_keys": sorted(result.ingredient_curves.keys()),
                "substance_curve_keys": sorted(result.substance_curves.keys()),
            },
        }

    def _build_pk_product_profiles(self, products: list[PulseProductProfile]) -> list[ProductPKProfile]:
        output: list[ProductPKProfile] = []
        for product in products:
            total_known_amount = sum((item.amount_mg or Decimal("0")) for item in product.ingredients)
            ingredients = []
            for ingredient in product.ingredients:
                basis = ingredient.basis or "per_ml"
                amount_per_ml = ingredient.amount_per_ml_mg
                amount_per_unit = ingredient.amount_per_unit_mg
                if basis == "per_ml" and amount_per_ml is None:
                    if product.concentration_mg_ml and ingredient.amount_mg and total_known_amount > 0:
                        amount_per_ml = (
                            product.concentration_mg_ml * ingredient.amount_mg / total_known_amount
                        ).quantize(Decimal("0.0001"))
                    elif ingredient.amount_mg:
                        amount_per_ml = ingredient.amount_mg
                ingredients.append(
                    IngredientPKProfile(
                        ingredient_name=ingredient.ingredient_name,
                        parent_substance=ingredient.parent_substance or ingredient.ingredient_name,
                        basis=basis,
                        amount_per_ml_mg=amount_per_ml,
                        amount_per_unit_mg=amount_per_unit,
                        half_life_days=ingredient.half_life_days or Decimal("3"),
                        active_fraction=ingredient.active_fraction or Decimal("1"),
                        ester_name=ingredient.ester_name,
                        tmax_hours=ingredient.tmax_hours,
                        release_model=ingredient.release_model,
                        is_pulse_driver=ingredient.is_pulse_driver or False,
                    )
                )
            output.append(
                ProductPKProfile(
                    product_id=product.product_id,
                    product_key=(product.product_name or str(product.product_id)).lower().replace(" ", "_"),
                    release_form=(product.package_kind or "injectable").lower(),
                    ingredients=ingredients,
                )
            )
        return output

    def _resolve_stack_smoothing_allocation(
        self, products: list[PulseProductProfile], stack_targets: list[StackInputTargetView]
    ) -> dict:
        by_product = {str(target.product_id): target.desired_weekly_mg for target in stack_targets}
        per_product_mg: dict[str, Decimal] = {}
        for product in sorted(products, key=lambda p: str(p.product_id)):
            per_product_mg[str(product.product_id)] = by_product[str(product.product_id)].quantize(Decimal("0.0001"))
        derived_total = sum(per_product_mg.values())
        return {
            "allocation_mode": "stack_input_fixed",
            "per_product_mg": per_product_mg,
            "guidance_coverage_score": Decimal("100.00"),
            "guidance_band_fit_score": Decimal("100.00"),
            "effective_half_life_mode": "amount_weighted",
            "half_life_resolution_quality": Decimal("1.00"),
            "quality_flags": [],
            "allocation_details": {
                "mode": "stack_input_fixed",
                "per_product_allocated_mg_week": {k: float(v) for k, v in per_product_mg.items()},
                "derived_total_weekly_target_mg": float(derived_total),
            },
        }

    def _resolve_inventory_constrained_allocation(
        self,
        *,
        products: list[PulseProductProfile],
        settings: DraftSettingsView,
        inventory_constraints: list[InventoryConstraintView],
    ) -> dict:
        ideal = self._resolve_auto_pulse_allocation(products)
        inventory_by_product = {str(item.product_id): item for item in inventory_constraints}
        constrained_per_product: dict[str, Decimal] = {}
        derived_active_by_product: dict[str, Decimal] = {}
        quality_flags: list[str] = []
        constrained_count = 0
        duration_weeks = Decimal(str(settings.duration_weeks or 1))

        for product in sorted(products, key=lambda p: str(p.product_id)):
            product_id = str(product.product_id)
            inventory = inventory_by_product[product_id]
            available_active_mg = self._derive_available_active_mg(product, inventory.count_unit, inventory.available_count)
            assert available_active_mg is not None
            derived_active_by_product[product_id] = available_active_mg
            max_weekly = (available_active_mg / duration_weeks).quantize(Decimal("0.0001"))
            ideal_weekly = ideal["per_product_mg"][product_id]
            constrained_weekly = min(ideal_weekly, max_weekly)
            constrained_per_product[product_id] = constrained_weekly
            if constrained_weekly < ideal_weekly:
                constrained_count += 1

        if constrained_count > 0:
            quality_flags.extend(
                [
                    "inventory_insufficient_for_requested_duration",
                    "inventory_forced_degraded_layout",
                ]
            )

        coverage_ratio = Decimal("1.0000")
        ideal_total = sum(ideal["per_product_mg"].values())
        constrained_total = sum(constrained_per_product.values())
        if ideal_total > 0:
            coverage_ratio = (constrained_total / ideal_total).quantize(Decimal("0.0001"))

        return {
            "allocation_mode": "inventory_constrained_best_effort",
            "per_product_mg": constrained_per_product,
            "guidance_coverage_score": ideal["guidance_coverage_score"],
            "guidance_band_fit_score": ideal["guidance_band_fit_score"],
            "effective_half_life_mode": ideal["effective_half_life_mode"],
            "half_life_resolution_quality": ideal["half_life_resolution_quality"],
            "quality_flags": quality_flags,
            "allocation_details": {
                "mode": "inventory_constrained_best_effort",
                "ideal_per_product_mg_week": {k: float(v) for k, v in ideal["per_product_mg"].items()},
                "per_product_allocated_mg_week": {k: float(v) for k, v in constrained_per_product.items()},
                "inventory_entered_counts": {
                    pid: {
                        "available_count": float(item.available_count),
                        "count_unit": item.count_unit,
                    }
                    for pid, item in inventory_by_product.items()
                },
                "derived_available_active_mg_per_product": {k: float(v) for k, v in derived_active_by_product.items()},
                "requested_duration_weeks": int(settings.duration_weeks or 0),
                "duration_fully_covered": coverage_ratio >= Decimal("1.0000"),
                "feasibility_signal": "constrained_best_effort" if constrained_count > 0 else "fully_covered",
                "coverage_ratio": float(coverage_ratio),
            },
        }

    @staticmethod
    def _derive_available_active_mg(
        product: PulseProductProfile, count_unit: str, available_count: Decimal
    ) -> Decimal | None:
        normalized = (count_unit or "").strip().lower()
        package_kind = (product.package_kind or "").strip().lower()
        if package_kind in {"vial", "ampoule"}:
            if normalized not in {"vial", "vials", "ampoule", "ampoules"}:
                return None
            if product.concentration_mg_ml is None or product.volume_per_package_ml is None:
                return None
            return (available_count * product.concentration_mg_ml * product.volume_per_package_ml).quantize(Decimal("0.0001"))
        if package_kind in {"tablet", "capsule"}:
            if normalized not in {"tablet", "tablets", "capsule", "capsules"}:
                return None
            if product.unit_strength_mg is None:
                return None
            return (available_count * product.unit_strength_mg).quantize(Decimal("0.0001"))
        return None

    def _resolve_auto_pulse_allocation(self, products: list[PulseProductProfile]) -> dict:
        sorted_products = sorted(products, key=lambda p: str(p.product_id))
        guidance_values: dict[str, Decimal] = {}
        for product in sorted_products:
            product_key = str(product.product_id)
            typical_total = sum(
                (i.dose_guidance_typical_mg_week or Decimal("0"))
                for i in product.ingredients
                if i.dose_guidance_typical_mg_week and i.dose_guidance_typical_mg_week > 0
            )
            if typical_total > 0:
                guidance_values[product_key] = typical_total
                continue
            range_mid_total = sum(
                ((i.dose_guidance_min_mg_week or Decimal("0")) + (i.dose_guidance_max_mg_week or Decimal("0"))) / Decimal("2")
                for i in product.ingredients
                if i.dose_guidance_min_mg_week
                and i.dose_guidance_max_mg_week
                and i.dose_guidance_min_mg_week > 0
                and i.dose_guidance_max_mg_week > 0
            )
            if range_mid_total > 0:
                guidance_values[product_key] = range_mid_total

        median_guidance = Decimal("100")
        if guidance_values:
            sorted_values = sorted(guidance_values.values())
            median_guidance = sorted_values[len(sorted_values) // 2]

        per_product_mg: dict[str, Decimal] = {}
        fallback_count = 0
        for product in sorted_products:
            key = str(product.product_id)
            if key in guidance_values:
                per_product_mg[key] = guidance_values[key].quantize(Decimal("0.0001"))
            else:
                fallback_count += 1
                per_product_mg[key] = median_guidance.quantize(Decimal("0.0001"))

        quality_flags: list[str] = []
        if fallback_count > 0:
            quality_flags.append("auto_pulse_missing_guidance_for_some_products")
        total_target = sum(per_product_mg.values())
        guidance_coverage_score = Decimal(str((len(guidance_values) / max(len(sorted_products), 1)) * 100)).quantize(Decimal("0.01"))
        return {
            "allocation_mode": "auto_pulse_guidance_driven",
            "per_product_mg": per_product_mg,
            "guidance_coverage_score": guidance_coverage_score,
            "guidance_band_fit_score": Decimal("100.00"),
            "effective_half_life_mode": "amount_weighted",
            "half_life_resolution_quality": Decimal("1.00"),
            "quality_flags": quality_flags,
            "allocation_details": {
                "mode": "auto_pulse_guidance_driven",
                "per_product_allocated_mg_week": {k: float(v) for k, v in per_product_mg.items()},
                "auto_generated_total_weekly_target_mg": float(total_target),
                "fallback_products_count": fallback_count,
            },
        }

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
                injections = max(
                    1,
                    min(
                        settings.max_injections_per_week or 1,
                        int((Decimal("7") / (anchor * Decimal("0.65"))).to_integral_value(rounding=ROUND_HALF_UP)),
                    ),
                )
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

        half_life_resolutions = {str(product.product_id): self._effective_half_life_resolution(product) for product in sorted_products}
        per_product_half_life = {key: float(resolution.value) for key, resolution in half_life_resolutions.items()}
        per_product_half_life_mode = {key: resolution.mode for key, resolution in half_life_resolutions.items()}
        weighted_resolution_count = sum(1 for resolution in half_life_resolutions.values() if resolution.mode == "amount_weighted")
        fallback_resolution_count = len(sorted_products) - weighted_resolution_count
        effective_half_life_mode = "amount_weighted" if fallback_resolution_count == 0 else "mixed_fallback"
        half_life_resolution_quality = Decimal(str(weighted_resolution_count / max(len(sorted_products), 1))).quantize(Decimal("0.01"))

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
                if i.dose_guidance_min_mg_week
                and i.dose_guidance_max_mg_week
                and i.dose_guidance_min_mg_week > 0
                and i.dose_guidance_max_mg_week > 0
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
        guidance_coverage_score = (guidance_coverage * Decimal("0.65") + half_life_coverage * Decimal("0.35")) * Decimal("100")
        if mode == "equal_fallback":
            guidance_coverage_score -= Decimal("15")
        guidance_coverage_score = max(Decimal("0"), min(Decimal("100"), guidance_coverage_score)).quantize(Decimal("0.01"))

        quality_flags: list[str] = []
        if guidance_coverage < Decimal("1"):
            quality_flags.append("dose_guidance_missing_for_some_products")
        if mode == "equal_fallback":
            quality_flags.append("allocation_used_equal_fallback")
        if not has_driver:
            quality_flags.append("pulse_driver_missing")
        if half_life_values and (max(half_life_values) / max(min(half_life_values), Decimal("0.1"))) >= Decimal("6"):
            quality_flags.append("half_life_conflict_detected")

        boundary_results, boundary_summary, guidance_band_fit_score = self._evaluate_guidance_boundaries(sorted_products, per_product_mg)
        if boundary_summary["below_range_count"] > 0:
            quality_flags.append("allocation_below_guidance_for_some_products")
        if boundary_summary["above_range_count"] > 0:
            quality_flags.append("allocation_above_guidance_for_some_products")
        if boundary_summary["below_range_count"] > 0 or boundary_summary["above_range_count"] > 0:
            quality_flags.append("allocation_outside_guidance_band")

        return {
            "allocation_mode": mode,
            "per_product_mg": per_product_mg,
            "guidance_coverage_score": guidance_coverage_score,
            "guidance_band_fit_score": guidance_band_fit_score,
            "effective_half_life_mode": effective_half_life_mode,
            "half_life_resolution_quality": half_life_resolution_quality,
            "quality_flags": quality_flags,
            "allocation_details": {
                "weights": {k: float(v) for k, v in weighted_inputs.items()},
                "mode": mode,
                "fallback_products_count": fallback_count,
                "effective_half_life_mode": effective_half_life_mode,
                "per_product_effective_half_life_days": per_product_half_life,
                "per_product_half_life_resolution_mode": per_product_half_life_mode,
                "per_product_allocated_mg_week": {k: float(v) for k, v in per_product_mg.items()},
                "per_product_guidance_band": boundary_results,
                "guidance_band_fit_score": float(guidance_band_fit_score),
                "boundary_summary": boundary_summary,
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
        stddev = variance**0.5
        coeff = stddev / avg
        score = max(0.0, 100.0 - coeff * 100.0)
        return Decimal(str(score)).quantize(Decimal("0.01"))

    @staticmethod
    def _effective_half_life(product: PulseProductProfile) -> Decimal:
        return PulseCalculationEngine._effective_half_life_resolution(product).value

    @staticmethod
    def _effective_half_life_resolution(product: PulseProductProfile) -> _HalfLifeResolution:
        weighted_sum = Decimal("0")
        weight_total = Decimal("0")

        for ingredient in product.ingredients:
            if not ingredient.half_life_days or ingredient.half_life_days <= 0:
                continue
            amount_weight = ingredient.amount_mg if ingredient.amount_mg and ingredient.amount_mg > 0 else Decimal("0")
            if amount_weight <= 0:
                continue
            if ingredient.is_pulse_driver:
                amount_weight *= Decimal("1.15")
            weighted_sum += ingredient.half_life_days * amount_weight
            weight_total += amount_weight

        if weight_total > 0:
            return _HalfLifeResolution(
                value=(weighted_sum / weight_total).quantize(Decimal("0.0001")),
                mode="amount_weighted",
            )

        simple_values = [i.half_life_days for i in product.ingredients if i.half_life_days and i.half_life_days > 0]
        if simple_values:
            return _HalfLifeResolution(
                value=(sum(simple_values) / Decimal(len(simple_values))).quantize(Decimal("0.0001")),
                mode="arithmetic_fallback",
            )
        return _HalfLifeResolution(value=Decimal("3.0000"), mode="default_fallback")

    def _evaluate_guidance_boundaries(
        self,
        products: list[PulseProductProfile],
        per_product_mg: dict[str, Decimal],
    ) -> tuple[dict[str, dict], dict[str, int], Decimal]:
        boundary_results: dict[str, dict] = {}
        evaluated_count = 0
        in_range_count = 0

        for product in products:
            key = str(product.product_id)
            allocated = per_product_mg.get(key, Decimal("0"))
            expected_min = sum(
                (i.dose_guidance_min_mg_week or Decimal("0"))
                for i in product.ingredients
                if i.dose_guidance_min_mg_week and i.dose_guidance_min_mg_week > 0
            )
            expected_max = sum(
                (i.dose_guidance_max_mg_week or Decimal("0"))
                for i in product.ingredients
                if i.dose_guidance_max_mg_week and i.dose_guidance_max_mg_week > 0
            )

            status = "no_guidance"
            if expected_min > 0 and expected_max > 0 and expected_max >= expected_min:
                evaluated_count += 1
                if allocated < expected_min:
                    status = "below_range"
                elif allocated > expected_max:
                    status = "above_range"
                else:
                    status = "in_range"
                    in_range_count += 1

            boundary_results[key] = {
                "allocated_mg_week": float(allocated),
                "expected_min_mg_week": float(expected_min) if expected_min > 0 else None,
                "expected_max_mg_week": float(expected_max) if expected_max > 0 else None,
                "status": status,
            }

        below_range_count = sum(1 for result in boundary_results.values() if result["status"] == "below_range")
        above_range_count = sum(1 for result in boundary_results.values() if result["status"] == "above_range")
        guidance_band_fit_score = Decimal("100.00")
        if evaluated_count > 0:
            guidance_band_fit_score = (Decimal(in_range_count) / Decimal(evaluated_count) * Decimal("100")).quantize(Decimal("0.01"))

        summary = {
            "evaluated_products_count": evaluated_count,
            "in_range_count": in_range_count,
            "below_range_count": below_range_count,
            "above_range_count": above_range_count,
        }
        return boundary_results, summary, guidance_band_fit_score

    def _optimize_phase_offsets(self, settings: DraftSettingsView, plans: list[_PlanProduct]) -> bool:
        if not plans:
            return False

        original_phases = [plan.phase for plan in plans]
        global_best = self._calculate_flatness(settings, plans)

        for _ in range(3):
            improved_in_pass = False
            for plan in plans:
                start_phase = plan.phase
                best_phase = start_phase
                best_score = global_best

                for candidate in range(max(plan.day_interval, 1)):
                    if candidate == start_phase:
                        continue
                    plan.phase = candidate
                    candidate_score = self._calculate_flatness(settings, plans)
                    if candidate_score > best_score:
                        best_score = candidate_score
                        best_phase = candidate

                plan.phase = best_phase
                if best_score > global_best:
                    global_best = best_score
                    improved_in_pass = True

            if not improved_in_pass:
                break

        final_score = self._calculate_flatness(settings, plans)
        if final_score <= self._calculate_flatness(settings, [
            _PlanProduct(
                profile=plan.profile,
                weekly_mg=plan.weekly_mg,
                injections_per_week=plan.injections_per_week,
                day_interval=plan.day_interval,
                phase=original_phase,
            )
            for plan, original_phase in zip(plans, original_phases, strict=True)
        ]):
            for plan, original_phase in zip(plans, original_phases, strict=True):
                plan.phase = original_phase
            return False

        return True
