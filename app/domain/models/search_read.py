from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.db.base import BaseModel, SchemaTableMixin


class SearchProjectionState(SchemaTableMixin, BaseModel):
    __tablename__ = "search_projection_state"
    __schema_name__ = "search_read"

    projection_name: Mapped[str] = mapped_column(String(128), nullable=False)
    checkpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    checkpointed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    indexed_documents_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_rebuild_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="incremental")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("projection_name", name="uq_search_projection_state_name"),
        {"schema": __schema_name__},
    )


class SearchQueryLog(SchemaTableMixin, BaseModel):
    __tablename__ = "search_query_logs"
    __schema_name__ = "search_read"

    raw_query: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_query: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    was_found: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_search_query_logs_created_at", "created_at"),
        Index("ix_search_query_logs_was_found_created_at", "was_found", "created_at"),
        {"schema": __schema_name__},
    )
