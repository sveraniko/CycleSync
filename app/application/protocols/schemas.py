from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class DraftItemView:
    item_id: UUID
    draft_id: UUID
    product_id: UUID
    selected_brand: str | None
    selected_product_name: str | None
    notes: str | None
    created_at: datetime


@dataclass(slots=True)
class DraftView:
    draft_id: UUID
    user_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[DraftItemView]


@dataclass(slots=True)
class AddProductToDraftResult:
    draft: DraftView
    item: DraftItemView
    added: bool
