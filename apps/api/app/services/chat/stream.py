import asyncio
import contextlib
import json
import logging
import math
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.background_tasks import create_background_task
from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.ids import uuid7
from app.core.redis_lock import acquire_lock, refresh_lock, release_lock
from app.exceptions import (
    ChatBusyError,
    ChatNotFoundError,
    ChatServiceError,
    QuotaExceededError,
)
from app.gateways import litellm_gateway
from app.gateways.litellm_gateway import ModelUnavailableError
from app.models.orm import User
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import users as users_repo
from app.services import attachment_lifecycle, model_catalog
from app.services import calendar as calendar_service
from app.services import image_generation as image_generation_service
from app.services import math_fence as math_fence_service
from app.services import plan as plan_service
from app.services import quota as quota_service
from app.services import todos as todos_service
from app.services import web_search as web_search_service
from app.services.chat.finalize_registry import (
    mark_pending_finalize,
    register_pending_finalize,
    wait_for_pending_finalize,
)
from app.services.chat.post_turn import (
    enqueue_post_turn_jobs,
    finalize_stream_turn_db,
    restore_regenerate_backup,
    seed_usage_from_db,
)
from app.services.chat.prompt_builder import StreamReasoningFn, StreamStatusFn
from app.services.chat.turn_prep import (
    RegenerateBackup,
    StreamContext,
    build_stream_prompt_context,
    count_image_attachments,
    prepare_chat_turn,
    stream_context_from_bundle,
    vision_reserve_tokens,
)
from app.services.chat.turn_timing import TurnTimingTracker
from app.services.context_window import estimate_tokens
from app.services.image_gen_intent import (
    extract_image_gen_prompt,
    extract_image_revision_prompt,
    image_gen_revision_context,
)
from app.services.quota import quota_exceeded_message

logger = logging.getLogger(__name__)

# Same token-based Redis lock as compaction; covers prepare + stream so two
# concurrent connections cannot race prepare_chat_turn on one chat.
_CHATPREP_LOCK_TTL_SECONDS = 120
# Refresh well under TTL so a slow provider turn cannot let a second request
# acquire the same chat mid-stream.
_CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS = 30.0


async def _acquire_chatprep_lock(redis: Redis, chat_id: UUID) -> tuple[str, str]:
    """Acquire per-chat prepare lock; raise ChatBusyError if already held."""
    lock_key = f"chatprep:{chat_id}"
    token = await acquire_lock(redis, lock_key, _CHATPREP_LOCK_TTL_SECONDS)
    if token is None:
        raise ChatBusyError()
    return lock_key, token


@dataclass
class TurnResources:
    """The two resources one turn holds: the prepare lock and reserved quota.

    Both must be released exactly once on every exit path, including
    ``CancelledError`` (a WS/SSE disconnect), or the user's daily quota leaks
    or the chat stays locked. ``reserve`` records the hold so the owning
    ``turn_resources`` block refunds it if the turn raises; a turn that reaches
    finalize keeps the hold, because finalize reconciles real usage.
    """

    redis: Redis
    user_id: UUID
    chat_id: UUID
    lock_key: str
    lock_token: str
    reserved_tokens: int = 0
    _refunded: bool = False

    async def reserve(self, **kwargs: Any) -> int:
        """Reserve daily quota for this turn and take ownership of the refund."""
        self.reserved_tokens = await reserve_turn_quota(self.redis, **kwargs)
        return self.reserved_tokens

    async def refund(self) -> None:
        """Refund the outstanding hold, at most once."""
        if self._refunded or self.reserved_tokens <= 0:
            return
        self._refunded = True
        await quota_service.refund_usage(self.redis, str(self.user_id), self.reserved_tokens)


@asynccontextmanager
async def turn_resources(
    redis: Redis,
    *,
    user_id: UUID,
    chat_id: UUID,
    borrowed: "TurnResources | None" = None,
) -> AsyncIterator[TurnResources]:
    """Own the prepare lock + quota reservation for one turn.

    ``borrowed`` lets one entry point hand its already-acquired resources to
    another (edit delegates to ``stream_chat_response`` while still holding the
    lock across its destructive delete). The borrower must not release or
    refund — the original owner's block still does, exactly once.
    """
    if borrowed is not None:
        yield borrowed
        return

    lock_key, lock_token = await _acquire_chatprep_lock(redis, chat_id)
    resources = TurnResources(
        redis=redis,
        user_id=user_id,
        chat_id=chat_id,
        lock_key=lock_key,
        lock_token=lock_token,
    )
    refresh_task = asyncio.create_task(
        _chatprep_refresh_loop(redis, lock_key, lock_token),
        name="chatprep-refresh",
    )
    try:
        yield resources
    except BaseException:
        # CancelledError is a BaseException on 3.12 — a hard WS/SSE disconnect
        # must still refund, or the reservation is charged for a turn that
        # never produced a reply.
        await resources.refund()
        raise
    finally:
        refresh_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await refresh_task
        await release_lock(redis, lock_key, lock_token)


