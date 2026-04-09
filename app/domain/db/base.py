from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import MetaData, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from sqlalchemy.sql.sqltypes import DateTime

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(schema_name)s_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(schema_name)s_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(schema_name)s_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(schema_name)s_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(schema_name)s_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    metadata = metadata


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class IDMixin:
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)


class SchemaTableMixin:
    __table_args__: dict[str, Any]

    @declared_attr.directive
    def __table_args__(cls) -> dict[str, Any]:
        return {"schema": cls.__schema_name__}


class BaseModel(IDMixin, TimestampMixin, Base):
    __abstract__ = True
