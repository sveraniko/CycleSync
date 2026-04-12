import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.application.protocols.draft_service import DraftApplicationService
from app.application.protocols.readiness import ProtocolDraftReadinessService
from app.application.protocols.repository import DraftCalculationProductInfo
from app.application.protocols.schemas import (
    AddProductToDraftResult,
    DraftItemView,
    DraftSettingsInput,
    DraftSettingsView,
    DraftView,
    InventoryConstraintInput,
    InventoryConstraintView,
    StackInputTargetInput,
    StackInputTargetView,
)


@dataclass
class EventRecord:
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    payload: dict


class FakeDraftRepository:
    def __init__(self) -> None:
        self.user_id = "u1"
        self.draft_id = uuid4()
        self.items: list[DraftItemView] = []
        self.events: list[EventRecord] = []
        self.settings: DraftSettingsView | None = None
        self.calculation_products: list[DraftCalculationProductInfo] = []
        self.stack_targets: list[StackInputTargetView] = []
        self.inventory_constraints: list[InventoryConstraintView] = []

    async def get_or_create_active_draft(self, user_id: str):
        created = not hasattr(self, "_created")
        self._created = True
        return self._build_draft(user_id), created

    async def get_active_draft(self, user_id: str):
        return self._build_draft(user_id)

    async def add_product_to_draft(self, user_id: str, product_id: UUID) -> AddProductToDraftResult:
        existing = next((i for i in self.items if i.product_id == product_id), None)
        if existing:
            return AddProductToDraftResult(draft=self._build_draft(user_id), item=existing, added=False)

        item = DraftItemView(
            item_id=uuid4(),
            draft_id=self.draft_id,
            product_id=product_id,
            selected_brand="Brand",
            selected_product_name="Product",
            notes=None,
            created_at=datetime.now(timezone.utc),
        )
        self.items.append(item)
        return AddProductToDraftResult(draft=self._build_draft(user_id), item=item, added=True)

    async def remove_item_from_draft(self, user_id: str, item_id: UUID):
        self.items = [i for i in self.items if i.item_id != item_id]
        return self._build_draft(user_id)

    async def clear_draft(self, user_id: str):
        self.items = []
        return self._build_draft(user_id)

    async def get_product_info(self, product_id: UUID):
        return None

    async def enqueue_event(self, *, event_type: str, aggregate_type: str, aggregate_id: UUID, payload: dict, **kwargs):
        self.events.append(
            EventRecord(
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
            )
        )

    async def upsert_draft_settings(self, draft_id: UUID, settings: DraftSettingsInput) -> DraftSettingsView:
        now = datetime.now(timezone.utc)
        self.settings = DraftSettingsView(
            draft_id=draft_id,
            protocol_input_mode=settings.protocol_input_mode,
            weekly_target_total_mg=settings.weekly_target_total_mg,
            duration_weeks=settings.duration_weeks,
            preset_code=settings.preset_code,
            max_injection_volume_ml=settings.max_injection_volume_ml,
            max_injections_per_week=settings.max_injections_per_week,
            planned_start_date=settings.planned_start_date,
            updated_at=now,
        )
        return self.settings

    async def get_draft_settings(self, draft_id: UUID) -> DraftSettingsView | None:
        return self.settings

    async def list_calculation_products(self, draft_id: UUID) -> list[DraftCalculationProductInfo]:
        return self.calculation_products

    async def upsert_stack_input_targets(self, draft_id: UUID, targets: list[StackInputTargetInput]) -> list[StackInputTargetView]:
        for target in targets:
            existing = next(
                (
                    row
                    for row in self.stack_targets
                    if row.draft_id == draft_id
                    and row.product_id == target.product_id
                    and row.protocol_input_mode == target.protocol_input_mode
                ),
                None,
            )
            now = datetime.now(timezone.utc)
            if existing:
                existing.desired_weekly_mg = target.desired_weekly_mg
                existing.updated_at = now
            else:
                self.stack_targets.append(
                    StackInputTargetView(
                        id=uuid4(),
                        draft_id=draft_id,
                        product_id=target.product_id,
                        protocol_input_mode=target.protocol_input_mode,
                        desired_weekly_mg=target.desired_weekly_mg,
                        created_at=now,
                        updated_at=now,
                    )
                )
        return [target for target in self.stack_targets if target.draft_id == draft_id]

    async def list_stack_input_targets(self, draft_id: UUID, protocol_input_mode: str | None = None) -> list[StackInputTargetView]:
        rows = [target for target in self.stack_targets if target.draft_id == draft_id]
        if protocol_input_mode is not None:
            rows = [target for target in rows if target.protocol_input_mode == protocol_input_mode]
        return rows

    async def upsert_inventory_constraints(
        self, draft_id: UUID, constraints: list[InventoryConstraintInput]
    ) -> list[InventoryConstraintView]:
        for constraint in constraints:
            existing = next(
                (
                    row
                    for row in self.inventory_constraints
                    if row.draft_id == draft_id
                    and row.product_id == constraint.product_id
                    and row.protocol_input_mode == constraint.protocol_input_mode
                ),
                None,
            )
            now = datetime.now(timezone.utc)
            if existing:
                existing.available_count = constraint.available_count
                existing.count_unit = constraint.count_unit
                existing.updated_at = now
            else:
                self.inventory_constraints.append(
                    InventoryConstraintView(
                        id=uuid4(),
                        draft_id=draft_id,
                        product_id=constraint.product_id,
                        protocol_input_mode=constraint.protocol_input_mode,
                        available_count=constraint.available_count,
                        count_unit=constraint.count_unit,
                        created_at=now,
                        updated_at=now,
                    )
                )
        return [item for item in self.inventory_constraints if item.draft_id == draft_id]

    async def list_inventory_constraints(
        self, draft_id: UUID, protocol_input_mode: str | None = None
    ) -> list[InventoryConstraintView]:
        rows = [item for item in self.inventory_constraints if item.draft_id == draft_id]
        if protocol_input_mode is not None:
            rows = [item for item in rows if item.protocol_input_mode == protocol_input_mode]
        return rows

    def _build_draft(self, user_id: str) -> DraftView:
        now = datetime.now(timezone.utc)
        return DraftView(
            draft_id=self.draft_id,
            user_id=user_id,
            status="active",
            created_at=now,
            updated_at=now,
            items=list(self.items),
        )