async def _chatprep_refresh_loop(redis: Redis, lock_key: str, lock_token: str) -> None:
    """Keep the prepare lock alive through prompt gather and the tool loop."""
    try:
        while True:
            await asyncio.sleep(_CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS)
            try:
                await refresh_lock(redis, lock_key, lock_token, _CHATPREP_LOCK_TTL_SECONDS)
            except Exception:
                logger.debug("chatprep lock refresh failed", exc_info=True)
    except asyncio.CancelledError:
        return


async def _yield_with_chatprep_refresh(
    redis: Redis,
    lock_key: str,
    lock_token: str,
    tokens: AsyncIterator[str],
) -> AsyncIterator[str]:
    last_refresh = 0.0
    async for token in tokens:
        now = time.monotonic()
        if now - last_refresh >= _CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS:
            try:
                await refresh_lock(redis, lock_key, lock_token, _CHATPREP_LOCK_TTL_SECONDS)
            except Exception:
                logger.debug("chatprep lock refresh failed", exc_info=True)
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
    """Reserve against the assembled prompt, not just the latest user line."""
    prompt_tokens = 0
    for message in prompt_messages:
        content = message.get("content")
        if isinstance(content, str):
            prompt_tokens += estimate_tokens(content)
    base = prompt_tokens + (max_output if max_output is not None else settings.max_output_tokens)
    return math.ceil(base * model_catalog.quota_multiplier(model))


