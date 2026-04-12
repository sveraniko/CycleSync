from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from uuid import UUID

from app.application.protocols.repository import CourseEstimateSourceData, DraftRepository, EstimatorProductMetadata
from app.application.protocols.schemas import CourseEstimate, CourseEstimateLine, InventoryConstraintView


@dataclass(slots=True)
class _AggregatedRequirement:
    required_active_mg_total: Decimal = Decimal("0")
    required_volume_ml_total: Decimal = Decimal("0")


class CourseEstimatorService:
    def __init__(self, repository: DraftRepository) -> None:
        self.repository = repository

    async def estimate_from_preview(self, preview_id: UUID) -> CourseEstimate:
        source = await self.repository.get_course_estimate_source_from_preview(preview_id)
        if source is None:
            raise ValueError("preview_not_found")
        return self._estimate(source)

    async def estimate_from_active_protocol(self, protocol_id: UUID) -> CourseEstimate:
        source = await self.repository.get_course_estimate_source_from_active_protocol(protocol_id)
        if source is None:
            raise ValueError("active_protocol_not_found")
        return self._estimate(source)

    def _estimate(self, source: CourseEstimateSourceData) -> CourseEstimate:
        aggregated: dict[UUID, _AggregatedRequirement] = defaultdict(_AggregatedRequirement)
        for entry in source.entries:
            aggregated[entry.product_id].required_active_mg_total += entry.computed_mg
            aggregated[entry.product_id].required_volume_ml_total += entry.volume_ml

        inventory_by_product = {constraint.product_id: constraint for constraint in source.inventory_constraints}
        has_inventory = bool(source.inventory_constraints)

        lines: list[CourseEstimateLine] = []
        for product_id in sorted(aggregated.keys(), key=str):
            metadata = source.product_metadata.get(product_id)
            requirement = aggregated[product_id]
            constraint = inventory_by_product.get(product_id)
            line = self._build_line(product_id, metadata, requirement, constraint, has_inventory)
            lines.append(line)

        return CourseEstimate(
            source_type=source.source_type,
            protocol_id=source.protocol_id,
            preview_id=source.preview_id,
            draft_id=source.draft_id,
            protocol_input_mode=source.protocol_input_mode,
            duration_weeks=source.duration_weeks,
            total_products_count=len(lines),
            has_inventory_comparison=has_inventory,
            generated_at=datetime.now(timezone.utc),
            lines=lines,
        )

    def _build_line(
        self,
        product_id: UUID,
        metadata: EstimatorProductMetadata | None,
        requirement: _AggregatedRequirement,
        constraint: InventoryConstraintView | None,
        has_inventory: bool,
    ) -> CourseEstimateLine:
        warnings: list[str] = []
        required_active_mg_total = requirement.required_active_mg_total.quantize(Decimal("0.0001"))
        required_volume_ml_total = requirement.required_volume_ml_total.quantize(Decimal("0.0001"))
        required_unit_count_total: Decimal | None = None
        package_count_required: Decimal | None = None
        package_count_required_rounded: int | None = None
        package_kind = metadata.package_kind if metadata else None

        if metadata is None:
            warnings.append("product_metadata_missing")
        elif package_kind in {"vial", "ampoule"}:
            if metadata.volume_per_package_ml is None or metadata.volume_per_package_ml <= 0:
                warnings.append("volume_per_package_missing")
            else:
                package_count_required = (required_volume_ml_total / metadata.volume_per_package_ml).quantize(Decimal("0.0001"))
        elif package_kind in {"tablet", "capsule"}:
            if metadata.unit_strength_mg is None or metadata.unit_strength_mg <= 0:
                warnings.append("package_estimation_not_supported")
            else:
                required_unit_count_total = (required_active_mg_total / metadata.unit_strength_mg).quantize(Decimal("0.0001"))
                if metadata.units_per_package is None or metadata.units_per_package <= 0:
                    warnings.append("units_per_package_missing")
                else:
                    package_count_required = (required_unit_count_total / metadata.units_per_package).quantize(Decimal("0.0001"))
        else:
            warnings.append("packaging_metadata_missing")

        if package_count_required is not None:
            package_count_required_rounded = int(package_count_required.to_integral_value(rounding=ROUND_CEILING))

        available_active_mg: Decimal | None = None
        available_package_count: Decimal | None = None
        shortfall_active_mg: Decimal | None = None
        shortfall_package_count: Decimal | None = None
        inventory_status = "not_applicable"

        if has_inventory:
            if constraint is None:
                inventory_status = "unknown"
            else:
                available_package_count = constraint.available_count.quantize(Decimal("0.0001"))
                available_active_mg = self._derive_available_active_mg(metadata, constraint)
                if package_count_required_rounded is None:
                    inventory_status = "unknown"
                elif available_package_count >= Decimal(package_count_required_rounded):
                    inventory_status = "sufficient"
                else:
                    inventory_status = "insufficient"
                    shortfall_package_count = (
                        Decimal(package_count_required_rounded) - available_package_count
                    ).quantize(Decimal("0.0001"))
                    if available_active_mg is not None:
                        shortfall_active_mg = max(
                            required_active_mg_total - available_active_mg,
                            Decimal("0"),
                        ).quantize(Decimal("0.0001"))

        estimation_status = "ok" if not warnings else "unsupported"
        return CourseEstimateLine(
            product_id=product_id,
            product_name=metadata.product_name if metadata else "unknown_product",
            required_active_mg_total=required_active_mg_total,
            required_volume_ml_total=required_volume_ml_total if required_volume_ml_total > 0 else None,
            required_unit_count_total=required_unit_count_total,
            package_kind=package_kind,
            package_count_required=package_count_required,
            package_count_required_rounded=package_count_required_rounded,
            available_active_mg=available_active_mg,
            available_package_count=available_package_count,
            inventory_sufficiency_status=inventory_status,
            shortfall_active_mg=shortfall_active_mg,
            shortfall_package_count=shortfall_package_count,
            estimation_status=estimation_status,
            estimation_warnings=warnings,
        )

    @staticmethod
    def _derive_available_active_mg(
        metadata: EstimatorProductMetadata | None,
        constraint: InventoryConstraintView,
    ) -> Decimal | None:
        if metadata is None:
            return None
        package_kind = (metadata.package_kind or "").strip().lower()
        normalized_unit = (constraint.count_unit or "").strip().lower()
        available_count = constraint.available_count
        if package_kind in {"vial", "ampoule"}:
            if normalized_unit not in {"vial", "vials", "ampoule", "ampoules"}:
                return None
            if metadata.volume_per_package_ml is None or metadata.unit_strength_mg is None:
                return None
            return (available_count * metadata.volume_per_package_ml * metadata.unit_strength_mg).quantize(Decimal("0.0001"))
        if package_kind in {"tablet", "capsule"}:
            if normalized_unit not in {"tablet", "tablets", "capsule", "capsules"}:
                return None
            if metadata.unit_strength_mg is None:
                return None
            return (available_count * metadata.unit_strength_mg).quantize(Decimal("0.0001"))
        return None
