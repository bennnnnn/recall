import asyncio
import json
import logging
import math
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from redis.asyncio import Redis

from app.core.background_tasks import create_background_task
from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis_lock import acquire_lock, release_lock
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


async def _acquire_chatprep_lock(redis: Redis, chat_id: UUID) -> tuple[str, str]:
    """Acquire per-chat prepare lock; raise ChatBusyError if already held."""
    lock_key = f"chatprep:{chat_id}"
    token = await acquire_lock(redis, lock_key, _CHATPREP_LOCK_TTL_SECONDS)
    if token is None:
        raise ChatBusyError()
    return lock_key, token


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


async def _refund_after_stream_error(
    redis: Redis,
    user_id: UUID,
    chat_id: UUID,
    reserved: int,
    *,
    regenerate_backup: RegenerateBackup | None = None,
) -> None:
    await quota_service.refund_usage(redis, str(user_id), reserved)
    if regenerate_backup is not None:
        await restore_regenerate_backup(user_id, chat_id, regenerate_backup)


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
        async with SessionLocal() as session:
            if replace_assistant_id is not None:
                last = await messages_repo.get_last(session, chat_id)
                if (
                    last is not None
                    and last.id == replace_assistant_id
                    and last.role == "assistant"
                ):
                    await messages_repo.delete_message(session, last)
                    await session.commit()
            _user_msg, asst_msg = await image_generation_service.generate_for_chat(
                session,
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
    pre_reserved: int | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
    user: User | None = None,
    skip_usage_seed: bool = False,
) -> AsyncIterator[str]:
    timing = TurnTimingTracker()
    timing.mark_phase("turn_start")
    status = wrap_stream_status(timing, on_status)

    lock_key, lock_token = await _acquire_chatprep_lock(redis, chat_id)
    try:
        # The previous turn's DB commit may still be in flight (done is sent
        # before it lands) — wait so this turn's prompt sees that reply.
        await wait_for_pending_finalize(chat_id)

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
            # Edit path reserves before delegating here; refund that reservation
            # since image-gen does not consume chat-token quota.
            if pre_reserved is not None:
                await quota_service.refund_usage(redis, str(user_id), pre_reserved)
            return

        if pre_reserved is not None:
            reserved = pre_reserved
        else:
            vision_extra = 0
            if attachment_ids:
                async with SessionLocal() as session:
                    image_count = await count_image_attachments(session, user_id, attachment_ids)
                vision_extra = vision_reserve_tokens(settings, image_count)
            reserved = await reserve_turn_quota(
                redis,
                user=user,
                content=content,
                model=model,
                settings=settings,
                daily_limit=daily_limit,
                vision_extra=vision_extra,
                seed=False,
            )

        try:
            ctx = await prepare_chat_turn(
                user_id=user_id,
                chat_id=chat_id,
                content=content,
                model_alias=model_alias,
                settings=settings,
                redis=redis,
                reserved_tokens=reserved,
                attachment_ids=attachment_ids or [],
                client_timezone=client_timezone,
                client_location=client_location,
                client_latitude=client_latitude,
                client_longitude=client_longitude,
                on_status=status,
                user=user,
                timing=timing,
            )
        except BaseException:
            # CancelledError (ASGI/WS cancel) is BaseException on 3.12 — must refund.
            await quota_service.refund_usage(redis, str(user_id), reserved)
            raise

        try:
            async for token in stream_and_finalize(
                redis,
                settings,
                ctx,
                should_cancel=should_cancel,
                result=result,
                on_status=status,
                on_reasoning=on_reasoning,
            ):
                yield token
        except BaseException:
            await _refund_after_stream_error(redis, user_id, chat_id, reserved)
            raise
    finally:
        await release_lock(redis, lock_key, lock_token)


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

    lock_key, lock_token = await _acquire_chatprep_lock(redis, chat_id)
    try:
        # The reply being regenerated may not be committed yet — wait so we
        # delete/replace the real row instead of racing the background insert.
        await wait_for_pending_finalize(chat_id)

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

            model = plan_service.resolve_user_model_override(
                user, model_alias, last_user.content, settings
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

        reserved = await reserve_turn_quota(
            redis,
            user=user,
            content=user_message_content,
            model=model,
            settings=settings,
            max_output=bundle.max_out,
            seed=True,
        )

        # Preserve regenerate semantics (run_title off, skip_memory_jobs = minimal_quiz).
        ctx = stream_context_from_bundle(
            bundle,
            user_id=user_id,
            chat_id=chat_id,
            model=model,
            user_message_content=user_message_content,
            reserved_tokens=reserved,
            user=user,
            prior_count=prior_count,
            chat_project_id=chat_project_id,
            timing=timing,
            run_title=False,
            skip_memory_jobs=bundle.minimal_quiz,
            regenerate_backup=regenerate_backup,
        )

        try:
            async for token in stream_and_finalize(
                redis,
                settings,
                ctx,
                should_cancel=should_cancel,
                result=result,
                on_status=status,
                on_reasoning=on_reasoning,
            ):
                yield token
        except BaseException:
            await _refund_after_stream_error(
                redis,
                user_id,
                chat_id,
                reserved,
                regenerate_backup=regenerate_backup,
            )
            raise
    finally:
        await release_lock(redis, lock_key, lock_token)


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

    # Turns after the edited message are deleted below — make sure the
    # previous turn's background insert has landed so it gets deleted too.
    await wait_for_pending_finalize(chat_id)

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
        reserved = await reserve_turn_quota(
            redis,
            user=user,
            content=content,
            model=model,
            settings=settings,
            seed=False,
        )
        try:
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
            await attachment_lifecycle.purge_attachments_for_messages(
                session, settings, message_ids
            )
            await messages_repo.delete_messages_from(
                session,
                chat_id,
                from_created_at=target.created_at,
                from_message_id=target.id,
            )
        except Exception:
            # The quota was reserved above; if the delete/summary-reset throws
            # before delegating to stream_chat_response (which owns its own
            # refund on failure), the reservation leaks and the user is charged
            # for a turn that never ran. Refund before re-raising.
            await quota_service.refund_usage(redis, str(user_id), reserved)
            raise

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
        pre_reserved=reserved,
        on_status=on_status,
        on_reasoning=on_reasoning,
        user=user,
        skip_usage_seed=True,
    ):
        yield token


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
    settings: Settings,
    ctx: StreamContext,
    *,
    usage: dict[str, int],
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
) -> None:
    """Run MCP tool rounds when enabled; may update ``ctx.verified_math``."""
    if settings.mcp_tool_loop_enabled and not ctx.instant_reply and not ctx.lightweight_turn:
        from app.services import tool_loop as tool_loop_service

        ctx.prompt_messages, tool_verified = await tool_loop_service.run_tool_rounds(
            settings=settings,
            model_alias=ctx.model,
            messages=ctx.prompt_messages,
            usage=usage,
            on_status=on_status,
            should_cancel=should_cancel,
        )
        # Heuristic math_tools is skipped when the tool loop is on —
        # carry sympy canonical fences so validate_math_fences still
        # overwrites/densifies geometry and graph JSON.
        if tool_verified is not None:
            ctx.verified_math = tool_verified


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

        try:
            assistant_text = await run_sympy(
                math_fence_service.validate_math_fences_worker,
                assistant_text,
                ctx.verified_math,
                timeout=settings.math_solve_timeout_seconds,
            )
        except TimeoutError:
            logger.warning("validate_math_fences timed out; keeping raw assistant text")
        except Exception:
            logger.exception("validate_math_fences failed; keeping raw assistant text")
        from app.services.vocab_quiz import strip_vocab_session_metadata

        assistant_text = strip_vocab_session_metadata(assistant_text)

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
            usage["output"] = estimate_tokens(assistant_text)
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


