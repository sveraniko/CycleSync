from datetime import datetime, timezone

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

    postgres = await db_healthcheck(infra.db_engine)
    redis = await redis_healthcheck(infra.redis)

    overall_ok = postgres["ok"] and redis["ok"]
    checks = {
        "postgres": postgres,
        "redis": redis,
    }

    return {
        "status": "ok" if overall_ok else "degraded",
        "checks": checks,
    }


@router.get("/diagnostics")
async def diagnostics(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    ready_payload = await ready(request)
    catalog_source_configured = bool(settings.google_sheets_sheet_id and settings.google_sheets_tab_name)
    return {
        "app_name": settings.app_name,
        "env": settings.app_env,
        "timezone": settings.timezone_default,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dependencies": ready_payload["checks"],
        "readiness": {
            "status": ready_payload["status"],
            "ok": ready_payload["status"] == "ok",
        },
        "catalog_source": {
            "configured": catalog_source_configured,
            "source": "google_sheets",
            "sheet_id_present": bool(settings.google_sheets_sheet_id),
            "tab_name": settings.google_sheets_tab_name,
        },
    }
