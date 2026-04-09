import asyncio

import structlog
from aiogram import Bot, Dispatcher

from app.application.search import SearchApplicationService
from app.bots.router import get_root_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.search import SqlAlchemySearchRepository


async def run_bot() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = structlog.get_logger("cyclesync.bot")

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required to run bot shell")

    infra = await init_infrastructure(
        postgres_dsn=settings.postgres_dsn,
        redis_dsn=settings.redis_dsn,
        meilisearch_url=settings.meilisearch_url,
        meilisearch_api_key=settings.meilisearch_api_key,
        meilisearch_index=settings.meilisearch_index,
    )
    search_repository = SqlAlchemySearchRepository(infra.db_session_factory)
    search_service = SearchApplicationService(repository=search_repository, gateway=infra.search_gateway)

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(get_root_router())

    logger.info("bot_startup", env=settings.app_env)
    try:
        await dispatcher.start_polling(bot, search_service=search_service)
    finally:
        await bot.session.close()
        await close_infrastructure(infra)
        logger.info("bot_shutdown")


if __name__ == "__main__":
    asyncio.run(run_bot())
