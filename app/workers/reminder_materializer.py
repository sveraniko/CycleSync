from datetime import time

from app.application.access import AccessEvaluationService
from app.application.reminders import ReminderApplicationService
from app.core.config import get_settings
from app.infrastructure.access import SqlAlchemyAccessRepository
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.reminders import SqlAlchemyReminderRepository


async def run_reminder_materializer(limit: int = 100) -> list:
    settings = get_settings()
    infra = await init_infrastructure(
        postgres_dsn=settings.postgres_dsn,
        redis_dsn=settings.redis_dsn,
        meilisearch_url=settings.meilisearch_url,
        meilisearch_api_key=settings.meilisearch_api_key,
        meilisearch_index=settings.meilisearch_index,
    )
    try:
        access_service = AccessEvaluationService(
            repository=SqlAlchemyAccessRepository(infra.db_session_factory)
        )
        service = ReminderApplicationService(
            repository=SqlAlchemyReminderRepository(infra.db_session_factory),
            access_evaluator=access_service,
            default_timezone=settings.timezone_default,
            default_local_time=time(hour=9, minute=0),
        )
        return await service.materialize_requested_schedules(limit=limit)
    finally:
        await close_infrastructure(infra)
