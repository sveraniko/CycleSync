import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.application.protocols.course_estimator import CourseEstimatorService
from app.application.protocols.repository import CourseEstimateSourceData, EstimatorProductMetadata
from app.application.protocols.schemas import InventoryConstraintView, PulsePlanEntry


class FakeEstimatorRepository:
    def __init__(self, preview: CourseEstimateSourceData, active: CourseEstimateSourceData) -> None:
        self.preview = preview
        self.active = active

    async def get_course_estimate_source_from_preview(self, preview_id):
        if self.preview.preview_id == preview_id:
            return self.preview
        return None

    async def get_course_estimate_source_from_active_protocol(self, protocol_id):
        if self.active.protocol_id == protocol_id:
            return self.active
        return None


def _make_entry(product_id, mg: str, ml: str, offset: int = 0) -> PulsePlanEntry:
    return PulsePlanEntry(
        day_offset=offset,
        scheduled_day=date(2026, 1, 1),
        product_id=product_id,
        ingredient_context=None,
        volume_ml=Decimal(ml),
        computed_mg=Decimal(mg),
        injection_event_key=f"e-{offset}",
        sequence_no=offset,
    )


def _make_constraint(product_id, count: str, unit: str) -> InventoryConstraintView:
    now_id = uuid4()
    return InventoryConstraintView(
        id=now_id,
        draft_id=uuid4(),
        product_id=product_id,
        protocol_input_mode="inventory_constrained",
        available_count=Decimal(count),
        count_unit=unit,
        created_at=None,
        updated_at=None,
    )


def _build_source(
    *,
    source_type: str,
    preview_id,
    protocol_id,
    entries,
    metadata,
    constraints,
) -> CourseEstimateSourceData:
    return CourseEstimateSourceData(
        source_type=source_type,
        preview_id=preview_id,
        protocol_id=protocol_id,
        draft_id=uuid4(),
        protocol_input_mode="inventory_constrained" if constraints else "total_target",
        duration_weeks=8,
        entries=entries,
        inventory_constraints=constraints,
        product_metadata=metadata,
    )


def test_injectable_package_estimation() -> None:
    product_id = uuid4()
    preview_id = uuid4()
    source = _build_source(
        source_type="preview",
        preview_id=preview_id,
        protocol_id=None,
        entries=[_make_entry(product_id, "250", "1.25"), _make_entry(product_id, "250", "1.25", 1)],
        metadata={
            product_id: EstimatorProductMetadata(
                product_id=product_id,
                product_name="Test Vial",
                package_kind="vial",
                units_per_package=None,
                volume_per_package_ml=Decimal("1"),
                unit_strength_mg=Decimal("200"),
            )
        },
        constraints=[],
    )
    repo = FakeEstimatorRepository(preview=source, active=source)
    estimate = asyncio.run(CourseEstimatorService(repo).estimate_from_preview(preview_id))

    line = estimate.lines[0]
    assert line.required_active_mg_total == Decimal("500.0000")
    assert line.required_volume_ml_total == Decimal("2.5000")
    assert line.package_count_required == Decimal("2.5000")


def test_tablet_capsule_package_estimation() -> None:
    product_id = uuid4()
    preview_id = uuid4()
    source = _build_source(
        source_type="preview",
        preview_id=preview_id,
        protocol_id=None,
        entries=[_make_entry(product_id, "300", "0")],
        metadata={
            product_id: EstimatorProductMetadata(
                product_id=product_id,
                product_name="Test Tablets",
                package_kind="tablet",
                units_per_package=Decimal("30"),
                volume_per_package_ml=None,
                unit_strength_mg=Decimal("10"),
            )
        },
        constraints=[],
    )
    estimate = asyncio.run(CourseEstimatorService(FakeEstimatorRepository(source, source)).estimate_from_preview(preview_id))

    line = estimate.lines[0]
    assert line.required_unit_count_total == Decimal("30.0000")
    assert line.package_count_required == Decimal("1.0000")


def test_rounded_package_count() -> None:
    product_id = uuid4()
    preview_id = uuid4()
    source = _build_source(
        source_type="preview",
        preview_id=preview_id,
        protocol_id=None,
        entries=[_make_entry(product_id, "125", "1.1")],
        metadata={
            product_id: EstimatorProductMetadata(
                product_id=product_id,
                product_name="Rounding",
                package_kind="vial",
                units_per_package=None,
                volume_per_package_ml=Decimal("1"),
                unit_strength_mg=Decimal("100"),
            )
        },
        constraints=[],
    )

    line = asyncio.run(CourseEstimatorService(FakeEstimatorRepository(source, source)).estimate_from_preview(preview_id)).lines[0]
    assert line.package_count_required == Decimal("1.1000")
    assert line.package_count_required_rounded == 2


