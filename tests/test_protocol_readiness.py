import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.application.protocols.readiness import ProtocolDraftReadinessService
from app.application.protocols.repository import DraftCalculationProductInfo
from app.application.protocols.schemas import DraftItemView, DraftSettingsView, DraftView
from app.application.protocols.schemas import StackInputTargetView


class FakeReadinessRepository:
    def __init__(
        self,
        settings: DraftSettingsView | None,
        products: list[DraftCalculationProductInfo],
        stack_targets: list[StackInputTargetView] | None = None,
    ) -> None:
        self.settings = settings
        self.products = products
        self.stack_targets = stack_targets or []

    async def get_draft_settings(self, draft_id):
        return self.settings

    async def list_calculation_products(self, draft_id):
        return self.products

    async def list_stack_input_targets(self, draft_id, protocol_input_mode=None):
        if protocol_input_mode is None:
            return self.stack_targets
        return [target for target in self.stack_targets if target.protocol_input_mode == protocol_input_mode]


def _draft_with_one_item() -> DraftView:
    now = datetime.now(timezone.utc)
    draft_id = uuid4()
    return DraftView(
        draft_id=draft_id,
        user_id="u1",
        status="active",
        created_at=now,
        updated_at=now,
        items=[
            DraftItemView(
                item_id=uuid4(),
                draft_id=draft_id,
                product_id=uuid4(),
                selected_brand="Brand",
                selected_product_name="Product",
                notes=None,
                created_at=now,
            )
        ],
    )


def test_readiness_reports_missing_settings_and_catalog_gaps() -> None:
    draft = _draft_with_one_item()
    repo = FakeReadinessRepository(
        settings=None,
        products=[
            DraftCalculationProductInfo(
                product_id=uuid4(),
                product_name="Gap Product",
                is_automatable=False,
                max_injection_volume_ml=None,
                ingredient_names=["Unknown"],
                has_half_life=False,
            )
        ],
    )
    service = ProtocolDraftReadinessService(repository=repo)

    result = asyncio.run(service.validate(draft))

    assert result.ready is False
    codes = {issue.code for issue in result.issues}
    assert "settings.missing" in codes
    assert "catalog.product_not_automatable" in codes
    assert "catalog.half_life_missing" in codes


def test_readiness_reports_conflicting_constraints() -> None:
    draft = _draft_with_one_item()
    now = datetime.now(timezone.utc)
    settings = DraftSettingsView(
        draft_id=draft.draft_id,
        protocol_input_mode="total_target",
        weekly_target_total_mg=Decimal("250"),
        duration_weeks=10,
        preset_code="layered_pulse",
        max_injection_volume_ml=Decimal("2.0"),
        max_injections_per_week=20,
        planned_start_date=None,
        updated_at=now,
    )
    repo = FakeReadinessRepository(
        settings=settings,
        products=[
            DraftCalculationProductInfo(
                product_id=uuid4(),
                product_name="OK Product",
                is_automatable=True,
                max_injection_volume_ml=Decimal("2.0"),
                ingredient_names=["Ingredient"],
                has_half_life=True,
            )
        ],
    )
    service = ProtocolDraftReadinessService(repository=repo)

    result = asyncio.run(service.validate(draft))

    warnings = [issue for issue in result.issues if issue.severity == "warning"]
    assert any(issue.code == "constraints.max_injections_too_high" for issue in warnings)


def test_total_target_mode_requires_weekly_target() -> None:
    draft = _draft_with_one_item()
    settings = DraftSettingsView(
        draft_id=draft.draft_id,
        protocol_input_mode="total_target",
        weekly_target_total_mg=None,
        duration_weeks=8,
        preset_code="layered_pulse",
        max_injection_volume_ml=Decimal("2.0"),
        max_injections_per_week=3,
        planned_start_date=None,
        updated_at=datetime.now(timezone.utc),
    )
    repo = FakeReadinessRepository(settings=settings, products=[])
    result = asyncio.run(ProtocolDraftReadinessService(repository=repo).validate(draft))
    assert any(issue.code == "settings.weekly_target_required" for issue in result.issues)


