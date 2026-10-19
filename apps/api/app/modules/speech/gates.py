"""The gates a paid speech request passes before it spends: plan, spend cap, rate, day.

Each raises the HTTP error the phone already handles: 403 opens the paywall, 429
says which limit it hit. Callers keep their own order of checks.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.rate_limit import allow_request_fail_closed
from app.models.orm import User
from app.modules.billing import can_use
from app.modules.billing.entitlements import Feature
from app.services import quota as quota_service
from app.services.quota import counters

# Speech's per-day counters in ``services/quota/counters.COUNTERS``.
SpeechCounter = Literal["speech_tts", "speech_transcription"]

_RATE_WINDOW_SECONDS = 60


def require_plan_feature(user: User, settings: Settings, feature: Feature, message: str) -> None:
    """Refuse a feature the user's plan does not include (403 opens the paywall)."""
    if not can_use(user, feature, settings):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


async def require_voice_spend_ok(redis: Redis, settings: Settings) -> None:
    """Refuse while the global provider-spend breaker is open."""
    if await quota_service.global_spend_exceeded(redis, settings):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=quota_service.VOICE_SPEND_CAP_MESSAGE,
        )


async def require_speech_rate(redis: Redis, settings: Settings, key: str, message: str) -> None:
    """At most ``speech_rate_limit_per_minute`` requests a minute under *key* (0 is off).

    A Redis error denies the request (fail closed).
    """
    rate_limit = settings.speech_rate_limit_per_minute
    if rate_limit <= 0:
        return
    allowed = await allow_request_fail_closed(
        redis, key, limit=rate_limit, window_seconds=_RATE_WINDOW_SECONDS
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)


async def reserve_day_or_raise(
    counter: SpeechCounter, redis: Redis, user: User, settings: Settings
) -> date:
    """Take one of today's *counter* slots; 429 with the plan's message at the cap."""
    day = await counters.reserve(counter, redis, user, settings)
    if not day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=counters.limit_message(counter, user),
        )
    return day


class RefundDayOnFailure:
    """``async with``: give a reserved slot back to its day when the block fails.

    A 429 HTTPException keeps the slot (a cap refusal is not a failed request);
    any other HTTPException, error or cancellation refunds it. Without a *day*
    (nothing was reserved) nothing is refunded. The block's exception always
    propagates. A class rather than ``@asynccontextmanager``, whose generator
    would turn a StopAsyncIteration out of Redis into a RuntimeError.
    """

    def __init__(
        self, counter: SpeechCounter, redis: Redis, user_id: UUID, day: date | None
    ) -> None:
        self.counter: SpeechCounter = counter
        self.redis = redis
        self.user_id = user_id
        self.day = day

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: object
    ) -> None:
        if exc is None or not self.day:
            return
        if isinstance(exc, HTTPException):
            if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                return
        elif not isinstance(exc, asyncio.CancelledError | Exception):
            return
        await counters.refund(self.counter, self.redis, self.user_id, day=self.day)
