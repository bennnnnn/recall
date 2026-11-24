"""The gates a paid speech request passes before it spends: plan, spend cap, rate, day
(read-aloud: its tokens).

Each raises a ``SpeechRefusedError`` (a ``DomainError``): 403 opens the paywall, 429
says which limit it hit. Callers keep their own order of checks.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import status
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.rate_limit import allow_request_unless_down
from app.exceptions import DomainError
from app.models.orm import User
from app.modules.billing import can_use
from app.modules.billing.entitlements import Feature
from app.services import quota as quota_service
from app.services.quota import counters
from app.services.quota.messages import SPEECH_TTS_LIMIT_EXCEEDED_MESSAGE

# Speech's per-day counter in ``services/quota/counters.COUNTERS``: read-aloud has none,
# its tokens are charged instead (``charge_tts_tokens``).
SpeechCounter = Literal["speech_transcription"]

_CHARS_PER_TOKEN = 4

_RATE_WINDOW_SECONDS = 60


class SpeechRefusedError(DomainError):
    """A speech or live talk request refused before it spends."""


def require_plan_feature(user: User, settings: Settings, feature: Feature, message: str) -> None:
    """Refuse a feature the user's plan does not include (403 opens the paywall)."""
    if not can_use(user, feature, settings):
        raise SpeechRefusedError(message, status_code=status.HTTP_403_FORBIDDEN, code="not_in_plan")


async def require_voice_spend_ok(redis: Redis, settings: Settings) -> None:
    """Refuse while the global provider-spend breaker is open."""
    if await quota_service.global_spend_exceeded(redis, settings):
        raise SpeechRefusedError(
            quota_service.VOICE_SPEND_CAP_MESSAGE,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="voice_spend_cap",
        )


async def require_speech_rate(redis: Redis, settings: Settings, key: str, message: str) -> None:
    """At most ``speech_rate_limit_per_minute`` requests a minute under *key* (0 is off).

    A Redis error denies the request (fail closed) with ``RedisUnavailableError``: 503
    unavailable, never ``speech_rate_limited``, which live talk words as the month's
    minutes used up.
    """
    rate_limit = settings.speech_rate_limit_per_minute
    if rate_limit <= 0:
        return
    allowed = await allow_request_unless_down(
        redis, key, limit=rate_limit, window_seconds=_RATE_WINDOW_SECONDS
    )
    if not allowed:
        raise SpeechRefusedError(
            message, status_code=status.HTTP_429_TOO_MANY_REQUESTS, code="speech_rate_limited"
        )


async def reserve_day_or_raise(
    counter: SpeechCounter, redis: Redis, user: User, settings: Settings
) -> date:
    """Take one of today's *counter* slots; 429 with the plan's message at the cap."""
    day = await counters.reserve(counter, redis, user, settings)
    if not day:
        raise SpeechRefusedError(
            counters.limit_message(counter, user),
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="daily_limit",
            feature=counter,
        )
    return day


class RefundOnFailure:
    """``async with``: give back what a request took (a day's slot, read-aloud's tokens)
    when the block fails.

    A 429 refusal keeps it (a cap refusal is not a failed request), and so does any
    failure once the provider was asked (``spend``): the provider may bill a call that
    errored, returned nothing usable or was cut short by a cancel. It refunded those,
    so a client that hung up mid-call, or audio the provider turns away after upload,
    never used up the day. Any other refusal, error or cancellation (before the call)
    gives it back. With nothing to give back (*give_back* None) nothing happens. The
    block's exception always propagates. A class rather than
    ``@asynccontextmanager``, whose generator would turn a StopAsyncIteration out of
    Redis into a RuntimeError.
    """

    def __init__(self, give_back: Callable[[], Awaitable[None]] | None) -> None:
        self._give_back = give_back
        self.spent = False

    def spend(self) -> None:
        """The provider is being asked: from here a failure keeps what was taken."""
        self.spent = True

    async def __aenter__(self) -> RefundOnFailure:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: object
    ) -> None:
        if exc is None or self._give_back is None or self.spent:
            return
        # A refusal from the gates or the route (an HTTPException) names its status.
        if getattr(exc, "status_code", None) == status.HTTP_429_TOO_MANY_REQUESTS:
            return
        if not isinstance(exc, asyncio.CancelledError | Exception):
            return
        await self._give_back()


def refund_day_on_failure(
    counter: SpeechCounter, redis: Redis, user_id: UUID, day: date | None
) -> RefundOnFailure:
    """``RefundOnFailure`` for a slot of *counter* taken on *day* (None: none taken)."""
    if not day:
        return RefundOnFailure(None)
    return RefundOnFailure(lambda: counters.refund(counter, redis, user_id, day=day))


def tts_tokens(text: str) -> int:
    """What read-aloud charges to the day's token budget: the text's tokens, about four
    characters each (the same reckoning a prompt's estimate uses), at least one."""
    return max(1, -(-len(text) // _CHARS_PER_TOKEN))


async def charge_tts_tokens(
    redis: Redis, user: User, settings: Settings, text: str
) -> RefundOnFailure:
    """Take read-aloud's tokens from today's budget (it has no daily count of its own);
    429 ``daily_limit`` when what is left cannot cover them. The returned guard gives
    them back if the request fails before the provider is asked."""
    wanted = tts_tokens(text)
    owner = str(user.id)
    granted = await quota_service.reserve_usage_up_to(
        redis, owner, wanted, daily_limit=quota_service.daily_limit_for_user(user, settings)
    )
    if granted < wanted:
        await quota_service.refund_usage(redis, owner, granted)
        raise SpeechRefusedError(
            SPEECH_TTS_LIMIT_EXCEEDED_MESSAGE,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="daily_limit",
            feature="speech_tts",
        )
    return RefundOnFailure(lambda: quota_service.refund_usage(redis, owner, granted))
