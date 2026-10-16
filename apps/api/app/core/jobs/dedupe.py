"""Run a logical job once: the claim on ``jobdone:<dedupe_key>``."""

import asyncio
import logging

from redis.asyncio import Redis

logger = logging.getLogger("app.core.jobs")

# Idempotency: SET NX before dispatch so reclaim/duplicate enqueue cannot
# double-apply side effects (duplicate todos, welcome emails, …).
# In-flight value is _DEDUPE_RUNNING with a short TTL; success overwrites with
# _DEDUPE_DONE for 24h. A reclaim that loses NX must not xack while the key
# is still running — that was a guaranteed drop: reclaim idle is 60s and the
# running TTL is 300s, so skip+xack acknowledged the PEL entry forever.
_JOB_DONE_PREFIX = "jobdone:"
_JOB_DONE_TTL_SECONDS = 86_400
# Covers a normal handler (LLM / index batch). A keepalive refreshes this
# while the handler runs so a slow index does not expire and double-run.
# After a crash, the key expires and the next XAUTOCLAIM can NX-succeed.
_JOB_DONE_CLAIM_TTL_SECONDS = 300
_DEDUPE_RUNNING = "1"
_DEDUPE_DONE = "done"


def job_done_key(dedupe_key: str) -> str:
    return f"{_JOB_DONE_PREFIX}{dedupe_key}"


async def _claim_dedupe(
    redis: Redis, dedupe_key: str | None, *, ttl: int = _JOB_DONE_CLAIM_TTL_SECONDS
) -> bool:
    """Return True if this worker should run the job (or there is no dedupe).

    Uses a short TTL so a worker that crashes mid-handler doesn't pin the
    key for 24h — the claim expires and a later reclaim can NX-succeed.
    """
    if not dedupe_key:
        return True
    try:
        claimed = await redis.set(
            job_done_key(dedupe_key),
            _DEDUPE_RUNNING,
            ex=ttl,
            nx=True,
        )
    except Exception:
        # Fail open: never drop work because Redis SET blipped.
        logger.debug("job dedupe claim failed key=%s", dedupe_key, exc_info=True)
        return True
    return bool(claimed)


async def _dedupe_is_complete(redis: Redis, dedupe_key: str | None) -> bool:
    """True when a later duplicate should skip and ack (handler already succeeded)."""
    if not dedupe_key:
        return False
    key = job_done_key(dedupe_key)
    try:
        value = await redis.get(key)
        if value == _DEDUPE_DONE:
            return True
        if value != _DEDUPE_RUNNING:
            return False
        ttl = await redis.ttl(key)
        # Pre-fix success only EXPIREd "1" to 24h. Treat a long TTL as done so
        # a rolling deploy does not leave those duplicates pending for a day.
        return isinstance(ttl, int) and ttl > _JOB_DONE_CLAIM_TTL_SECONDS
    except Exception:
        logger.debug("job dedupe state read failed key=%s", dedupe_key, exc_info=True)
        return False


async def _extend_dedupe(redis: Redis, dedupe_key: str | None) -> None:
    """Mark the logical job done so later duplicates skip and ack."""
    if not dedupe_key:
        return
    try:
        await redis.set(
            job_done_key(dedupe_key),
            _DEDUPE_DONE,
            ex=_JOB_DONE_TTL_SECONDS,
        )
    except Exception:
        logger.debug("job dedupe extend failed key=%s", dedupe_key, exc_info=True)


async def _refresh_running_claim(redis: Redis, dedupe_key: str | None) -> None:
    """Keep an in-flight claim alive across a slow handler."""
    if not dedupe_key:
        return
    key = job_done_key(dedupe_key)
    try:
        current = await redis.get(key)
        if current == _DEDUPE_RUNNING:
            await redis.expire(key, _JOB_DONE_CLAIM_TTL_SECONDS)
    except Exception:
        logger.debug("job dedupe refresh failed key=%s", dedupe_key, exc_info=True)


async def _refresh_running_claim_loop(redis: Redis, dedupe_key: str) -> None:
    interval = max(1, _JOB_DONE_CLAIM_TTL_SECONDS // 2)
    while True:
        await asyncio.sleep(interval)
        await _refresh_running_claim(redis, dedupe_key)


async def _release_dedupe(redis: Redis, dedupe_key: str | None) -> None:
    if not dedupe_key:
        return
    try:
        await redis.delete(job_done_key(dedupe_key))
    except Exception:
        logger.debug("job dedupe release failed key=%s", dedupe_key, exc_info=True)
