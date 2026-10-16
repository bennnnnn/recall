"""One turn's reply: produce it, finalize it, then register its save and post-turn jobs.

The text comes from ``stream_paths`` (instant reply, tool loop, model stream);
``finalize_passes`` turns it into the reply that persists.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways.litellm_gateway import ModelUnavailableError
from app.modules.chat.finalize_passes import enrich_final_content
from app.modules.chat.prompt_builder import StreamReasoningFn, StreamStatusFn
from app.modules.chat.related_prompts import schedule_related_prompts
from app.modules.chat.stream_events import await_ignoring_cancel, clear_task_cancellation
from app.modules.chat.stream_paths import (
    StreamAccum,
    run_instant_reply_path,
    run_llm_token_stream,
    run_tool_loop_path,
)
from app.modules.chat.turn_prep import StreamContext, await_user_message_persist
from app.modules.images.answer_photo import AnswerPhoto

logger = logging.getLogger(__name__)


def log_background_task_failure(task: asyncio.Task[Any], message: str) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.exception(message, exc_info=exc)


def _prior_window(prompt_messages: Any) -> list[Any]:
    """The recent window before this turn's own user line.

    Tool and web results can follow that line, so the cut is at the last user
    message, not the last message.
    """
    if not isinstance(prompt_messages, list):
        return []
    for index in range(len(prompt_messages) - 1, -1, -1):
        message = prompt_messages[index]
        if isinstance(message, dict) and message.get("role") == "user":
            return prompt_messages[:index]
    return []


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
        schedule_related_prompts(
            result,
            redis,
            settings,
            message_id=str(ctx.assistant_message_id),
            question=ctx.user_message_content or "",
            answer=assistant_text,
            prior=_prior_window(ctx.prompt_messages),
            allow_general=not ctx.lightweight_turn and ctx.instant_reply is None,
        )
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
                if ctx.timing is not None:
                    ctx.timing.mark_phase("tool_loop_start")
                try:
                    await run_tool_loop_path(
                        seams,
                        redis,
                        settings,
                        ctx,
                        usage=usage,
                        on_status=on_status,
                        should_cancel=should_cancel,
                    )
                finally:
                    if ctx.timing is not None:
                        ctx.timing.mark_phase("tool_loop_done")
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
                    await await_user_message_persist(ctx)
                    await finalize_terminal_image_turn(seams, redis, settings, ctx, result)
                    return
                if ctx.instant_reply:
                    async for token in run_instant_reply_path(
                        ctx,
                        should_cancel=should_cancel,
                        accum=accum,
                    ):
                        yield token
                else:
                    if settings.image_search_enabled and ctx.user is not None:
                        ctx.answer_photo = AnswerPhoto(settings, ctx.user)
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
            clear_task_cancellation()
            accum.mark_user_stop()
            logger.info(
                "Hard cancel with partial reply; finalizing chat_id=%s parts=%d",
                ctx.chat_id,
                len(accum.parts),
            )
        except ModelUnavailableError:
            if not accum.parts:
                raise
            accum.mark_interrupted()
            logger.info(
                "Provider fail with partial reply; finalizing chat_id=%s parts=%d",
                ctx.chat_id,
                len(accum.parts),
            )
        assistant_text = "".join(accum.parts).strip()
        if not assistant_text:
            raise ModelUnavailableError(
                "That model isn't responding right now. Try again — or pick a different model.",
                failed_alias=ctx.model,
            )
        if result is not None and accum.completion != "complete":
            result["completion"] = accum.completion

        async def persist_reply() -> None:
            nonlocal assistant_text
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
            await await_user_message_persist(ctx)
            await register_and_enqueue_finalize(
                seams,
                redis,
                settings,
                ctx,
                assistant_text=assistant_text,
                usage=usage,
                result=result,
            )

        # Closing the provider socket after Stop cancels this task again.
        # The save runs on its own task so that second cancel cannot drop it.
        if accum.was_cancelled:
            await await_ignoring_cancel(persist_reply())
        else:
            await persist_reply()
    finally:
        if ctx.user_message_persist is not None:
            try:
                await await_user_message_persist(ctx)
            except Exception:
                logger.exception(
                    "User message persist failed chat_id=%s",
                    ctx.chat_id,
                )
        if ctx.timing is not None:
            ctx.timing.log_summary(
                user_id=ctx.user_id,
                chat_id=ctx.chat_id,
                model=ctx.model,
                lightweight=ctx.lightweight_turn,
                content_chars=len(ctx.user_message_content or ""),
            )