def test_inventory_comparison_sufficient() -> None:
    product_id = uuid4()
    preview_id = uuid4()
    constraints = [_make_constraint(product_id, "3", "vials")]
    source = _build_source(
        source_type="preview",
        preview_id=preview_id,
        protocol_id=None,
        entries=[_make_entry(product_id, "200", "2")],
        metadata={
            product_id: EstimatorProductMetadata(
                product_id=product_id,
                product_name="Inventory Good",
                package_kind="vial",
                units_per_package=None,
                volume_per_package_ml=Decimal("1"),
                unit_strength_mg=Decimal("100"),
            )
        },
        constraints=constraints,
    )

    line = asyncio.run(CourseEstimatorService(FakeEstimatorRepository(source, source)).estimate_from_preview(preview_id)).lines[0]
    assert line.inventory_sufficiency_status == "sufficient"
    assert line.shortfall_package_count is None


def test_inventory_comparison_insufficient() -> None:
    product_id = uuid4()
    preview_id = uuid4()
    constraints = [_make_constraint(product_id, "1", "vials")]
    source = _build_source(
        source_type="preview",
        preview_id=preview_id,
        protocol_id=None,
        entries=[_make_entry(product_id, "400", "3")],
        metadata={
            product_id: EstimatorProductMetadata(
                product_id=product_id,
                product_name="Inventory Low",
                package_kind="vial",
                units_per_package=None,
                volume_per_package_ml=Decimal("1"),
                unit_strength_mg=Decimal("100"),
            )
        },
        constraints=constraints,
    )

    line = asyncio.run(CourseEstimatorService(FakeEstimatorRepository(source, source)).estimate_from_preview(preview_id)).lines[0]
    assert line.inventory_sufficiency_status == "insufficient"
    assert line.shortfall_package_count == Decimal("2.0000")


def test_missing_packaging_metadata_warning() -> None:
    product_id = uuid4()
    preview_id = uuid4()
    source = _build_source(
        source_type="preview",
        preview_id=preview_id,
        protocol_id=None,
        entries=[_make_entry(product_id, "200", "1")],
        metadata={
            product_id: EstimatorProductMetadata(
                product_id=product_id,
                product_name="Unknown",
                package_kind=None,
                units_per_package=None,
                volume_per_package_ml=None,
                unit_strength_mg=None,
            )
        },
        constraints=[],
    )

    line = asyncio.run(CourseEstimatorService(FakeEstimatorRepository(source, source)).estimate_from_preview(preview_id)).lines[0]
    assert "packaging_metadata_missing" in line.estimation_warnings
    assert line.estimation_status == "unsupported"


def test_preview_source_estimation() -> None:
    product_id = uuid4()
    preview_id = uuid4()
    source = _build_source(
        source_type="preview",
        preview_id=preview_id,
        protocol_id=None,
        entries=[_make_entry(product_id, "100", "0.5")],
        metadata={
            product_id: EstimatorProductMetadata(
                product_id=product_id,
                product_name="Preview",
                package_kind="vial",
                units_per_package=None,
                volume_per_package_ml=Decimal("1"),
                unit_strength_mg=Decimal("100"),
            )
        },
        constraints=[],
    )

    estimate = asyncio.run(CourseEstimatorService(FakeEstimatorRepository(source, source)).estimate_from_preview(preview_id))
    assert estimate.source_type == "preview"
    assert estimate.preview_id == preview_id


def test_active_protocol_source_estimation() -> None:
    product_id = uuid4()
    protocol_id = uuid4()
    source = _build_source(
        source_type="active_protocol",
        preview_id=uuid4(),
        protocol_id=protocol_id,
        entries=[_make_entry(product_id, "100", "0.5")],
        metadata={
            product_id: EstimatorProductMetadata(
                product_id=product_id,
                product_name="Active",
                package_kind="vial",
                units_per_package=None,
                volume_per_package_ml=Decimal("1"),
                unit_strength_mg=Decimal("100"),
            )
        },
        constraints=[],
    )

    estimate = asyncio.run(CourseEstimatorService(FakeEstimatorRepository(source, source)).estimate_from_active_protocol(protocol_id))
    assert estimate.source_type == "active_protocol"
    assert estimate.protocol_id == protocol_id
