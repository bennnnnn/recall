from functools import lru_cache

import redis.asyncio as redis

from app.core.config import get_settings


@lru_cache
def get_redis_client() -> redis.Redis:
    settings = get_settings()
    # Fail fast on transient Upstash/network blips instead of hanging the
    # request path: a 5s connect timeout + 5s command timeout covers quota,
    # job enqueue, rate limits, and locks. health_check_interval keeps idle
    # pooled connections from going stale behind a network flap.
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
    )