def _register_and_enqueue_finalize(
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
        ctx.assistant_message_id = uuid4()
    if result is not None:
        result["resolved_model"] = ctx.model
        result["message_id"] = str(ctx.assistant_message_id)
        if ctx.recalled_count:
            result["recalled"] = str(ctx.recalled_count)
        if ctx.memory_hints:
            result["memory_hints"] = json.dumps(ctx.memory_hints)
        if ctx.context_summarized:
            result["context_summarized"] = str(ctx.context_summarized)

    finalize_db_task = create_background_task(
        finalize_stream_turn_db(redis, ctx, assistant_text, usage, result),
        name="finalize_stream_turn_db",
    )
    register_pending_finalize(ctx.chat_id, finalize_db_task)
    finalize_db_task.add_done_callback(
        lambda t: logger.exception("Background DB finalization failed", exc_info=t.exception())
        if t.exception()
        else None
    )

    async def _run_jobs_after_db() -> None:
        try:
            await finalize_db_task
            await enqueue_post_turn_jobs(redis, settings, ctx, assistant_text)
        except Exception:
            logger.exception("Background job enqueue failed")

    jobs_task = create_background_task(_run_jobs_after_db(), name="post_turn_jobs")
    jobs_task.add_done_callback(
        lambda t: logger.exception("Background finalization failed", exc_info=t.exception())
        if t.exception()
        else None
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
                if on_status is not None:
                    await on_status("thinking")
                await _run_tool_loop_path(
                    settings,
                    ctx,
                    usage=usage,
                    on_status=on_status,
                    should_cancel=should_cancel,
                )

                if on_status is not None and not model_catalog.is_reasoning_alias(ctx.model):
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

        _register_and_enqueue_finalize(
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
    "reserve_turn_quota",
    "stream_and_finalize",
    "stream_chat_response",
    "stream_edit_response",
    "stream_regenerate_response",
    "weighted_reserve_tokens",
    "wrap_stream_status",
]
