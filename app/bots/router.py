from aiogram import Router

from app.bots.handlers.search import router as search_router
from app.bots.handlers.start import router as start_router


def get_root_router() -> Router:
    root_router = Router(name="root")
    root_router.include_router(start_router)
    root_router.include_router(search_router)
    return root_router
