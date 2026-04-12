import asyncio

import structlog
from aiogram import Bot, Dispatcher

from app.application.protocols import (
    DraftApplicationService,
    ProtocolDraftReadinessService,
    PulseCalculationEngine,
)
from app.application.access import AccessEvaluationService
from app.application.reminders import ReminderApplicationService
from app.application.labs import LabsApplicationService, LabsTriageService
from app.application.expert_cases import SpecialistCaseAssemblyService
from app.application.search import SearchApplicationService
from app.bots.router import get_root_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.protocols import SqlAlchemyDraftRepository
from app.infrastructure.access import SqlAlchemyAccessRepository
from app.infrastructure.reminders import SqlAlchemyReminderRepository
from app.infrastructure.labs import SqlAlchemyLabsRepository, build_labs_triage_gateway
from app.infrastructure.expert_cases import SqlAlchemySpecialistCasesRepository
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
    search_service = SearchApplicationService(
        repository=search_repository, gateway=infra.search_gateway
    )
    draft_repository = SqlAlchemyDraftRepository(infra.db_session_factory)
    reminder_repository = SqlAlchemyReminderRepository(infra.db_session_factory)
    labs_repository = SqlAlchemyLabsRepository(infra.db_session_factory)
    specialist_cases_repository = SqlAlchemySpecialistCasesRepository(infra.db_session_factory)
    access_repository = SqlAlchemyAccessRepository(infra.db_session_factory)
    access_service = AccessEvaluationService(repository=access_repository)
    labs_triage_gateway = build_labs_triage_gateway(settings)
    logger.info("labs_triage_gateway_configured", **labs_triage_gateway.diagnostics())
    readiness_service = ProtocolDraftReadinessService(repository=draft_repository)
    pulse_engine = PulseCalculationEngine()
    draft_service = DraftApplicationService(
        repository=draft_repository,
        readiness_validator=readiness_service,
        pulse_engine=pulse_engine,
    )

    reminder_service = ReminderApplicationService(
        repository=reminder_repository,
        access_evaluator=access_service,
        default_timezone=settings.timezone_default,
    )
    labs_service = LabsApplicationService(repository=labs_repository)
    labs_triage_service = LabsTriageService(
        repository=labs_repository,
        gateway=labs_triage_gateway,
        access_evaluator=access_service,
    )
    specialist_case_service = SpecialistCaseAssemblyService(
        repository=specialist_cases_repository,
        access_evaluator=access_service,
    )

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(get_root_router())

    logger.info("bot_startup", env=settings.app_env)
    try:
        await dispatcher.start_polling(
            bot,
            search_service=search_service,
            draft_service=draft_service,
            reminder_service=reminder_service,
            labs_service=labs_service,
            labs_triage_service=labs_triage_service,
            specialist_case_service=specialist_case_service,
        )
    finally:
        await bot.session.close()
        close_gateway = getattr(labs_triage_gateway, "close", None)
        if callable(close_gateway):
            await close_gateway()
        await close_infrastructure(infra)
        logger.info("bot_shutdown")


if __name__ == "__main__":
    asyncio.run(run_bot())
