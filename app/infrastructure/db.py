from collections.abc import AsyncGenerator
from time import perf_counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(postgres_dsn: str) -> AsyncEngine:
    return create_async_engine(postgres_dsn, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False)


async def db_healthcheck(engine: AsyncEngine) -> dict[str, Any]:
    started = perf_counter()
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {
            "ok": True,
            "status": "ok",
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        }
    except Exception as exc:  # pragma: no cover - defensive path for infra outages
        return {
            "ok": False,
            "status": "error",
            "latency_ms": round((perf_counter() - started) * 1000, 2),
            "error": str(exc),
        }


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
