from time import perf_counter
from typing import Any

from redis.asyncio import Redis


def create_redis_client(redis_dsn: str) -> Redis:
    return Redis.from_url(redis_dsn, decode_responses=True)


async def redis_healthcheck(client: Redis) -> dict[str, Any]:
    started = perf_counter()
    try:
        await client.ping()
        return {
            "ok": True,
            "status": "ok",
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        }
    except Exception as exc:  # pragma: no cover - defensive path for infra outages
        return {
            "ok": False,
            "status": "error",
            "latency_ms": round((perf_counter() - started) * 1000, 2),
            "error": str(exc),
        }
