from aiogram import Router

from app.bots.handlers.draft import router as draft_router
from app.bots.handlers.search import router as search_router
from app.bots.handlers.settings import router as settings_router
from app.bots.handlers.start import router as start_router
from app.bots.handlers.reminder_actions import router as reminder_actions_router
from app.bots.handlers.labs import router as labs_router


def get_root_router() -> Router:
    root_router = Router(name="root")
    root_router.include_router(start_router)
    root_router.include_router(draft_router)
    root_router.include_router(search_router)
    root_router.include_router(settings_router)
    root_router.include_router(reminder_actions_router)
    root_router.include_router(labs_router)
    return root_router
