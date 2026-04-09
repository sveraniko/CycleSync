from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.routers.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = structlog.get_logger("cyclesync.api")

    infra = await init_infrastructure(
        postgres_dsn=settings.postgres_dsn,
        redis_dsn=settings.redis_dsn,
        meilisearch_url=settings.meilisearch_url,
        meilisearch_api_key=settings.meilisearch_api_key,
        meilisearch_index=settings.meilisearch_index,
    )
    app.state.settings = settings
    app.state.infra = infra

    logger.info(
        "api_startup",
        env=settings.app_env,
        host=settings.api_host,
        port=settings.api_port,
    )
    try:
        yield
    finally:
        await close_infrastructure(infra)
        logger.info("api_shutdown")


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(health_router)
