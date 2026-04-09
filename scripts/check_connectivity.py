import asyncio

from app.core.config import get_settings
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.db import db_healthcheck
from app.infrastructure.redis import redis_healthcheck


async def main() -> None:
    settings = get_settings()
    infra = await init_infrastructure(settings.postgres_dsn, settings.redis_dsn)
    try:
        db = await db_healthcheck(infra.db_engine)
        redis = await redis_healthcheck(infra.redis)
        print({"postgres": db, "redis": redis})
    finally:
        await close_infrastructure(infra)


if __name__ == "__main__":
    asyncio.run(main())