def test_draft_service_create_add_remove_clear_list() -> None:
    repo = FakeDraftRepository()
    service = DraftApplicationService(repository=repo)

    draft = asyncio.run(service.list_draft("u1"))
    assert draft.status == "active"

    product_id = uuid4()
    add_result = asyncio.run(service.add_product_to_draft("u1", product_id))
    assert add_result.added is True
    assert len(add_result.draft.items) == 1

    draft_after_remove = asyncio.run(service.remove_item_from_draft("u1", add_result.item.item_id))
    assert draft_after_remove is not None
    assert len(draft_after_remove.items) == 0

    add_result_2 = asyncio.run(service.add_product_to_draft("u1", product_id))
    assert add_result_2.added is True

    draft_after_clear = asyncio.run(service.clear_draft("u1"))
    assert draft_after_clear is not None
    assert len(draft_after_clear.items) == 0

    event_names = [e.event_type for e in repo.events]
    assert "draft_created" in event_names
    assert "draft_opened" in event_names
    assert "draft_item_added" in event_names
    assert "draft_item_removed" in event_names
    assert "draft_cleared" in event_names


def test_draft_service_add_duplicate_is_idempotent() -> None:
    repo = FakeDraftRepository()
    service = DraftApplicationService(repository=repo)

    product_id = uuid4()
    first = asyncio.run(service.add_product_to_draft("u1", product_id))
    second = asyncio.run(service.add_product_to_draft("u1", product_id))

    assert first.added is True
    assert second.added is False
    assert len(second.draft.items) == 1

    draft_item_added_events = [e for e in repo.events if e.event_type == "draft_item_added"]
    assert len(draft_item_added_events) == 1


def test_draft_settings_persistence_and_readiness() -> None:
    repo = FakeDraftRepository()
    repo.calculation_products = [
        DraftCalculationProductInfo(
            product_id=uuid4(),
            product_name="Test Product",
            is_automatable=True,
            max_injection_volume_ml=Decimal("2.0"),
            ingredient_names=["Testosterone Enanthate"],
            has_half_life=True,
        )
    ]
    readiness = ProtocolDraftReadinessService(repository=repo)
    service = DraftApplicationService(repository=repo, readiness_validator=readiness)

    asyncio.run(service.add_product_to_draft("u1", uuid4()))
    saved = asyncio.run(
        service.save_draft_settings(
            "u1",
            DraftSettingsInput(
                protocol_input_mode="total_target",
                weekly_target_total_mg=Decimal("350"),
                duration_weeks=12,
                preset_code="unified_rhythm",
                max_injection_volume_ml=Decimal("2.5"),
                max_injections_per_week=3,
            ),
        )
    )
    assert saved.weekly_target_total_mg == Decimal("350")
    loaded = asyncio.run(service.get_draft_settings("u1"))
    assert loaded is not None
    assert loaded.preset_code == "unified_rhythm"
    assert loaded.protocol_input_mode == "total_target"

    readiness_result = asyncio.run(service.get_draft_readiness("u1"))
    assert readiness_result.ready is True
    assert readiness_result.issues == []


def test_stack_input_persistence_and_event() -> None:
    repo = FakeDraftRepository()
    service = DraftApplicationService(repository=repo)
    product_id = uuid4()
    asyncio.run(service.add_product_to_draft("u1", product_id))

    saved = asyncio.run(
        service.save_stack_input_targets(
            "u1",
            [
                StackInputTargetInput(
                    product_id=product_id,
                    protocol_input_mode="stack_smoothing",
                    desired_weekly_mg=Decimal("175"),
                )
            ],
        )
    )
    loaded = asyncio.run(service.get_stack_input_targets("u1"))

    assert saved[0].desired_weekly_mg == Decimal("175")
    assert loaded[0].product_id == product_id
    assert any(event.event_type == "stack_input_updated" for event in repo.events)


def test_inventory_input_persistence_and_event() -> None:
    repo = FakeDraftRepository()
    service = DraftApplicationService(repository=repo)
    product_id = uuid4()
    asyncio.run(service.add_product_to_draft("u1", product_id))

    saved = asyncio.run(
        service.save_inventory_constraints(
            "u1",
            [
                InventoryConstraintInput(
                    product_id=product_id,
                    protocol_input_mode="inventory_constrained",
                    available_count=Decimal("20"),
                    count_unit="vial",
                )
            ],
        )
    )
    loaded = asyncio.run(service.get_inventory_constraints("u1"))

    assert saved[0].available_count == Decimal("20")
    assert loaded[0].count_unit == "vial"
    assert any(event.event_type == "inventory_constraints_updated" for event in repo.events)
