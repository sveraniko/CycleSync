from redis.asyncio import Redis


def create_redis_client(redis_dsn: str) -> Redis:
    return Redis.from_url(redis_dsn, decode_responses=True)


async def redis_healthcheck(client: Redis) -> bool:
    try:
        await client.ping()
        return True
    except Exception:
        return False
