import json
import logging
import math
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.background_tasks import create_background_task
from app.core.config import Settings
from app.core.db import SessionLocal
from app.exceptions import ChatNotFoundError, QuotaExceededError
from app.models.orm import User
from app.services.chat.post_turn import (
    enqueue_post_turn_jobs,
    finalize_stream_turn_db,
    seed_usage_from_db,
)
from app.services.chat.prompt_builder import StreamReasoningFn, StreamStatusFn
from app.services.chat.prompt_constants import is_lightweight_chat_turn
from app.services.chat.turn_prep import (
    RegenerateBackup,
    StreamContext,
    build_stream_prompt_context,
    count_image_attachments,
    vision_reserve_tokens,
)
from app.services.chat.turn_timing import TurnTimingTracker
from app.services.context_window import estimate_tokens
from app.services.quota import quota_exceeded_message

logger = logging.getLogger(__name__)


def wrap_stream_status(
    timing: TurnTimingTracker | None,
    on_status: StreamStatusFn | None,
) -> StreamStatusFn | None:
    if timing is None and on_status is None:
        return None

    async def emit(phase: str) -> None:
        if timing is not None:
            timing.mark_phase(phase)
        if on_status is not None:
            await on_status(phase)

    return emit


async def _refund_after_stream_error(
    redis: Redis,
    user_id: UUID,
    chat_id: UUID,
    reserved: int,
    *,
    regenerate_backup: RegenerateBackup | None = None,
) -> None:
    import app.services.chat as chat_pkg

    await chat_pkg.quota_service.refund_usage(redis, str(user_id), reserved)
    if regenerate_backup is not None:
        await chat_pkg._restore_regenerate_backup(user_id, chat_id, regenerate_backup)


