from functools import lru_cache

import redis.asyncio as redis

from app.core.config import get_settings

# Request-path commands should fail fast. The jobs consumer uses a longer
# socket_timeout so XREADGROUP BLOCK (5s) does not race the socket deadline.
_REQUEST_SOCKET_TIMEOUT_S = 5.0
_JOBS_SOCKET_TIMEOUT_S = 15.0


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
        socket_timeout=_REQUEST_SOCKET_TIMEOUT_S,
        health_check_interval=30,
    )


@lru_cache
def get_jobs_redis_client() -> redis.Redis:
    """Redis client for the jobs worker loop (long-poll XREADGROUP)."""
    settings = get_settings()
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=_JOBS_SOCKET_TIMEOUT_S,
        health_check_interval=30,
    )
