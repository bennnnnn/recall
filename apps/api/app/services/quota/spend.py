"""Global UTC-day spend kill-switch (OpenRouter $).

Integer micro-dollars (1e-6 USD) so INCRBY stays atomic, rounded UP so no
paid call ever records as free. The previous unit was 1e-3 USD with
round(): a typical $0.0002-0.0005 free-chat turn recorded 0, and the cap
never saw free-tier traffic. 0-limit settings are unlimited (dev/tests).
Redis errors fail closed: treat as exceeded so we do not burn money while
the meter is blind.
"""

import logging
import math
from datetime import date

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.services.quota.counters import DAILY_TTL, utc_today

logger = logging.getLogger(__name__)

IMAGE_GEN_SPEND_USD = 0.03
WEB_SEARCH_CLASSIFIER_SPEND_USD = 0.001
REFERENCE_RESOLVER_SPEND_USD = 0.001
# Tavily image search + one SSRF-safe fetch (cheaper than image-gen, still billed).
IMAGE_SEARCH_SPEND_USD = 0.01
# One scan read-back: Mathpix, plus a vision call when the page needs it.
MATH_SCAN_READ_SPEND_USD = 0.005
STT_SPEND_USD = 0.01
TTS_SPEND_USD = 0.015
LIVE_TALK_SESSION_SPEND_USD = 0.03
LIVE_TALK_TURN_SPEND_USD = 0.08

_MICRO_USD_PER_USD = 1_000_000
# Pre-fix counter (1e-3 USD units). Still read so a mid-day deploy keeps the
# day's total; it expires with DAILY_TTL and can be dropped after that.
_LEGACY_SPEND_UNITS_TO_MICRO_USD = 1_000


def _spend_key(day: date | None = None) -> str:
    return f"spend_musd:{(day or utc_today()).isoformat()}"


def _legacy_spend_key(day: date | None = None) -> str:
    return f"spend_mcents:{(day or utc_today()).isoformat()}"


def _usd_to_micro_usd(usd: float) -> int:
    if usd <= 0:
        return 0
    # round() first strips float noise (0.0004 * 1e6 = 400.00000000000006).
    return max(1, math.ceil(round(usd * _MICRO_USD_PER_USD, 6)))


async def record_global_spend(redis: Redis, usd: float) -> int:
    """Add estimated dollars to today's global spend counter. Returns micro-USD."""
    amount = _usd_to_micro_usd(usd)
    if amount <= 0:
        return await get_global_spend_micro_usd(redis)
    key = _spend_key()
    new_total = await redis.incrby(key, amount)
    if new_total == amount:
        await redis.expire(key, DAILY_TTL)
    return new_total


async def get_global_spend_micro_usd(redis: Redis) -> int:
    value = await redis.get(_spend_key())
    legacy = await redis.get(_legacy_spend_key())
    return int(value or 0) + int(legacy or 0) * _LEGACY_SPEND_UNITS_TO_MICRO_USD


async def global_spend_exceeded(redis: Redis, settings: Settings) -> bool:
    """True when today's spend is at/over the cap, or Redis is down and a cap is set."""
    if settings.daily_global_spend_usd <= 0:
        return False
    limit = _usd_to_micro_usd(settings.daily_global_spend_usd)
    try:
        return await get_global_spend_micro_usd(redis) >= limit
    except RedisError:
        logger.warning("Global spend check failed; treating as exceeded", exc_info=True)
        return True


async def record_voice_spend(redis: Redis, usd: float) -> None:
    """Best-effort: voice cost must not fail the user path if Redis is unhappy."""
    try:
        await record_global_spend(redis, usd)
    except Exception:
        logger.exception("record_voice_spend failed")