async def _top_up_reserve_for_prompt(
    res: TurnResources,
    *,
    settings: Settings,
    ctx: StreamContext,
    daily_limit: int,
) -> None:
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
    ok = await quota_service.reserve_usage(
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
    """Seed usage (optional) then reserve weighted tokens; raise on quota exceed."""
    if seed:
        async with SessionLocal() as session:
            await seed_usage_from_db(redis, session, user.id)
    if daily_limit is None:
        daily_limit = quota_service.daily_limit_for_user(user, settings)
    reserved = weighted_reserve_tokens(
        content=content,
        model=model,
        settings=settings,
        max_output=max_output,
        vision_extra=vision_extra,
    )
    if not await quota_service.reserve_usage(
        redis, str(user.id), reserved, daily_limit=daily_limit
    ):
        raise QuotaExceededError(quota_exceeded_message(user))
    return reserved


async def _try_image_gen_for_turn(
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    content: str,
    result: dict[str, Any] | None,
    create_user_message: bool,
    replace_assistant_id: UUID | None = None,
) -> bool:
    """If content is Pro image-gen intent, generate and fill ``result``.

    Returns True when the turn was handled (caller must not run the LLM).
    Free users / non-image text return False so the chat model can reply.
    """
    if not plan_service.is_pro(user):
        return False
    image_prompt = extract_image_gen_prompt(content)
    if not image_prompt:
        # Short follow-ups ("White", "make it blue") after an image-only reply.
        # extract_image_revision_prompt rejects >120 chars or >8 tokens on
        # text alone — skip the 20-row lookup for ordinary messages.
        trimmed = content.strip()
        if not trimmed or len(trimmed) > 120 or len(trimmed.split()) > 8:
            return False
        async with SessionLocal() as session:
            recent = await messages_repo.list_recent(session, chat_id, limit=20)
        last_image_only, previous_subject = image_gen_revision_context(recent)
        image_prompt = extract_image_revision_prompt(
            content,
            last_assistant_is_image_only=last_image_only,
            previous_subject=previous_subject,
        )
    if not image_prompt:
        return False
    try:
        # generate_for_chat opens its own short-lived sessions around DB work
        # and keeps none open during the provider HTTP call. Do not delete the
        # prior assistant first — 403/404 soft-fail cannot restore it.
        _user_msg, asst_msg = await image_generation_service.generate_for_chat(
            settings,
            user=user,
            chat_id=chat_id,
            prompt=image_prompt,
            user_message_content=content.strip() if create_user_message else None,
            create_user_message=create_user_message,
        )
    except image_generation_service.ImageGenerationError as exc:
        if exc.status_code == 429:
            raise QuotaExceededError(exc.detail) from exc
        if exc.status_code in (403, 404):
            # Not available / not Pro — let the chat model explain.
            return False
        raise ChatServiceError(exc.detail) from exc

    if replace_assistant_id is not None:
        async with SessionLocal() as session:
            old = await messages_repo.get_by_id(session, replace_assistant_id, chat_id)
            if old is not None and old.role == "assistant":
                await messages_repo.delete_message(session, old)

    if result is not None:
        result["message_id"] = str(asst_msg.id)
        result["final_content"] = asst_msg.content
        result["resolved_model"] = asst_msg.model or "image-gen-model"
    return True


async def stream_chat_response(
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    content: str,
    model_alias: str | None = None,
    attachment_ids: list[UUID] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, Any] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
    user: User | None = None,
    skip_usage_seed: bool = False,
    resources: TurnResources | None = None,
) -> AsyncIterator[str]:
    content = content.strip()
    if not content and not attachment_ids:
        raise ChatNotFoundError("Message cannot be empty.")

    timing = TurnTimingTracker()
    timing.mark_phase("turn_start")
    status = wrap_stream_status(timing, on_status)

    # `resources` is set when edit already reserved quota and holds the lock; it
    # keeps ownership, so nothing here releases or refunds on its behalf.
    async with turn_resources(redis, user_id=user_id, chat_id=chat_id, borrowed=resources) as res:
        # The previous turn's DB commit may still be in flight (done is sent
        # before it lands) — wait so this turn's prompt sees that reply.
        await wait_for_pending_finalize(chat_id, redis)

        async with SessionLocal() as session:
            if user is None:
                user = await users_repo.get_by_id(session, user_id)
                if user is None:
                    raise ChatNotFoundError("User not found.")
            if not skip_usage_seed:
                await seed_usage_from_db(redis, session, user_id)
            daily_limit = quota_service.daily_limit_for_user(user, settings)
            model = plan_service.resolve_user_model_override(user, model_alias, content, settings)

        # Safety net: Pro image intent must never become an LLM stub that promises
        # an attachment. Client also intercepts; this covers regenerate + missed JS.
        if not attachment_ids and await _try_image_gen_for_turn(
            settings,
            user=user,
            chat_id=chat_id,
            content=content,
            result=result,
            create_user_message=True,
        ):
            # Image-gen has its own daily cap and consumes no chat-token quota,
            # so release the edit path's hold explicitly on this success exit.
            await res.refund()
            return

        if res.reserved_tokens <= 0:
            vision_extra = 0
            if attachment_ids:
                async with SessionLocal() as session:
                    image_count = await count_image_attachments(session, user_id, attachment_ids)
                vision_extra = vision_reserve_tokens(settings, image_count)
            await res.reserve(
                user=user,
                content=content,
                model=model,
                settings=settings,
                daily_limit=daily_limit,
                vision_extra=vision_extra,
                max_output=settings.max_output_tokens,
                seed=False,
            )

        ctx = await prepare_chat_turn(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            model_alias=model_alias,
            settings=settings,
            redis=redis,
            reserved_tokens=res.reserved_tokens,
            attachment_ids=attachment_ids or [],
            client_timezone=client_timezone,
            client_location=client_location,
            client_latitude=client_latitude,
            client_longitude=client_longitude,
            on_status=status,
            user=user,
            timing=timing,
        )
        await _top_up_reserve_for_prompt(res, settings=settings, ctx=ctx, daily_limit=daily_limit)

        async for token in _yield_with_chatprep_refresh(
            redis,
            res.lock_key,
            res.lock_token,
            stream_and_finalize(
                redis,
                settings,
                ctx,
                should_cancel=should_cancel,
                result=result,
                on_status=status,
                on_reasoning=on_reasoning,
                resources=res,
            ),
        ):
            yield token


