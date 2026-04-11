import asyncio
import json

from aiogram import Bot

from app.application.reminders import ReminderApplicationService
from app.core.config import get_settings
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.reminders import (
    SqlAlchemyReminderRepository,
    TelegramReminderDeliveryGateway,
)


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required for reminder dispatch")

    infra = await init_infrastructure(
        postgres_dsn=settings.postgres_dsn,
        redis_dsn=settings.redis_dsn,
        meilisearch_url=settings.meilisearch_url,
        meilisearch_api_key=settings.meilisearch_api_key,
        meilisearch_index=settings.meilisearch_index,
    )
    bot = Bot(token=settings.bot_token)

    try:
        repo = SqlAlchemyReminderRepository(infra.db_session_factory)
        service = ReminderApplicationService(
            repository=repo,
            default_timezone=settings.timezone_default,
        )
        gateway = TelegramReminderDeliveryGateway(bot)
        report = await service.dispatch_due_reminders(delivery_gateway=gateway)
        print(
            json.dumps(
                {
                    "due_selected": report.due_selected,
                    "sent": report.sent,
                    "expired": report.expired,
                    "cleaned": report.cleaned,
                    "failed_delivery": report.failed_delivery,
                }
            )
        )
    finally:
        await bot.session.close()
        await close_infrastructure(infra)


if __name__ == "__main__":
    asyncio.run(main())
