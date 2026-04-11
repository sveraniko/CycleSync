from datetime import datetime, timezone

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.infrastructure.db import db_healthcheck
from app.infrastructure.redis import redis_healthcheck

router = APIRouter(prefix="/health", tags=["health"])


async def _load_reminder_foundation_metrics(session_factory) -> dict[str, int]:
    try:
        async with session_factory() as session:
            pending = await session.scalar(
                text(
                    "SELECT count(*) FROM reminders.reminder_schedule_requests WHERE status = 'requested'"
                )
            )
            failed = await session.scalar(
                text(
                    "SELECT count(*) FROM reminders.reminder_schedule_requests WHERE status = 'failed'"
                )
            )
            materialized = await session.scalar(
                text("SELECT count(*) FROM reminders.protocol_reminders")
            )
            status_rows = await session.execute(
                text(
                    "SELECT status, count(*) FROM reminders.protocol_reminders GROUP BY status"
                )
            )
            failed_delivery = await session.scalar(
                text(
                    "SELECT count(*) FROM reminders.protocol_reminders WHERE status = 'failed_delivery'"
                )
            )
            integrity_rows = await session.execute(
                text(
                    "SELECT integrity_state, count(*) FROM adherence.protocol_adherence_summaries GROUP BY integrity_state"
                )
            )
            reason_rows = await session.execute(
                text(
                    "SELECT integrity_reason_code, count(*) FROM adherence.protocol_adherence_summaries WHERE integrity_reason_code IS NOT NULL GROUP BY integrity_reason_code"
                )
            )

        status_counts = {row[0]: int(row[1]) for row in status_rows}
        integrity_state_counts = {row[0]: int(row[1]) for row in integrity_rows}
        return {
            "pending_schedule_requests": int(pending or 0),
            "failed_schedule_requests": int(failed or 0),
            "materialized_reminder_rows": int(materialized or 0),
            "status_counts": status_counts,
            "failed_delivery_count": int(failed_delivery or 0),
            "integrity_state_counts": integrity_state_counts,
            "broken_protocol_count": int(integrity_state_counts.get("broken", 0)),
            "degraded_protocol_count": int(integrity_state_counts.get("degraded", 0)),
            "top_integrity_reason_codes": {row[0]: int(row[1]) for row in reason_rows},
        }
    except Exception:
        return {
            "pending_schedule_requests": 0,
            "failed_schedule_requests": 0,
            "materialized_reminder_rows": 0,
            "status_counts": {},
            "failed_delivery_count": 0,
            "integrity_state_counts": {},
            "broken_protocol_count": 0,
            "degraded_protocol_count": 0,
            "top_integrity_reason_codes": {},
        }


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    infra = request.app.state.infra

    postgres = await db_healthcheck(infra.db_engine)
    redis = await redis_healthcheck(infra.redis)

    search = await infra.search_gateway.healthcheck()

    overall_ok = postgres["ok"] and redis["ok"]
    checks = {
        "postgres": postgres,
        "redis": redis,
        "search": search,
    }

    return {
        "status": "ok" if overall_ok else "degraded",
        "checks": checks,
    }


@router.get("/diagnostics")
async def diagnostics(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    ready_payload = await ready(request)
    catalog_source_configured = bool(
        settings.google_sheets_sheet_id and settings.google_sheets_tab_name
    )
    reminder_metrics = await _load_reminder_foundation_metrics(
        request.app.state.infra.db_session_factory
    )
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
        "reminders_foundation": reminder_metrics,
        "catalog_source": {
            "configured": catalog_source_configured,
            "source": "google_sheets",
            "sheet_id_present": bool(settings.google_sheets_sheet_id),
            "tab_name": settings.google_sheets_tab_name,
        },
    }