async def stream_regenerate_response(
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, Any] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
) -> AsyncIterator[str]:
    timing = TurnTimingTracker()
    timing.mark_phase("turn_start")
    status = wrap_stream_status(timing, on_status)

    async with turn_resources(redis, user_id=user_id, chat_id=chat_id) as res:
        # The reply being regenerated may not be committed yet — wait so we
        # delete/replace the real row instead of racing the background insert.
        await wait_for_pending_finalize(chat_id, redis)

        regenerate_backup: RegenerateBackup | None = None
        model: str
        user_message_content: str
        chat_project_id: UUID | None
        prior_count: int
        omit_message_ids: set[UUID] | None = None

        async with SessionLocal() as session:
            user = await users_repo.get_by_id(session, user_id)
            if user is None:
                raise ChatNotFoundError("User not found.")

            chat = await chats_repo.get_by_id(session, chat_id, user_id)
            if chat is None:
                raise ChatNotFoundError("Chat not found.")

            last = await messages_repo.get_last(session, chat_id)
            if last is None:
                raise ChatNotFoundError("No messages to regenerate.")

            last_user = await messages_repo.get_last_user(session, chat_id)
            if last_user is None:
                raise ChatNotFoundError("No user message to regenerate from.")

            model = plan_service.resolve_regenerate_model(
                user, model_alias, last_user.content, last.model, settings
            )
            user_message_content = last_user.content
            chat_project_id = chat.project_id
            prior_count = await messages_repo.count_for_chat(session, chat_id)

            if last.role == "assistant":
                # Keep the row until finalize succeeds so a mid-stream crash cannot
                # lose the prior reply. Omit it from the regenerate prompt instead.
                regenerate_backup = RegenerateBackup(
                    content=last.content,
                    model=last.model,
                    message_id=last.id,
                )
                omit_message_ids = {last.id}

        if await _try_image_gen_for_turn(
            settings,
            user=user,
            chat_id=chat_id,
            content=user_message_content,
            result=result,
            create_user_message=False,
            replace_assistant_id=(
                regenerate_backup.message_id if regenerate_backup is not None else None
            ),
        ):
            return

        # Reserve before prompt prep (classifier / web-search) — same invariant
        # as message/edit paths. Style-based estimate; finalize reconciles usage.
        await res.reserve(
            user=user,
            content=user_message_content,
            model=model,
            settings=settings,
            max_output=settings.max_output_tokens,
            seed=True,
        )
        bundle = await build_stream_prompt_context(
            user_id,
            chat_id,
            user_message_content,
            model,
            settings,
            redis,
            client_timezone=client_timezone,
            client_location=client_location,
            client_latitude=client_latitude,
            client_longitude=client_longitude,
            on_status=status,
            user=user,
            chat=chat,
            timing=timing,
            omit_message_ids=omit_message_ids,
        )

        # Preserve regenerate semantics (run_title off, skip_memory_jobs = minimal_quiz).
        ctx = stream_context_from_bundle(
            bundle,
            user_id=user_id,
            chat_id=chat_id,
            model=model,
            user_message_content=user_message_content,
            reserved_tokens=res.reserved_tokens,
            user=user,
            prior_count=prior_count,
            chat_project_id=chat_project_id,
            timing=timing,
            run_title=False,
            skip_memory_jobs=bundle.minimal_quiz,
            regenerate_backup=regenerate_backup,
        )
        await _top_up_reserve_for_prompt(
            res,
            settings=settings,
            ctx=ctx,
            daily_limit=quota_service.daily_limit_for_user(user, settings),
        )

        try:
            async for token in _yield_with_chatprep_refresh(
                redis,
                res.lock_key,
                res.lock_token,
                stream_and_finalize(
                    redis,
                    settings,
                    ctx,
                    should_cancel=should_cancel,
                    result=result,
                    on_status=status,
                    on_reasoning=on_reasoning,
                    resources=res,
                ),
            ):
                yield token
        except BaseException:
            # Quota is refunded by the turn_resources block; the prior reply
            # still has to be put back before the error propagates.
            if regenerate_backup is not None:
                await restore_regenerate_backup(user_id, chat_id, regenerate_backup)
            raise