def test_auto_pulse_mode_allows_missing_weekly_target() -> None:
    draft = _draft_with_one_item()
    settings = DraftSettingsView(
        draft_id=draft.draft_id,
        protocol_input_mode="auto_pulse",
        weekly_target_total_mg=None,
        duration_weeks=8,
        preset_code="layered_pulse",
        max_injection_volume_ml=Decimal("2.0"),
        max_injections_per_week=3,
        planned_start_date=None,
        updated_at=datetime.now(timezone.utc),
    )
    repo = FakeReadinessRepository(
        settings=settings,
        products=[
            DraftCalculationProductInfo(
                product_id=uuid4(),
                product_name="OK Product",
                is_automatable=True,
                max_injection_volume_ml=Decimal("2.0"),
                ingredient_names=["Ingredient"],
                has_half_life=True,
            )
        ],
    )
    result = asyncio.run(ProtocolDraftReadinessService(repository=repo).validate(draft))
    assert all(issue.code != "settings.weekly_target_required" for issue in result.issues)


def test_inventory_constrained_mode_reports_not_available() -> None:
    draft = _draft_with_one_item()
    settings = DraftSettingsView(
        draft_id=draft.draft_id,
        protocol_input_mode="inventory_constrained",
        weekly_target_total_mg=None,
        duration_weeks=8,
        preset_code="layered_pulse",
        max_injection_volume_ml=Decimal("2.0"),
        max_injections_per_week=3,
        planned_start_date=None,
        updated_at=datetime.now(timezone.utc),
    )
    repo = FakeReadinessRepository(settings=settings, products=[])
    result = asyncio.run(ProtocolDraftReadinessService(repository=repo).validate(draft))
    assert any(issue.code == "settings.inventory_constrained.not_available" for issue in result.issues)


def test_stack_smoothing_mode_requires_target_for_each_selected_product() -> None:
    draft = _draft_with_one_item()
    settings = DraftSettingsView(
        draft_id=draft.draft_id,
        protocol_input_mode="stack_smoothing",
        weekly_target_total_mg=None,
        duration_weeks=8,
        preset_code="layered_pulse",
        max_injection_volume_ml=Decimal("2.0"),
        max_injections_per_week=3,
        planned_start_date=None,
        updated_at=datetime.now(timezone.utc),
    )
    repo = FakeReadinessRepository(settings=settings, products=[])
    result = asyncio.run(ProtocolDraftReadinessService(repository=repo).validate(draft))
    assert any(issue.code == "settings.stack_target_missing" for issue in result.issues)


def test_stack_smoothing_happy_path() -> None:
    draft = _draft_with_one_item()
    settings = DraftSettingsView(
        draft_id=draft.draft_id,
        protocol_input_mode="stack_smoothing",
        weekly_target_total_mg=None,
        duration_weeks=8,
        preset_code="layered_pulse",
        max_injection_volume_ml=Decimal("2.0"),
        max_injections_per_week=3,
        planned_start_date=None,
        updated_at=datetime.now(timezone.utc),
    )
    target = StackInputTargetView(
        id=uuid4(),
        draft_id=draft.draft_id,
        product_id=draft.items[0].product_id,
        protocol_input_mode="stack_smoothing",
        desired_weekly_mg=Decimal("200"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    repo = FakeReadinessRepository(
        settings=settings,
        products=[
            DraftCalculationProductInfo(
                product_id=draft.items[0].product_id,
                product_name="OK Product",
                is_automatable=True,
                max_injection_volume_ml=Decimal("2.0"),
                ingredient_names=["Ingredient"],
                has_half_life=True,
            )
        ],
        stack_targets=[target],
    )
    result = asyncio.run(ProtocolDraftReadinessService(repository=repo).validate(draft))
    assert all(issue.code != "settings.stack_target_missing" for issue in result.issues)
