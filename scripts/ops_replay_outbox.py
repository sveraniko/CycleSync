import asyncio
import sys

from app.core.config import get_settings
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.ops import SqlAlchemyOpsRepository


async def main() -> None:
    settings = get_settings()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    aggregate_type = sys.argv[2] if len(sys.argv) > 2 else None

    infra = await init_infrastructure(
        postgres_dsn=settings.postgres_dsn,
        redis_dsn=settings.redis_dsn,
        meilisearch_url=settings.meilisearch_url,
        meilisearch_api_key=settings.meilisearch_api_key,
        meilisearch_index=settings.meilisearch_index,
    )
    try:
        repo = SqlAlchemyOpsRepository(infra.db_session_factory)
        replayed = await repo.replay_outbox(limit=limit, aggregate_type=aggregate_type)
        print(f"replayed_outbox_events={replayed}")
    finally:
        await close_infrastructure(infra)


if __name__ == "__main__":
    asyncio.run(main())