async def stream_edit_response(
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    message_id: UUID,
    new_content: str,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, Any] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
) -> AsyncIterator[str]:
    """Replace a user message and delete all turns after it, then re-stream."""
    content = new_content.strip()
    if not content:
        raise ChatNotFoundError("Message cannot be empty.")

    # Hold the per-chat lock across destructive delete + re-stream so a
    # concurrent turn on another device cannot finalize an orphan reply to a
    # user message this edit is about to remove.
    async with turn_resources(redis, user_id=user_id, chat_id=chat_id) as res:
        # Turns after the edited message are deleted below — make sure the
        # previous turn's background insert has landed so it gets deleted too.
        await wait_for_pending_finalize(chat_id, redis)

        async with SessionLocal() as session:
            user = await users_repo.get_by_id(session, user_id)
            if user is None:
                raise ChatNotFoundError("User not found.")
            chat = await chats_repo.get_by_id(session, chat_id, user_id)
            if chat is None:
                raise ChatNotFoundError("Chat not found.")
            target = await messages_repo.get_by_id(session, message_id, chat_id)
            if target is None or target.role != "user":
                raise ChatNotFoundError("Only user messages can be edited.")
            model = plan_service.resolve_user_model_override(user, model_alias, content, settings)
            # Seed inside this session so the subsequent delete work shares the
            # same connection; reservation itself is Redis-only.
            await seed_usage_from_db(redis, session, user_id)
            await res.reserve(
                user=user,
                content=content,
                model=model,
                settings=settings,
                max_output=settings.max_output_tokens,
                seed=False,
            )
            # The quota is reserved above; if the delete/summary-reset throws
            # before delegating to stream_chat_response, the enclosing
            # turn_resources block refunds it — otherwise the user is charged
            # for a turn that never ran. That block catches BaseException, so a
            # cancel mid-delete refunds too (the old `except Exception` here
            # did not).
            message_ids = await messages_repo.ids_from_chat_at_or_after(
                session,
                chat_id,
                from_created_at=target.created_at,
                from_message_id=target.id,
            )
            # BUG FIX (was silent): history compression (services/chat/post_turn.py
            # -> background/compaction.py) folds the oldest `summary_message_count`
            # messages into `chat.summary` and never revisits them. If the edited
            # message falls inside that already-summarized prefix, deleting
            # everything from it onward removes messages the cached summary still
            # narrates — nothing else ever invalidates `chat.summary`, so a stale
            # summary describing a conversation branch the user edited away would
            # keep getting injected into every future prompt as ground truth
            # (prompt_builder.py's "Summary of earlier conversation" block), and
            # should_run_compression() would never naturally recover it (deleting
            # messages can only shrink `summarized_count` below the stored
            # `summary_message_count`, so `pending` goes negative and compression
            # just keeps no-op'ing). Reset the summary here whenever the edit
            # touches the summarized prefix — do not remove this without also
            # fixing the staleness some other way.
            summarized_count = chat.summary_message_count or 0
            if summarized_count > 0:
                total_before_edit = await messages_repo.count_for_chat(session, chat_id)
                edited_position = total_before_edit - len(message_ids)
                if edited_position < summarized_count:
                    chat.summary = None
                    chat.summary_message_count = 0
            storage_keys = await attachment_lifecycle.detach_attachments_for_messages(
                session, message_ids, commit=False
            )
            await messages_repo.delete_messages_from(
                session,
                chat_id,
                from_created_at=target.created_at,
                from_message_id=target.id,
            )
            # The message rows are committed above (the re-stream's recent
            # window must not see the about-to-be-replaced tail). The
            # attachment FILES in object storage are the only irrevocable
            # step — defer that delete until the re-stream has actually
            # produced output, so a stream failure (model unavailable,
            # disconnect, quota error) does not destroy user files for a
            # turn that never replied. On failure the keys are left orphaned
            # for the attachment orphan reaper to clean up later.

        async for token in stream_chat_response(
            redis,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            model_alias=model_alias,
            should_cancel=should_cancel,
            result=result,
            client_timezone=client_timezone,
            client_location=client_location,
            client_latitude=client_latitude,
            client_longitude=client_longitude,
            on_status=on_status,
            on_reasoning=on_reasoning,
            user=user,
            skip_usage_seed=True,
            resources=res,
        ):
            yield token

        # Re-stream succeeded — now safe to delete the orphaned attachment
        # files. (Skipped on stream failure: the `async for` raises before
        # reaching here, and turn_resources refunds quota.)
        if storage_keys:
            await attachment_lifecycle.delete_storage_keys(settings, storage_keys)


@dataclass
class _StreamAccum:
    """Mutable stream state shared across phase helpers."""

    parts: list[str] = field(default_factory=list)
    was_cancelled: bool = False


async def _run_instant_reply_path(
    ctx: StreamContext,
    *,
    should_cancel: Callable[[], bool] | None,
    accum: _StreamAccum,
) -> AsyncIterator[str]:
    """Yield the precomputed instant reply, or mark cancel if the client stopped."""
    if not (should_cancel and should_cancel()):
        if ctx.timing is not None:
            ctx.timing.mark_first_token()
        # Orchestrator only enters this path when instant_reply is truthy.
        reply = ctx.instant_reply
        if reply is None:
            return
        accum.parts.append(reply)
        yield reply
    else:
        accum.was_cancelled = True


async def _run_tool_loop_path(
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    usage: dict[str, int],
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
) -> None:
    """Run MCP tool rounds when enabled; may update ``ctx.verified_math``."""
    # Skip the tool loop when turn_prep's heuristic math already produced a
    # verified block — the model just copies the canonical fence, so the
    # loop's sympy/graph adapter is redundant. Running it anyway costs up to
    # ``mcp_tool_loop_max_rounds`` (3) non-streaming OpenRouter round-trips
    # (~24s) before the first token. Non-math turns still use the loop.
    if (
        settings.mcp_tool_loop_enabled
        and not ctx.instant_reply
        and not ctx.lightweight_turn
        and ctx.verified_math is None
    ):
        if await quota_service.global_spend_exceeded(redis, settings):
            logger.warning(
                "skipping MCP tool loop: global spend cap user_id=%s chat_id=%s",
                ctx.user_id,
                ctx.chat_id,
            )
            return
        from app.services import tool_loop as tool_loop_service

        (
            ctx.prompt_messages,
            tool_verified,
            terminal_image,
        ) = await tool_loop_service.run_tool_rounds(
            settings=settings,
            model_alias=ctx.model,
            messages=ctx.prompt_messages,
            usage=usage,
            on_status=on_status,
            should_cancel=should_cancel,
            user=ctx.user,
            redis=redis,
            chat_id=ctx.chat_id,
        )
        # Heuristic math_tools is skipped when the tool loop is on —
        # carry sympy canonical fences so validate_math_fences still
        # overwrites/densifies geometry and graph JSON.
        if tool_verified is not None:
            ctx.verified_math = tool_verified
        if terminal_image is not None:
            ctx.terminal_image_message_id = terminal_image.message_id
            ctx.terminal_image_content = terminal_image.final_content
            ctx.terminal_image_model = terminal_image.resolved_model


