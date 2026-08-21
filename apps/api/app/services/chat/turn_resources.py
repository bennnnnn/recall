import asyncio
import contextlib
import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.exceptions import ChatBusyError, ChatServiceError, QuotaExceededError
from app.models.orm import User
from app.services.chat.prompt_builder import StreamStatusFn
from app.services.chat.turn_prep import StreamContext
from app.services.chat.turn_timing import TurnTimingTracker
from app.services.quota import quota_exceeded_message

CHATPREP_LOCK_TTL_SECONDS = 120
CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS = 30.0


@dataclass
class TurnResources:
    """Prepare-lock and quota ownership for one chat turn."""

    redis: Redis
    user_id: UUID
    chat_id: UUID
    lock_key: str
    lock_token: str
    reserved_tokens: int = 0
    _refunded: bool = False
    seams: Any = None

    async def reserve(self, **kwargs: Any) -> int:
        if self.seams is None:
            from app.services.chat import stream

            self.seams = stream
        self.reserved_tokens = await self.seams.reserve_turn_quota(self.redis, **kwargs)
        return self.reserved_tokens

    async def refund(self) -> None:
        if self._refunded or self.reserved_tokens <= 0:
            return
        if self.seams is None:
            from app.services.chat import stream

            self.seams = stream
        self._refunded = True
        await self.seams.quota_service.refund_usage(
            self.redis, str(self.user_id), self.reserved_tokens
        )


async def acquire_chatprep_lock(seams: Any, redis: Redis, chat_id: UUID) -> tuple[str, str]:
    lock_key = f"chatprep:{chat_id}"
    token = await seams.acquire_lock(redis, lock_key, seams._CHATPREP_LOCK_TTL_SECONDS)
    if token is None:
        raise ChatBusyError()
    return lock_key, token


@asynccontextmanager
async def turn_resources(
    seams: Any,
    redis: Redis,
    *,
    user_id: UUID,
    chat_id: UUID,
    borrowed: TurnResources | None = None,
) -> AsyncIterator[TurnResources]:
    if borrowed is not None:
        yield borrowed
        return

    lock_key, lock_token = await acquire_chatprep_lock(seams, redis, chat_id)
    resources = TurnResources(
        seams=seams,
        redis=redis,
        user_id=user_id,
        chat_id=chat_id,
        lock_key=lock_key,
        lock_token=lock_token,
    )
    refresh_task = asyncio.create_task(
        chatprep_refresh_loop(seams, redis, lock_key, lock_token),
        name="chatprep-refresh",
    )
    try:
        yield resources
    except BaseException:
        await resources.refund()
        raise
    finally:
        refresh_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, ChatServiceError, Exception):
            await refresh_task
        await seams.release_lock(redis, lock_key, lock_token)


async def chatprep_refresh_loop(seams: Any, redis: Redis, lock_key: str, lock_token: str) -> None:
    try:
        while True:
            await asyncio.sleep(seams._CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS)
            ok = await seams.refresh_lock(
                redis,
                lock_key,
                lock_token,
                seams._CHATPREP_LOCK_TTL_SECONDS,
            )
            if not ok:
                raise ChatServiceError("Chat prepare lock lost during turn")
    except asyncio.CancelledError:
        return


async def yield_with_chatprep_refresh(
    seams: Any,
    redis: Redis,
    lock_key: str,
    lock_token: str,
    tokens: AsyncIterator[str],
) -> AsyncIterator[str]:
    last_refresh = 0.0
    import time

    async for token in tokens:
        now = time.monotonic()
        if now - last_refresh >= seams._CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS:
            ok = await seams.refresh_lock(
                redis,
                lock_key,
                lock_token,
                seams._CHATPREP_LOCK_TTL_SECONDS,
            )
            if not ok:
                raise ChatServiceError("Chat prepare lock lost during stream")
            last_refresh = now
        yield token


def wrap_stream_status(
    timing: TurnTimingTracker | None,
    on_status: StreamStatusFn | None,
) -> StreamStatusFn | None:
    if timing is None and on_status is None:
        return None

    async def emit(phase: str, detail: str | None = None) -> None:
        if timing is not None:
            timing.mark_phase(phase)
        if on_status is not None:
            await on_status(phase, detail)

    return emit


def weighted_reserve_tokens(
    seams: Any,
    *,
    content: str,
    model: str,
    settings: Settings,
    max_output: int | None = None,
    vision_extra: int = 0,
) -> int:
    base = seams.estimate_tokens(content) + (
        max_output if max_output is not None else settings.max_output_tokens
    )
    base += vision_extra
    return math.ceil(base * seams.model_catalog.quota_multiplier(model))


def prompt_weighted_reserve_tokens(
    seams: Any,
    prompt_messages: list[dict[str, Any]],
    *,
    model: str,
    settings: Settings,
    max_output: int | None = None,
) -> int:
    prompt_tokens = sum(
        seams.estimate_tokens(content)
        for message in prompt_messages
        if isinstance((content := message.get("content")), str)
    )
    base = prompt_tokens + (max_output if max_output is not None else settings.max_output_tokens)
    return math.ceil(base * seams.model_catalog.quota_multiplier(model))


async def top_up_reserve_for_prompt(
    seams: Any,
    res: TurnResources,
    *,
    settings: Settings,
    ctx: StreamContext,
    daily_limit: int,
) -> None:
    messages = ctx.prompt_messages
    if not isinstance(messages, list):
        return
    needed = seams.prompt_weighted_reserve_tokens(
        messages,
        model=ctx.model,
        settings=settings,
        max_output=ctx.max_output_tokens,
    )
    extra = needed - res.reserved_tokens
    if extra <= 0:
        return
    ok = await seams.quota_service.reserve_usage(
        res.redis,
        str(res.user_id),
        extra,
        daily_limit=daily_limit,
    )
    if not ok:
        raise QuotaExceededError(quota_exceeded_message(ctx.user) if ctx.user is not None else "")
    res.reserved_tokens = needed
    ctx.reserved_tokens = needed


async def reserve_turn_quota(
    seams: Any,
    redis: Redis,
    *,
    user: User,
    content: str,
    model: str,
    settings: Settings,
    daily_limit: int | None = None,
    max_output: int | None = None,
    vision_extra: int = 0,
    seed: bool = True,
) -> int:
    if seed:
        async with seams.SessionLocal() as session:
            await seams.seed_usage_from_db(redis, session, user.id)
    if daily_limit is None:
        daily_limit = seams.quota_service.daily_limit_for_user(user, settings)
    reserved = seams.weighted_reserve_tokens(
        content=content,
        model=model,
        settings=settings,
        max_output=max_output,
        vision_extra=vision_extra,
    )
    if not await seams.quota_service.reserve_usage(
        redis, str(user.id), reserved, daily_limit=daily_limit
    ):
        raise QuotaExceededError(quota_exceeded_message(user))
    return reserved
