from redis.asyncio import Redis


async def allow_request(redis: Redis, key: str, *, limit: int, window_seconds: int) -> bool:
    """Increment a windowed counter; expire on first hit.

    INCR and EXPIRE run in one pipeline so a crash between them cannot leave a
    counter key with no TTL (permanent rate-limit for that bucket).
    """
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = await pipe.execute()
    return int(count) <= limit