async def _run_llm_token_stream(
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    usage: dict[str, int],
    should_cancel: Callable[[], bool] | None,
    result: dict[str, Any] | None,
    on_reasoning: StreamReasoningFn | None,
    accum: _StreamAccum,
) -> AsyncIterator[str]:
    """Stream provider tokens into ``accum``, record health, resolve fallback model."""
    stream_meta: dict[str, str] = {}
    requested_model = ctx.model
    t0 = time.perf_counter()
    stream_ok = False
    llm_stream = litellm_gateway.stream_chat_completion(
        settings=settings,
        model_alias=ctx.model,
        messages=ctx.prompt_messages,
        max_tokens=ctx.max_output_tokens,
        usage=usage,
        fallback_aliases=ctx.fallback_models,
        stream_meta=stream_meta,
        on_reasoning=on_reasoning,
    )
    try:
        async for token in llm_stream:
            if should_cancel and should_cancel():
                accum.was_cancelled = True
                break
            if ctx.timing is not None and not accum.parts:
                ctx.timing.mark_first_token()
            accum.parts.append(token)
            yield token
        stream_ok = bool(accum.parts) or accum.was_cancelled
    except asyncio.CancelledError:
        # Hard stop while waiting on the provider never polls should_cancel,
        # so mark it here or the finally records a failed health sample.
        accum.was_cancelled = True
        raise
    finally:
        close = getattr(llm_stream, "aclose", None)
        if close is not None:
            await close()
        # User-initiated stop is not a provider failure — skip the sample
        # so cancel storms don't poison model-health / fallback routing.
        if not accum.was_cancelled:
            latency_ms = (time.perf_counter() - t0) * 1000
            resolved_for_health = stream_meta.get("model_alias") or requested_model
            try:
                from app.services import model_health as model_health_service

                await model_health_service.record_sample(
                    redis,
                    resolved_for_health,
                    latency_ms=latency_ms,
                    success=stream_ok,
                )
            except Exception:
                logger.debug("model health sample failed", exc_info=True)
    resolved = stream_meta.get("model_alias")
    if resolved:
        ctx.model = resolved
    if result is not None:
        result["requested_model"] = requested_model
        if resolved and resolved != requested_model:
            result["fallback_used"] = "1"


