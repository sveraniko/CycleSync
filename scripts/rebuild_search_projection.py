import asyncio
import sys
from uuid import UUID

from app.application.search import SearchApplicationService
from app.core.config import get_settings
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.search import SqlAlchemySearchRepository


async def main() -> None:
    settings = get_settings()
    infra = await init_infrastructure(
        postgres_dsn=settings.postgres_dsn,
        redis_dsn=settings.redis_dsn,
        meilisearch_url=settings.meilisearch_url,
        meilisearch_api_key=settings.meilisearch_api_key,
        meilisearch_index=settings.meilisearch_index,
    )

    service = SearchApplicationService(
        repository=SqlAlchemySearchRepository(infra.db_session_factory),
        gateway=infra.search_gateway,
    )

    try:
        if len(sys.argv) > 1:
            ids = [UUID(raw_id) for raw_id in sys.argv[1:]]
            indexed = await service.rebuild_projection(product_ids=ids)
            print(f"Targeted rebuild finished. indexed_documents={indexed}")
        else:
            indexed = await service.rebuild_projection()
            print(f"Full rebuild finished. indexed_documents={indexed}")
    finally:
        await close_infrastructure(infra)


if __name__ == "__main__":
    asyncio.run(main())
