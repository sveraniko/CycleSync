from aiogram import Router

from app.bots.handlers.start import router as start_router


def get_root_router() -> Router:
    root_router = Router(name="root")
    root_router.include_router(start_router)
    return root_router
