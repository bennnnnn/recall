import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


async def allow_request(redis: Redis, key: str, *, limit: int, window_seconds: int) -> bool:
    """Increment a windowed counter; expire on first hit.

    INCR and EXPIRE run in one pipeline so a crash between them cannot leave a
    counter key with no TTL (permanent rate-limit for that bucket).

    Requires Redis ≥ 7 for ``EXPIRE … NX`` (set TTL only when missing). Upstash
    and current Fly Redis satisfy this; without NX every hit would refresh the
    window and weaken the limit.
    """
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = await pipe.execute()
    return int(count) <= limit


async def allow_request_fail_closed(
    redis: Redis, key: str, *, limit: int, window_seconds: int
) -> bool:
    """Like ``allow_request``, but Redis errors deny the request (fail closed).

    Matches REST middleware / WS handshake: an outage must not silently remove
    the rate limit. Callers should translate ``False`` into HTTP 429.
    """
    try:
        return await allow_request(redis, key, limit=limit, window_seconds=window_seconds)
    except Exception:
        logger.warning("Rate limit check failed; failing closed key=%s", key, exc_info=True)
        return False
