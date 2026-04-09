from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.infrastructure.db import create_engine, create_session_factory
from app.infrastructure.redis import create_redis_client


@dataclass(slots=True)
class Infrastructure:
    db_engine: AsyncEngine
    db_session_factory: async_sessionmaker[AsyncSession]
    redis: Redis


async def init_infrastructure(postgres_dsn: str, redis_dsn: str) -> Infrastructure:
    db_engine = create_engine(postgres_dsn)
    db_session_factory = create_session_factory(db_engine)
    redis = create_redis_client(redis_dsn)
    return Infrastructure(
        db_engine=db_engine,
        db_session_factory=db_session_factory,
        redis=redis,
    )


async def close_infrastructure(infra: Infrastructure) -> None:
    await infra.redis.close()
    await infra.db_engine.dispose()
