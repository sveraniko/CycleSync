"""
Reminder scheduler worker — runs materialize + dispatch in a continuous loop.

Intervals (env-configurable):
  REMINDER_MATERIALIZE_INTERVAL_SECONDS  default 120  (2 min)
  REMINDER_DISPATCH_INTERVAL_SECONDS     default  60  (1 min)

Designed to be the single long-running process that keeps reminders alive
without any external cron/systemd dependency.
"""
import asyncio
import json
import logging
import os
from datetime import time

from aiogram import Bot

from app.application.access import AccessEvaluationService
from app.application.reminders import ReminderApplicationService
from app.core.config import get_settings
from app.infrastructure.access import SqlAlchemyAccessRepository
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.reminders import (
    SqlAlchemyReminderRepository,
    TelegramReminderDeliveryGateway,
)

logger = logging.getLogger(__name__)

MATERIALIZE_INTERVAL = int(os.environ.get("REMINDER_MATERIALIZE_INTERVAL_SECONDS", 120))
DISPATCH_INTERVAL = int(os.environ.get("REMINDER_DISPATCH_INTERVAL_SECONDS", 60))
MATERIALIZE_BATCH = int(os.environ.get("REMINDER_MATERIALIZE_BATCH", 200))


async def run_scheduler() -> None:
    settings = get_settings()

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required for the reminder scheduler")

    logger.info(
        "reminder_scheduler starting — materialize every %ds, dispatch every %ds",
        MATERIALIZE_INTERVAL,
        DISPATCH_INTERVAL,
    )

    infra = await init_infrastructure(
        postgres_dsn=settings.postgres_dsn,
        redis_dsn=settings.redis_dsn,
        meilisearch_url=settings.meilisearch_url,
        meilisearch_api_key=settings.meilisearch_api_key,
        meilisearch_index=settings.meilisearch_index,
    )
    bot = Bot(token=settings.bot_token)

    try:
        last_materialize = 0.0

        while True:
            now = asyncio.get_event_loop().time()

            # --- dispatch (every DISPATCH_INTERVAL) ---
            try:
                repo = SqlAlchemyReminderRepository(infra.db_session_factory)
                access_svc = AccessEvaluationService(
                    repository=SqlAlchemyAccessRepository(infra.db_session_factory)
                )
                reminder_svc = ReminderApplicationService(
                    repository=repo,
                    access_evaluator=access_svc,
                    default_timezone=settings.timezone_default,
                )
                gateway = TelegramReminderDeliveryGateway(bot)
                report = await reminder_svc.dispatch_due_reminders(delivery_gateway=gateway)
                logger.info(
                    "dispatch — %s",
                    json.dumps({
                        "due_selected": report.due_selected,
                        "sent": report.sent,
                        "expired": report.expired,
                        "cleaned": report.cleaned,
                        "failed_delivery": report.failed_delivery,
                    }),
                )
            except Exception:
                logger.exception("dispatch cycle error")

            # --- materialize (every MATERIALIZE_INTERVAL) ---
            if now - last_materialize >= MATERIALIZE_INTERVAL:
                try:
                    access_svc = AccessEvaluationService(
                        repository=SqlAlchemyAccessRepository(infra.db_session_factory)
                    )
                    mat_svc = ReminderApplicationService(
                        repository=SqlAlchemyReminderRepository(infra.db_session_factory),
                        access_evaluator=access_svc,
                        default_timezone=settings.timezone_default,
                        default_local_time=time(hour=9, minute=0),
                    )
                    results = await mat_svc.materialize_requested_schedules(limit=MATERIALIZE_BATCH)
                    logger.info(
                        "materialize — processed_requests=%d",
                        len(results),
                    )
                    last_materialize = now
                except Exception:
                    logger.exception("materialize cycle error")

            await asyncio.sleep(DISPATCH_INTERVAL)

    finally:
        await bot.session.close()
        await close_infrastructure(infra)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run_scheduler())
