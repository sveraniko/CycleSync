from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.infrastructure.db import create_engine, create_session_factory
from app.infrastructure.redis import create_redis_client
from app.infrastructure.search import MeiliSearchGateway


@dataclass(slots=True)
class Infrastructure:
    db_engine: AsyncEngine
    db_session_factory: async_sessionmaker[AsyncSession]
    redis: Redis
    search_gateway: MeiliSearchGateway


async def init_infrastructure(
    postgres_dsn: str,
    redis_dsn: str,
    meilisearch_url: str,
    meilisearch_api_key: str,
    meilisearch_index: str,
) -> Infrastructure:
    db_engine = create_engine(postgres_dsn)
    db_session_factory = create_session_factory(db_engine)
    redis = create_redis_client(redis_dsn)
    search_gateway = MeiliSearchGateway(
        base_url=meilisearch_url,
        api_key=meilisearch_api_key,
        index_name=meilisearch_index,
    )
    return Infrastructure(
        db_engine=db_engine,
        db_session_factory=db_session_factory,
        redis=redis,
        search_gateway=search_gateway,
    )


async def close_infrastructure(infra: Infrastructure) -> None:
    await infra.search_gateway.close()
    await infra.redis.aclose()
    await infra.db_engine.dispose()
