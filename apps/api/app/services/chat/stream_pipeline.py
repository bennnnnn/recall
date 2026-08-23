import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways.litellm_gateway import ModelUnavailableError
from app.services.chat.prompt_builder import StreamReasoningFn, StreamStatusFn
from app.services.chat.turn_prep import StreamContext

logger = logging.getLogger(__name__)


@dataclass
class StreamAccum:
    parts: list[str] = field(default_factory=list)
    was_cancelled: bool = False


async def run_instant_reply_path(
    ctx: StreamContext,
    *,
    should_cancel: Callable[[], bool] | None,
    accum: StreamAccum,
) -> AsyncIterator[str]:
    if not (should_cancel and should_cancel()):
        if ctx.timing is not None:
            ctx.timing.mark_first_token()
        if ctx.instant_reply is None:
            return
        accum.parts.append(ctx.instant_reply)
        yield ctx.instant_reply
    else:
        accum.was_cancelled = True


async def run_tool_loop_path(
    seams: Any,
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    usage: dict[str, int],
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
) -> None:
    from app.services import tool_loop as tool_loop_service

    content = ctx.user_message_content if isinstance(ctx.user_message_content, str) else ""
    sources = ctx.search_sources if isinstance(ctx.search_sources, list) else []
    if not tool_loop_service.turn_needs_tool_loop(
        content,
        lightweight=bool(ctx.lightweight_turn),
        has_instant_reply=ctx.instant_reply is not None,
        has_verified_math=ctx.verified_math is not None,
        has_search_sources=bool(sources),
        settings=settings,
        user=ctx.user,
    ):
        return
    if await seams.quota_service.global_spend_exceeded(redis, settings):
        logger.warning(
            "skipping MCP tool loop: global spend cap user_id=%s chat_id=%s",
            ctx.user_id,
            ctx.chat_id,
        )
        return
    (
        ctx.prompt_messages,
        tool_verified,
        terminal_image,
        unused_final,
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
    if tool_verified is not None:
        ctx.verified_math = tool_verified
    if terminal_image is not None:
        ctx.terminal_image_message_id = terminal_image.message_id
        ctx.terminal_image_content = terminal_image.final_content
        ctx.terminal_image_model = terminal_image.resolved_model
    elif unused_final and ctx.instant_reply is None:
        # Reuse the no-tools completion instead of streaming a second call.
        ctx.instant_reply = unused_final


async def run_llm_token_stream(
    seams: Any,
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    usage: dict[str, int],
    should_cancel: Callable[[], bool] | None,
    result: dict[str, Any] | None,
    on_reasoning: StreamReasoningFn | None,
    accum: StreamAccum,
) -> AsyncIterator[str]:
    stream_meta: dict[str, str] = {}
    requested_model = ctx.model
    started = time.perf_counter()
    stream_ok = False
    llm_stream = seams.litellm_gateway.stream_chat_completion(
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
        accum.was_cancelled = True
        raise
    finally:
        close = getattr(llm_stream, "aclose", None)
        if close is not None:
            await close()
        if not accum.was_cancelled:
            try:
                from app.services import model_health as model_health_service

                await model_health_service.record_sample(
                    redis,
                    stream_meta.get("model_alias") or requested_model,
                    latency_ms=(time.perf_counter() - started) * 1000,
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


async def enrich_final_content(
    seams: Any,
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
    raw_assistant_text = assistant_text
    reminder_created = 0
    try:
        user = ctx.user
        if user is None:
            async with seams.SessionLocal() as session:
                user = await seams.users_repo.get_by_id(session, ctx.user_id)
        if user is not None:
            async with seams.SessionLocal() as session:
                assistant_text = await seams.calendar_service.materialize_calendar_proposals(
                    session, redis, user, settings, assistant_text
                )
                (
                    assistant_text,
                    reminder_created,
                ) = await seams.todos_service.materialize_reminder_fences(
                    session,
                    user_id=ctx.user_id,
                    chat_id=ctx.chat_id,
                    assistant_text=assistant_text,
                    user_timezone=getattr(user, "timezone", None),
                )

        from app.services.sympy_executor import run_sympy

        pre_validation_text = assistant_text
        try:
            assistant_text = await run_sympy(
                seams.math_fence_service.validate_math_fences_worker,
                assistant_text,
                ctx.verified_math,
                timeout=settings.math_solve_timeout_seconds,
            )
        except TimeoutError:
            logger.warning("validate_math_fences timed out; keeping raw assistant text")
            canonical = ctx.verified_math.canonical_fence if ctx.verified_math is not None else None
            assistant_text = seams.math_fence_service.replace_unclosed_graph_fence_safe(
                assistant_text, canonical
            )
        except Exception:
            logger.exception("validate_math_fences failed; keeping raw assistant text")
            canonical = ctx.verified_math.canonical_fence if ctx.verified_math is not None else None
            assistant_text = seams.math_fence_service.replace_unclosed_graph_fence_safe(
                assistant_text, canonical
            )

        from app.services.vocab_quiz import strip_vocab_session_metadata

        assistant_text = strip_vocab_session_metadata(assistant_text)
        if settings.chemistry_enabled and (
            "```smiles" in assistant_text.lower() or "```chemistry" in assistant_text.lower()
        ):
            from app.services import (
                chemistry_fence as chemistry_fence_service,
            )

            pre_chem_text = assistant_text
            try:
                assistant_text = await run_sympy(
                    chemistry_fence_service.enrich_chemistry_fences_worker,
                    assistant_text,
                    timeout=settings.math_solve_timeout_seconds,
                )
            except TimeoutError:
                logger.warning("enrich_chemistry_fences timed out; keeping raw assistant text")
            except Exception:
                logger.exception("enrich_chemistry_fences failed; keeping raw assistant text")
            if result is not None and assistant_text != pre_chem_text:
                result["final_content"] = assistant_text
        if result is not None and assistant_text != pre_validation_text:
            result["final_content"] = assistant_text

        if ctx.search_sources:
            assistant_text = seams.web_search_service.strip_sources_from_text(assistant_text)
            if result is not None:
                result["search_sources"] = json.dumps(
                    seams.web_search_service.sources_payload(ctx.search_sources)
                )
                result["final_content"] = assistant_text
            sources_fence = seams.web_search_service.format_sources_fence(ctx.search_sources)
            if sources_fence and not (should_cancel and should_cancel()):
                assistant_text = f"{assistant_text}{sources_fence}".strip()
        if ctx.local_places and ctx.search_sources and "```places" not in assistant_text.lower():
            assistant_text = seams.web_search_service.strip_duplicate_venue_list(assistant_text)
            places_fence = seams.web_search_service.format_places_fence(ctx.search_sources)
            if places_fence and not (should_cancel and should_cancel()):
                assistant_parts[:] = [assistant_text] if assistant_text.strip() else []
                assistant_parts.append(places_fence)
                assistant_text = "".join(assistant_parts).strip()
                if result is not None:
                    result["final_content"] = assistant_text
        if ctx.instant_reply and not usage:
            usage["output"] = 0
            usage["input"] = 0
        if result is not None and not ctx.skip_memory_jobs:
            transcript = f"User: {ctx.user_message_content}\nAssistant: {assistant_text}"
            if reminder_created > 0 or seams.todos_service.transcript_implies_todo_sync(transcript):
                result["todos_sync"] = "1"
            if reminder_created > 0:
                result["final_content"] = assistant_text
        if result is not None and was_cancelled and assistant_text:
            result["final_content"] = assistant_text

        # Prose artifact cleanup — runs last so it never interferes with
        # fence parsing. Strips orphan colon lines and collapses 3+ blank
        # lines. Only sets final_content when the text actually changes.
        from app.services.chat.prose_normalizer import normalize_prose_artifacts, prose_changed

        normalized = normalize_prose_artifacts(assistant_text)
        if prose_changed(assistant_text, normalized):
            assistant_text = normalized
            if result is not None:
                result["final_content"] = assistant_text
    except Exception:
        logger.exception("Post-stream enrichment failed; persisting raw assistant text")
        assistant_text = raw_assistant_text
        if result is not None and was_cancelled and assistant_text:
            result["final_content"] = assistant_text
    return assistant_text


def log_background_task_failure(task: asyncio.Task[Any], message: str) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.exception(message, exc_info=exc)


async def register_and_enqueue_finalize(
    seams: Any,
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    assistant_text: str,
    usage: dict[str, int],
    result: dict[str, Any] | None,
) -> None:
    if ctx.assistant_message_id is None:
        ctx.assistant_message_id = seams.uuid7()
    if result is not None:
        result["resolved_model"] = ctx.model
        result["message_id"] = str(ctx.assistant_message_id)
        if ctx.recalled_count:
            result["recalled"] = str(ctx.recalled_count)
        if ctx.memory_hints:
            result["memory_hints"] = json.dumps(ctx.memory_hints)
        if ctx.context_summarized:
            result["context_summarized"] = str(ctx.context_summarized)
    await seams.mark_pending_finalize(redis, ctx.chat_id)
    finalize_db_task = seams.create_background_task(
        seams.finalize_stream_turn_db(redis, ctx, assistant_text, usage, result),
        name="finalize_stream_turn_db",
    )
    seams.register_pending_finalize(ctx.chat_id, finalize_db_task)
    finalize_db_task.add_done_callback(
        lambda task: log_background_task_failure(task, "Background DB finalization failed")
    )

    async def run_jobs_after_db() -> None:
        try:
            await finalize_db_task
            seams.detect_quality_issues(ctx, assistant_text)
            await seams.enqueue_post_turn_jobs(redis, settings, ctx, assistant_text)
        except Exception:
            logger.exception("Background job enqueue failed")

    jobs_task = seams.create_background_task(run_jobs_after_db(), name="post_turn_jobs")
    jobs_task.add_done_callback(
        lambda task: log_background_task_failure(task, "Background finalization failed")
    )
    if result is not None:
        result["_finalize_task"] = jobs_task
        result["_finalize_db_task"] = finalize_db_task


async def finalize_terminal_image_turn(
    seams: Any,
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    result: dict[str, Any] | None,
) -> None:
    try:
        ctx.assistant_message_id = UUID(ctx.terminal_image_message_id)
    except (ValueError, TypeError):
        logger.warning(
            "terminal_image_message_id not a UUID: %r",
            ctx.terminal_image_message_id,
        )
    assistant_text = ctx.terminal_image_content or ""

    async def slim_finalize() -> None:
        try:
            async with seams.SessionLocal() as session:
                await seams.chats_repo.touch_by_id(session, ctx.chat_id, commit=True)
            await seams.enqueue_post_turn_jobs(redis, settings, ctx, assistant_text)
        except Exception:
            logger.exception("Slim finalize for terminal image failed")

    task = seams.create_background_task(slim_finalize(), name="finalize_terminal_image")
    task.add_done_callback(
        lambda done: log_background_task_failure(done, "Terminal-image finalize failed")
    )
    if result is not None:
        result["_finalize_task"] = task


async def stream_and_finalize(
    seams: Any,
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    should_cancel: Callable[[], bool] | None,
    result: dict[str, Any] | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
    resources: Any | None = None,
) -> AsyncIterator[str]:
    usage: dict[str, int] = {}
    accum = StreamAccum()
    try:
        try:
            if ctx.instant_reply:
                async for token in run_instant_reply_path(
                    ctx, should_cancel=should_cancel, accum=accum
                ):
                    yield token
            else:
                await run_tool_loop_path(
                    seams,
                    redis,
                    settings,
                    ctx,
                    usage=usage,
                    on_status=on_status,
                    should_cancel=should_cancel,
                )
                if ctx.terminal_image_content and ctx.terminal_image_message_id:
                    if result is not None:
                        result["message_id"] = ctx.terminal_image_message_id
                        result["final_content"] = ctx.terminal_image_content
                        result["resolved_model"] = ctx.terminal_image_model or "image-gen-model"
                    if resources is not None:
                        await resources.refund()
                    else:
                        await seams.quota_service.refund_usage(
                            redis,
                            str(ctx.user_id),
                            ctx.reserved_tokens,
                        )
                    await finalize_terminal_image_turn(seams, redis, settings, ctx, result)
                    return
                if ctx.instant_reply:
                    async for token in run_instant_reply_path(
                        ctx, should_cancel=should_cancel, accum=accum
                    ):
                        yield token
                else:
                    async for token in run_llm_token_stream(
                        seams,
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
            raise ModelUnavailableError(
                "That model isn't responding right now. Try again — or pick a different model.",
                failed_alias=ctx.model,
            )
        assistant_text = await enrich_final_content(
            seams,
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
        await register_and_enqueue_finalize(
            seams,
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