def weighted_reserve_tokens(
    *,
    content: str,
    model: str,
    settings: Settings,
    max_output: int | None = None,
    vision_extra: int = 0,
) -> int:
    from app.services import model_catalog

    base = estimate_tokens(content) + (
        max_output if max_output is not None else settings.max_output_tokens
    )
    base += vision_extra
    return math.ceil(base * model_catalog.quota_multiplier(model))


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
    import app.services.chat as chat_pkg

    timing = TurnTimingTracker()
    timing.mark_phase("turn_start")
    status = wrap_stream_status(timing, on_status)

    async with SessionLocal() as session:
        if user is None:
            user = await chat_pkg.users_repo.get_by_id(session, user_id)
            if user is None:
                raise ChatNotFoundError("User not found.")
        if not skip_usage_seed:
            await seed_usage_from_db(redis, session, user_id)
        daily_limit = chat_pkg.quota_service.daily_limit_for_user(user, settings)
        model = chat_pkg.plan_service.resolve_user_model_override(
            user, model_alias, content, settings
        )

    if pre_reserved is not None:
        reserved = pre_reserved
    else:
        vision_extra = 0
        if attachment_ids:
            async with SessionLocal() as session:
                image_count = await count_image_attachments(session, user_id, attachment_ids)
            vision_extra = vision_reserve_tokens(settings, image_count)
        reserved = weighted_reserve_tokens(
            content=content,
            model=model,
            settings=settings,
            vision_extra=vision_extra,
        )
        if not await chat_pkg.quota_service.reserve_usage(
            redis, str(user_id), reserved, daily_limit=daily_limit
        ):
            raise QuotaExceededError(quota_exceeded_message(user))

    try:
        ctx = await chat_pkg._prepare_chat_turn(
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
    except Exception:
        await chat_pkg.quota_service.refund_usage(redis, str(user_id), reserved)
        raise

    try:
        async for token in chat_pkg._stream_and_finalize(
            redis,
            settings,
            ctx,
            should_cancel=should_cancel,
            result=result,
            on_status=status,
            on_reasoning=on_reasoning,
        ):
            yield token
    except Exception:
        await _refund_after_stream_error(redis, user_id, chat_id, reserved)
        raise


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
    import app.services.chat as chat_pkg

    timing = TurnTimingTracker()
    timing.mark_phase("turn_start")
    status = wrap_stream_status(timing, on_status)

    regenerate_backup: RegenerateBackup | None = None
    model: str
    user_message_content: str
    chat_project_id: UUID | None
    prior_count: int

    async with SessionLocal() as session:
        user = await chat_pkg.users_repo.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")

        chat = await chat_pkg.chats_repo.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")

        last = await chat_pkg.messages_repo.get_last(session, chat_id)
        if last is None:
            raise ChatNotFoundError("No messages to regenerate.")

        last_user = await chat_pkg.messages_repo.get_last_user(session, chat_id)
        if last_user is None:
            raise ChatNotFoundError("No user message to regenerate from.")

        model = chat_pkg.plan_service.resolve_user_model_override(
            user, model_alias, last_user.content, settings
        )
        user_message_content = last_user.content
        chat_project_id = chat.project_id
        prior_count = await chat_pkg.messages_repo.count_for_chat(session, chat_id)

        if last.role == "assistant":
            regenerate_backup = RegenerateBackup(content=last.content, model=last.model)
            await chat_pkg.attachment_lifecycle.purge_attachments_for_messages(
                session, settings, [last.id]
            )
            await chat_pkg.messages_repo.delete_message(session, last)
            await session.commit()

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
    )

    async with SessionLocal() as session:
        reserved = weighted_reserve_tokens(
            content=user_message_content,
            model=model,
            settings=settings,
            max_output=bundle.max_out,
        )
        daily_limit = chat_pkg.quota_service.daily_limit_for_user(user, settings)
        await seed_usage_from_db(redis, session, user_id)
        if not await chat_pkg.quota_service.reserve_usage(
            redis, str(user_id), reserved, daily_limit=daily_limit
        ):
            raise QuotaExceededError(quota_exceeded_message(user))

    ctx = StreamContext(
        user_id=user_id,
        chat_id=chat_id,
        model=model,
        prompt_messages=bundle.prompt_messages,
        run_title=False,
        user_message_content=user_message_content,
        reserved_tokens=reserved,
        max_output_tokens=bundle.max_out,
        user=user,
        recalled_count=int(bundle.meta.get("recalled") or 0),
        memory_hints=list(bundle.meta.get("memory_hints") or []),
        context_summarized=int(bundle.meta.get("context_summarized") or 0),
        instant_reply=bundle.instant_reply,
        search_sources=bundle.search_sources,
        local_places=bundle.local_places,
        skip_memory_jobs=bundle.minimal_quiz,
        prior_count=prior_count,
        chat_project_id=chat_project_id,
        regenerate_backup=regenerate_backup,
        fallback_models=bundle.fallback_models,
        verified_math=bundle.verified_math,
        timing=timing,
        lightweight_turn=is_lightweight_chat_turn(user_message_content),
    )

    try:
        async for token in chat_pkg._stream_and_finalize(
            redis,
            settings,
            ctx,
            should_cancel=should_cancel,
            result=result,
            on_status=status,
            on_reasoning=on_reasoning,
        ):
            yield token
    except Exception:
        await _refund_after_stream_error(
            redis,
            user_id,
            chat_id,
            reserved,
            regenerate_backup=regenerate_backup,
        )
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
    import app.services.chat as chat_pkg

    content = new_content.strip()
    if not content:
        raise ChatNotFoundError("Message cannot be empty.")

    async with SessionLocal() as session:
        user = await chat_pkg.users_repo.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")
        chat = await chat_pkg.chats_repo.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")
        target = await chat_pkg.messages_repo.get_by_id(session, message_id, chat_id)
        if target is None or target.role != "user":
            raise ChatNotFoundError("Only user messages can be edited.")
        daily_limit = chat_pkg.quota_service.daily_limit_for_user(user, settings)
        model = chat_pkg.plan_service.resolve_user_model_override(
            user, model_alias, content, settings
        )
        reserved = weighted_reserve_tokens(content=content, model=model, settings=settings)
        await seed_usage_from_db(redis, session, user_id)
        if not await chat_pkg.quota_service.reserve_usage(
            redis, str(user_id), reserved, daily_limit=daily_limit
        ):
            raise QuotaExceededError(quota_exceeded_message(user))
        message_ids = await chat_pkg.messages_repo.ids_from_chat_at_or_after(
            session,
            chat_id,
            from_created_at=target.created_at,
            from_message_id=target.id,
        )
        await chat_pkg.attachment_lifecycle.purge_attachments_for_messages(
            session, settings, message_ids
        )
        await chat_pkg.messages_repo.delete_messages_from(
            session,
            chat_id,
            from_created_at=target.created_at,
            from_message_id=target.id,
        )

    async for token in chat_pkg.stream_chat_response(
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
    import app.services.chat as chat_pkg

    usage: dict[str, int] = {}
    assistant_parts: list[str] = []
    was_cancelled = False

    try:
        if ctx.instant_reply:
            if not (should_cancel and should_cancel()):
                if ctx.timing is not None:
                    ctx.timing.mark_first_token()
                assistant_parts.append(ctx.instant_reply)
                yield ctx.instant_reply
            else:
                was_cancelled = True
        else:
            if on_status is not None and chat_pkg.model_catalog.is_reasoning_alias(ctx.model):
                await on_status("thinking")
            elif on_status is not None:
                await on_status("composing")
            if (
                settings.mcp_tool_loop_enabled
                and not ctx.instant_reply
                and not ctx.lightweight_turn
            ):
                from app.services import tool_loop as tool_loop_service

                ctx.prompt_messages = await tool_loop_service.run_tool_rounds(
                    settings=settings,
                    model_alias=ctx.model,
                    messages=ctx.prompt_messages,
                    usage=usage,
                    on_status=on_status,
                    should_cancel=should_cancel,
                )
            stream_meta: dict[str, str] = {}
            requested_model = ctx.model
            import time

            t0 = time.perf_counter()
            stream_ok = False
            llm_stream = chat_pkg.litellm_gateway.stream_chat_completion(
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
                        was_cancelled = True
                        break
                    if ctx.timing is not None and not assistant_parts:
                        ctx.timing.mark_first_token()
                    assistant_parts.append(token)
                    yield token
                stream_ok = bool(assistant_parts) or was_cancelled
            finally:
                close = getattr(llm_stream, "aclose", None)
                if close is not None:
                    await close()
                latency_ms = (time.perf_counter() - t0) * 1000
                resolved_for_health = stream_meta.get("model_alias") or requested_model
                try:
                    from app.services import model_health as model_health_service

                    await model_health_service.record_sample(
                        redis,
                        resolved_for_health,
                        latency_ms=latency_ms,
                        success=stream_ok and not was_cancelled,
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

        assistant_text = "".join(assistant_parts).strip()
        if not assistant_text:
            await chat_pkg.quota_service.refund_usage(redis, str(ctx.user_id), ctx.reserved_tokens)
            if ctx.regenerate_backup is not None:
                await chat_pkg._restore_regenerate_backup(
                    ctx.user_id,
                    ctx.chat_id,
                    ctx.regenerate_backup,
                )
            return

        # Enrichment (calendar ids, math fences, sources, …) must never block
        # persistence — the user already saw streamed tokens. On failure, keep
        # the raw joined text so finalize_stream_turn_db still runs.
        raw_assistant_text = assistant_text
        try:
            user = ctx.user
            if user is not None:
                async with SessionLocal() as session:
                    assistant_text = await chat_pkg.calendar_service.materialize_calendar_proposals(
                        session,
                        redis,
                        user,
                        settings,
                        assistant_text,
                    )
            else:
                async with SessionLocal() as session:
                    user = await chat_pkg.users_repo.get_by_id(session, ctx.user_id)
                    if user is not None:
                        assistant_text = (
                            await chat_pkg.calendar_service.materialize_calendar_proposals(
                                session,
                                redis,
                                user,
                                settings,
                                assistant_text,
                            )
                        )

            assistant_text = chat_pkg.math_fence_service.validate_math_fences(
                assistant_text, verified=ctx.verified_math
            )
            from app.services.vocab_quiz import strip_vocab_session_metadata

            assistant_text = strip_vocab_session_metadata(assistant_text)

            if ctx.search_sources:
                assistant_text = chat_pkg.web_search_service.strip_sources_from_text(assistant_text)
                if result is not None:
                    result["search_sources"] = json.dumps(
                        chat_pkg.web_search_service.sources_payload(ctx.search_sources)
                    )
                    result["final_content"] = assistant_text
                sources_fence = chat_pkg.web_search_service.format_sources_fence(ctx.search_sources)
                if sources_fence and not (should_cancel and should_cancel()):
                    assistant_text = f"{assistant_text}{sources_fence}".strip()

            if (
                ctx.local_places
                and ctx.search_sources
                and "```places" not in assistant_text.lower()
            ):
                assistant_text = chat_pkg.web_search_service.strip_duplicate_venue_list(
                    assistant_text
                )
                places_fence = chat_pkg.web_search_service.format_places_fence(ctx.search_sources)
                if places_fence and not (should_cancel and should_cancel()):
                    assistant_parts[:] = [assistant_text] if assistant_text.strip() else []
                    assistant_parts.append(places_fence)
                    assistant_text = "".join(assistant_parts).strip()
                    if result is not None:
                        result["final_content"] = assistant_text

            if ctx.instant_reply and not usage:
                usage["output_tokens"] = estimate_tokens(assistant_text)
                usage["input_tokens"] = 0

            if result is not None and not ctx.skip_memory_jobs:
                transcript = f"User: {ctx.user_message_content}\nAssistant: {assistant_text}"
                if chat_pkg.todos_service.transcript_implies_todo_sync(transcript):
                    result["todos_sync"] = "1"

            if result is not None and was_cancelled and assistant_text:
                result["final_content"] = assistant_text
        except Exception:
            logger.exception(
                "Post-stream enrichment failed; persisting raw assistant text",
            )
            assistant_text = raw_assistant_text
            if result is not None and was_cancelled and assistant_text:
                result["final_content"] = assistant_text

        if result is not None:
            result["resolved_model"] = ctx.model

        finalize_db_task = create_background_task(
            finalize_stream_turn_db(redis, ctx, assistant_text, usage, result),
            name="finalize_stream_turn_db",
        )
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
    finally:
        if ctx.timing is not None:
            ctx.timing.log_summary(
                user_id=ctx.user_id,
                chat_id=ctx.chat_id,
                model=ctx.model,
                lightweight=ctx.lightweight_turn,
            )