async def _enrich_final_content(
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    assistant_text: str,
    usage: dict[str, int],
    result: dict[str, Any] | None,
    was_cancelled: bool,
    assistant_parts: list[str],
    should_cancel: Callable[[], bool] | None,
) -> str:
    """Calendar / reminders / math fences / sources / places. Never blocks persistence."""
    # Enrichment (calendar ids, math fences, sources, …) must never block
    # persistence — the user already saw streamed tokens. On failure, keep
    # the raw joined text so finalize_stream_turn_db still runs.
    raw_assistant_text = assistant_text
    reminder_created = 0
    try:
        user = ctx.user
        if user is not None:
            async with SessionLocal() as session:
                assistant_text = await calendar_service.materialize_calendar_proposals(
                    session,
                    redis,
                    user,
                    settings,
                    assistant_text,
                )
                (
                    assistant_text,
                    reminder_created,
                ) = await todos_service.materialize_reminder_fences(
                    session,
                    user_id=ctx.user_id,
                    chat_id=ctx.chat_id,
                    assistant_text=assistant_text,
                    user_timezone=getattr(user, "timezone", None),
                )
        else:
            async with SessionLocal() as session:
                user = await users_repo.get_by_id(session, ctx.user_id)
                if user is not None:
                    assistant_text = await calendar_service.materialize_calendar_proposals(
                        session,
                        redis,
                        user,
                        settings,
                        assistant_text,
                    )
                    (
                        assistant_text,
                        reminder_created,
                    ) = await todos_service.materialize_reminder_fences(
                        session,
                        user_id=ctx.user_id,
                        chat_id=ctx.chat_id,
                        assistant_text=assistant_text,
                        user_timezone=getattr(user, "timezone", None),
                    )

        # validate_math_fences runs SymPy (densify_sparse_graph →
        # math_service.sample_function). Use the bounded process pool so a
        # pathological fence cannot starve the shared default thread pool
        # (pre-stream solve already uses run_sympy the same way).
        from app.services.sympy_executor import run_sympy

        pre_validation_text = assistant_text
        try:
            assistant_text = await run_sympy(
                math_fence_service.validate_math_fences_worker,
                assistant_text,
                ctx.verified_math,
                timeout=settings.math_solve_timeout_seconds,
            )
        except TimeoutError:
            logger.warning("validate_math_fences timed out; keeping raw assistant text")
            # Fail closed: validate_math_fences was killed before it could
            # clean up an unclosed ```graph fence the model truncated at EOS.
            # Strip/substitute it SymPy-free so the client doesn't render a
            # half-pasted points array (the densify pass that would re-enter
            # SymPy is intentionally skipped here).
            canonical_fence = (
                ctx.verified_math.canonical_fence if ctx.verified_math is not None else None
            )
            assistant_text = math_fence_service.replace_unclosed_graph_fence_safe(
                assistant_text, canonical_fence
            )
        except Exception:
            logger.exception("validate_math_fences failed; keeping raw assistant text")
            canonical_fence = (
                ctx.verified_math.canonical_fence if ctx.verified_math is not None else None
            )
            assistant_text = math_fence_service.replace_unclosed_graph_fence_safe(
                assistant_text, canonical_fence
            )
        from app.services.vocab_quiz import strip_vocab_session_metadata

        assistant_text = strip_vocab_session_metadata(assistant_text)

        # validate_math_fences may rewrite a ```graph fence the model emitted
        # without points (e.g. "Graph x=2y" → model drops the 96-point array)
        # by substituting the verified canonical fence. That corrected text is
        # persisted to the DB below, but without final_content the client keeps
        # the raw streamed draft and renders "Could not render function graph."
        # Send the corrected text whenever validation actually changed it.
        if result is not None and assistant_text != pre_validation_text:
            result["final_content"] = assistant_text

        if ctx.search_sources:
            assistant_text = web_search_service.strip_sources_from_text(assistant_text)
            if result is not None:
                result["search_sources"] = json.dumps(
                    web_search_service.sources_payload(ctx.search_sources)
                )
                result["final_content"] = assistant_text
            sources_fence = web_search_service.format_sources_fence(ctx.search_sources)
            if sources_fence and not (should_cancel and should_cancel()):
                assistant_text = f"{assistant_text}{sources_fence}".strip()

        if ctx.local_places and ctx.search_sources and "```places" not in assistant_text.lower():
            assistant_text = web_search_service.strip_duplicate_venue_list(assistant_text)
            places_fence = web_search_service.format_places_fence(ctx.search_sources)
            if places_fence and not (should_cancel and should_cancel()):
                assistant_parts[:] = [assistant_text] if assistant_text.strip() else []
                assistant_parts.append(places_fence)
                assistant_text = "".join(assistant_parts).strip()
                if result is not None:
                    result["final_content"] = assistant_text

        if ctx.instant_reply and not usage:
            # Instant replies are canned short-circuits (time/location/
            # not-connected calendar/email) — no LLM was called, so there is no
            # provider token cost to charge against daily quota. Seed 0/0 so
            # finalize's adjust_usage(reserved, actual=0) refunds the full
            # reservation instead of charging the canned reply's estimated
            # tokens (a user could otherwise exhaust daily quota by asking
            # "what time is it?" repeatedly).
            usage["output"] = 0
            usage["input"] = 0

        if result is not None and not ctx.skip_memory_jobs:
            transcript = f"User: {ctx.user_message_content}\nAssistant: {assistant_text}"
            if reminder_created > 0 or todos_service.transcript_implies_todo_sync(transcript):
                result["todos_sync"] = "1"
            # Push stripped text so the live bubble matches DB (no raw ```reminder JSON).
            if reminder_created > 0:
                result["final_content"] = assistant_text

        if result is not None and was_cancelled and assistant_text:
            result["final_content"] = assistant_text
    except Exception:
        logger.exception(
            "Post-stream enrichment failed; persisting raw assistant text",
        )
        assistant_text = raw_assistant_text
        if result is not None and was_cancelled and assistant_text:
            result["final_content"] = assistant_text

    return assistant_text


def _log_background_task_failure(task: asyncio.Task[Any], message: str) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.exception(message, exc_info=exc)


