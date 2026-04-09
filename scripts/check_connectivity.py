import asyncio

from app.core.config import get_settings
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.db import db_healthcheck
from app.infrastructure.redis import redis_healthcheck


async def main() -> None:
    settings = get_settings()
    infra = await init_infrastructure(
        postgres_dsn=settings.postgres_dsn,
        redis_dsn=settings.redis_dsn,
        meilisearch_url=settings.meilisearch_url,
        meilisearch_api_key=settings.meilisearch_api_key,
        meilisearch_index=settings.meilisearch_index,
    )
    try:
        db = await db_healthcheck(infra.db_engine)
        redis = await redis_healthcheck(infra.redis)
        meilisearch = await infra.search_gateway.healthcheck()
        print({"postgres": db, "redis": redis, "meilisearch": meilisearch})
    finally:
        await close_infrastructure(infra)


if __name__ == "__main__":
    asyncio.run(main())
