from datetime import UTC, datetime

from fastapi import APIRouter, Request

from app.infrastructure.db import db_healthcheck
from app.infrastructure.redis import redis_healthcheck

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    infra = request.app.state.infra

    db_ok = await db_healthcheck(infra.db_engine)
    redis_ok = await redis_healthcheck(infra.redis)

    overall = "ok" if db_ok and redis_ok else "degraded"
    return {
        "status": overall,
        "checks": {
            "postgres": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    }


@router.get("/diagnostics")
async def diagnostics(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    ready_payload = await ready(request)
    return {
        "app_name": settings.app_name,
        "env": settings.app_env,
        "timezone": settings.timezone_default,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "readiness": ready_payload,
    }
