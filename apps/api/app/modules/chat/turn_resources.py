import asyncio
import contextlib
import logging
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
from app.modules.chat.post_turn import seed_usage_from_db
from app.modules.chat.prompt_builder import StreamStatusFn
from app.modules.chat.turn_deps import ChatTurnDeps
from app.modules.chat.turn_prep import StreamContext
from app.modules.chat.turn_timing import TurnTimingTracker
from app.services import model_catalog
from app.services.context_window import estimate_tokens
from app.services.quota import quota_exceeded_message

logger = logging.getLogger(__name__)

# The refresh is the owner's heartbeat: a machine that dies mid-turn leaves the
# lock for at most one TTL (the phone's next send gets ``busy`` until then), so
# it stays short and is refreshed three times a TTL.
CHATPREP_LOCK_TTL_SECONDS = 30
CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS = 10.0


@dataclass
class TurnResources:
    """Prepare-lock and quota ownership for one chat turn."""

    deps: ChatTurnDeps
    redis: Redis
    user_id: UUID
    chat_id: UUID
    lock_key: str
    lock_token: str
    reserved_tokens: int = 0
    _refunded: bool = False

    async def reserve(
        self,
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
        self.reserved_tokens = await reserve_turn_quota(
            self.deps,
            self.redis,
            user=user,
            content=content,
            model=model,
            settings=settings,
            daily_limit=daily_limit,
            max_output=max_output,
            vision_extra=vision_extra,
            seed=seed,
        )
        return self.reserved_tokens

    async def refund(self) -> None:
        if self._refunded or self.reserved_tokens <= 0:
            return
        self._refunded = True
        await self.deps.quota.refund_usage(self.redis, str(self.user_id), self.reserved_tokens)


async def acquire_chatprep_lock(deps: ChatTurnDeps, redis: Redis, chat_id: UUID) -> tuple[str, str]:
    lock_key = f"chatprep:{chat_id}"
    token = await deps.locks.acquire_lock(redis, lock_key, CHATPREP_LOCK_TTL_SECONDS)
    if token is None:
        raise ChatBusyError()
    return lock_key, token


@asynccontextmanager
async def turn_resources(
    deps: ChatTurnDeps,
    redis: Redis,
    *,
    user_id: UUID,
    chat_id: UUID,
    borrowed: TurnResources | None = None,
) -> AsyncIterator[TurnResources]:
    if borrowed is not None:
        yield borrowed
        return

    lock_key, lock_token = await acquire_chatprep_lock(deps, redis, chat_id)
    resources = TurnResources(
        deps=deps,
        redis=redis,
        user_id=user_id,
        chat_id=chat_id,
        lock_key=lock_key,
        lock_token=lock_token,
    )
    refresh_task = asyncio.create_task(
        chatprep_refresh_loop(resources),
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
        await deps.locks.release_lock(redis, lock_key, lock_token)


async def _refresh_chatprep_lock(res: TurnResources) -> bool:
    return await res.deps.locks.refresh_lock(
        res.redis,
        res.lock_key,
        res.lock_token,
        CHATPREP_LOCK_TTL_SECONDS,
    )


async def chatprep_refresh_loop(res: TurnResources) -> None:
    """Keep the prepare lock alive for the whole turn, through Redis blips.

    A failed or refused refresh is logged and retried on the next tick: it
    must never end the turn, whose reply is streaming and still has to save.
    """
    try:
        while True:
            await asyncio.sleep(CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS)
            try:
                if not await _refresh_chatprep_lock(res):
                    logger.warning("Chat prepare lock no longer held key=%s", res.lock_key)
            except Exception:
                logger.warning(
                    "Chat prepare lock refresh failed key=%s", res.lock_key, exc_info=True
                )
    except asyncio.CancelledError:
        return


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
    *,
    content: str,
    model: str,
    settings: Settings,
    max_output: int | None = None,
    vision_extra: int = 0,
) -> int:
    base = estimate_tokens(content) + (
        max_output if max_output is not None else settings.max_output_tokens
    )
    base += vision_extra
    return math.ceil(base * model_catalog.quota_multiplier(model))


def prompt_weighted_reserve_tokens(
    prompt_messages: list[dict[str, Any]],
    *,
    model: str,
    settings: Settings,
    max_output: int | None = None,
) -> int:
    prompt_tokens = sum(
        estimate_tokens(content)
        for message in prompt_messages
        if isinstance((content := message.get("content")), str)
    )
    base = prompt_tokens + (max_output if max_output is not None else settings.max_output_tokens)
    return math.ceil(base * model_catalog.quota_multiplier(model))


async def top_up_reserve_for_prompt(
    res: TurnResources,
    *,
    settings: Settings,
    ctx: StreamContext,
    daily_limit: int,
) -> None:
    # Soft-quota turns intentionally reserve 0 before generation and charge
    # actual usage after the response finishes. Do not reintroduce a strict
    # preauthorization here after the full prompt is assembled. A non-zero
    # reservation is a legacy/borrowed path and keeps the old top-up behavior.
    if res.reserved_tokens <= 0:
        ctx.reserved_tokens = 0
        return

    messages = ctx.prompt_messages
    if not isinstance(messages, list):
        return
    needed = prompt_weighted_reserve_tokens(
        messages,
        model=ctx.model,
        settings=settings,
        max_output=ctx.max_output_tokens,
    )
    extra = needed - res.reserved_tokens
    if extra <= 0:
        return
    ok = await res.deps.quota.reserve_usage(
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
    deps: ChatTurnDeps,
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
    """Soft-enforce the daily chat quota before generation.

    Chat quota is a product guardrail, not a financial preauthorization. A turn
    that starts below the limit is allowed to finish even if its actual usage
    carries the user slightly over; finalize records the actual weighted usage
    and the *next* turn is blocked. Returning 0 tells the rest of the pipeline
    there is no pre-reserved amount to top up or refund.

    Account-wide chat rate limiting remains the abuse backstop for many
    concurrent chats. ``seed`` is kept for compatibility with regenerate and
    legacy callers; the normal chat path only seeds when today's Redis counter
    is missing, so ordinary sends stay on the cheap Redis path.
    """
    _ = (content, model, max_output, vision_extra)
    if seed:
        async with deps.session_factory() as session:
            await seed_usage_from_db(redis, session, user.id)
    if daily_limit is None:
        daily_limit = deps.quota.daily_limit_for_user(user, settings)
    used = await deps.quota.get_daily_usage(redis, str(user.id))
    if used >= daily_limit:
        raise QuotaExceededError(quota_exceeded_message(user))
    return 0