async def _register_and_enqueue_finalize(
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    assistant_text: str,
    usage: dict[str, int],
    result: dict[str, Any] | None,
) -> None:
    """Assign message id, register pending finalize, enqueue post-turn jobs."""
    # Give the assistant row its id now so `done` (message_id + metadata)
    # can be sent the moment the stream ends — the DB commit happens in the
    # background and anything reading this chat next awaits it via the
    # finalize registry.
    if ctx.assistant_message_id is None:
        ctx.assistant_message_id = uuid7()
    if result is not None:
        result["resolved_model"] = ctx.model
        result["message_id"] = str(ctx.assistant_message_id)
        if ctx.recalled_count:
            result["recalled"] = str(ctx.recalled_count)
        if ctx.memory_hints:
            result["memory_hints"] = json.dumps(ctx.memory_hints)
        if ctx.context_summarized:
            result["context_summarized"] = str(ctx.context_summarized)

    # Marker before task so other API machines can poll while finalize runs.
    await mark_pending_finalize(redis, ctx.chat_id)
    finalize_db_task = create_background_task(
        finalize_stream_turn_db(redis, ctx, assistant_text, usage, result),
        name="finalize_stream_turn_db",
    )
    register_pending_finalize(ctx.chat_id, finalize_db_task)
    finalize_db_task.add_done_callback(
        lambda t: _log_background_task_failure(t, "Background DB finalization failed")
    )

    async def _run_jobs_after_db() -> None:
        try:
            await finalize_db_task
            await enqueue_post_turn_jobs(redis, settings, ctx, assistant_text)
        except Exception:
            logger.exception("Background job enqueue failed")

    jobs_task = create_background_task(_run_jobs_after_db(), name="post_turn_jobs")
    jobs_task.add_done_callback(
        lambda t: _log_background_task_failure(t, "Background finalization failed")
    )
    if result is not None:
        result["_finalize_task"] = jobs_task
        result["_finalize_db_task"] = finalize_db_task


async def stream_and_finalize(
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    should_cancel: Callable[[], bool] | None,
    result: dict[str, Any] | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
    resources: TurnResources | None = None,
) -> AsyncIterator[str]:
    usage: dict[str, int] = {}
    accum = _StreamAccum()

    try:
        try:
            if ctx.instant_reply:
                async for token in _run_instant_reply_path(
                    ctx, should_cancel=should_cancel, accum=accum
                ):
                    yield token
            else:
                # Pre-stream work (tools/search) is "thinking", not "composing" —
                # composing only once the visible token stream is about to start.
                # Casual / non-rich turns skip status theater (same as greetings).
                quiet_status = ctx.lightweight_turn or not ctx.rich_context_turn
                if on_status is not None and not quiet_status:
                    await on_status("thinking")
                await _run_tool_loop_path(
                    redis,
                    settings,
                    ctx,
                    usage=usage,
                    on_status=on_status,
                    should_cancel=should_cancel,
                )

                # generate_image already persisted the assistant ``[Image: …]``
                # row — skip the visible LLM stream + second finalize insert.
                if ctx.terminal_image_content and ctx.terminal_image_message_id:
                    if result is not None:
                        result["message_id"] = ctx.terminal_image_message_id
                        result["final_content"] = ctx.terminal_image_content
                        result["resolved_model"] = ctx.terminal_image_model or "image-gen-model"
                    # Image gen has its own daily cap; refund the chat-token hold
                    # through TurnResources so __aexit__ cannot double-credit.
                    if resources is not None:
                        await resources.refund()
                    else:
                        await quota_service.refund_usage(
                            redis, str(ctx.user_id), ctx.reserved_tokens
                        )
                    return

                if (
                    on_status is not None
                    and not quiet_status
                    and not model_catalog.is_reasoning_alias(ctx.model)
                ):
                    await on_status("composing")
                async for token in _run_llm_token_stream(
                    redis,
                    settings,
                    ctx,
                    usage=usage,
                    should_cancel=should_cancel,
                    result=result,
                    on_reasoning=on_reasoning,
                    accum=accum,
                ):
                    yield token
        except asyncio.CancelledError:
            # Hard WS/SSE disconnect cancels the producer task. If we already
            # streamed tokens, persist them like a soft stop; otherwise re-raise
            # so the caller refunds the full reservation.
            if not accum.parts:
                raise
            accum.was_cancelled = True
            logger.info(
                "Hard cancel with partial reply; finalizing chat_id=%s parts=%d",
                ctx.chat_id,
                len(accum.parts),
            )

        assistant_text = "".join(accum.parts).strip()
        if not assistant_text:
            # Caller refunds quota / restores regenerate backup on this error.
            raise ModelUnavailableError(
                "That model isn't responding right now. Try again — or pick a different model.",
                failed_alias=ctx.model,
            )

        assistant_text = await _enrich_final_content(
            redis,
            settings,
            ctx,
            assistant_text=assistant_text,
            usage=usage,
            result=result,
            was_cancelled=accum.was_cancelled,
            assistant_parts=accum.parts,
            should_cancel=should_cancel,
        )

        await _register_and_enqueue_finalize(
            redis,
            settings,
            ctx,
            assistant_text=assistant_text,
            usage=usage,
            result=result,
        )
    finally:
        if ctx.timing is not None:
            ctx.timing.log_summary(
                user_id=ctx.user_id,
                chat_id=ctx.chat_id,
                model=ctx.model,
                lightweight=ctx.lightweight_turn,
            )


__all__ = [
    "prompt_weighted_reserve_tokens",
    "reserve_turn_quota",
    "stream_and_finalize",
    "stream_chat_response",
    "stream_edit_response",
    "stream_regenerate_response",
    "weighted_reserve_tokens",
    "wrap_stream_status",
]
