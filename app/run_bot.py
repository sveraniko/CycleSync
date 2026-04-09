import asyncio

import structlog
from aiogram import Bot, Dispatcher

from app.bots.router import get_root_router
from app.core.config import get_settings
from app.core.logging import configure_logging


async def run_bot() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = structlog.get_logger("cyclesync.bot")

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required to run bot shell")

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(get_root_router())

    logger.info("bot_startup", env=settings.app_env)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("bot_shutdown")


if __name__ == "__main__":
    asyncio.run(run_bot())
