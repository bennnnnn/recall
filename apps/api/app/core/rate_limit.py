from redis.asyncio import Redis


async def allow_request(redis: Redis, key: str, *, limit: int, window_seconds: int) -> bool:
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    return count <= limit
