"""How a turn's reply text is produced: an instant reply, the tool loop, the model stream.

``stream_pipeline.stream_and_finalize`` picks the paths for a turn and
finalizes the text they produce.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import replace
from typing import Any

from redis.asyncio import Redis

from app.core.background_tasks import create_background_task
from app.core.config import Settings
from app.modules.chat import tool_loop
from app.modules.chat.prompt_builder import StreamReasoningFn, StreamStatusFn
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.stream_events import clear_task_cancellation
from app.modules.chat.stream_scaffold import ScaffoldFilter
from app.modules.chat.tool_gate import should_classify_tool_web_search
from app.modules.chat.tool_loop.parts import classified_live_parts, open_parts, turn_plan
from app.modules.chat.turn_deps import ChatTurnDeps
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext, await_user_message_persist
from app.modules.web_search.subject import collect_prior_user_messages, last_assistant_content
from app.services import model_health as model_health_service
from app.services.solving import VerifiedMathBlock

logger = logging.getLogger(__name__)

_STOP_CLOSE_TIMEOUT_SECONDS = 2.0


async def _close_stopped_stream(close: Callable[[], Any]) -> None:
    """Close a stopped provider stream without blocking the reply save."""
    with suppress(Exception, asyncio.CancelledError):
        await asyncio.wait_for(close(), _STOP_CLOSE_TIMEOUT_SECONDS)


# Provider finish_reason values that mean the reply stopped short of a
# complete answer. "stop" is a normal end; these are not.
_INCOMPLETE_FINISH_REASONS = frozenset({"length", "max_tokens", "content_filter"})


async def run_instant_reply_path(
    ctx: StreamContext,
    *,
    should_cancel: Callable[[], bool] | None,
    accum: StreamAccum,
) -> AsyncIterator[str]:
    if not (should_cancel and should_cancel()):
        if ctx.instant_reply is None:
            return
        await await_user_message_persist(ctx)
        if ctx.timing is not None:
            ctx.timing.mark_first_token()
        accum.parts.append(ctx.instant_reply)
        accum.shown.append(ctx.instant_reply)
        yield ctx.instant_reply
    else:
        accum.mark_user_stop()


async def run_tool_loop_path(
    deps: ChatTurnDeps,
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    usage: dict[str, int],
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
) -> None:
    content = ctx.user_message_content if isinstance(ctx.user_message_content, str) else ""
    sources = ctx.search_sources if isinstance(ctx.search_sources, list) else []
    lightweight = bool(ctx.lightweight_turn)
    has_instant = ctx.instant_reply is not None
    has_verified = ctx.verified_subject is not None
    has_sources = bool(sources)
    web_search_flag: bool | None = None
    search_parts: list[str] | None = None
    if await deps.quota.global_spend_exceeded(redis, settings):
        logger.warning(
            "skipping MCP tool loop: global spend cap user_id=%s chat_id=%s",
            ctx.user_id,
            ctx.chat_id,
        )
        return
    # Sync heuristic first (math / news). Classifier only when
    # that gate is weak so we do not add an LLM round to already-needed turns.
    if not tool_loop.turn_needs_tool_loop(
        content,
        lightweight=lightweight,
        has_instant_reply=has_instant,
        has_verified_math=has_verified,
        has_search_sources=has_sources,
        settings=settings,
        user=ctx.user,
    ):
        if should_classify_tool_web_search(
            content,
            settings,
            lightweight=lightweight,
            has_instant_reply=has_instant,
            has_verified_math=has_verified,
            has_search_sources=has_sources,
            user=ctx.user,
        ):
            if isinstance(ctx.web_search_classified, bool):
                web_search_flag = ctx.web_search_classified
            else:
                prompt = ctx.prompt_messages if isinstance(ctx.prompt_messages, list) else []
                # Each request of a multi-part message is classified for itself, and
                # searched for itself (``tool_loop.parts``).
                found = await classified_live_parts(
                    open_parts(content, has_verified_math=has_verified, settings=settings),
                    settings,
                    prior_user_messages=collect_prior_user_messages(prompt, content) or None,
                    prior_assistant=last_assistant_content(prompt),
                )
                web_search_flag = bool(found)
                search_parts = found if turn_plan(content, settings).multi else None
        if not tool_loop.turn_needs_tool_loop(
            content,
            lightweight=lightweight,
            has_instant_reply=has_instant,
            has_verified_math=has_verified,
            has_search_sources=has_sources,
            web_search=web_search_flag,
            settings=settings,
            user=ctx.user,
        ):
            return
    (
        ctx.prompt_messages,
        tool_verified,
        terminal_image,
        tool_search_hits,
    ) = await tool_loop.run_tool_rounds(
        settings=settings,
        messages=ctx.prompt_messages,
        usage=usage,
        on_status=on_status,
        should_cancel=should_cancel,
        user=ctx.user,
        redis=redis,
        chat_id=ctx.chat_id,
        web_search=web_search_flag,
        user_timezone=ctx.user_timezone,
        user_text=content,
        user_location=ctx.search_location,
        has_verified_math=has_verified,
        search_parts=search_parts,
    )
    if tool_verified is not None:
        ctx.verified_subject = _with_tool_verified(ctx.verified_subject, tool_verified)
    if terminal_image is not None:
        ctx.terminal_image_message_id = terminal_image.message_id
        ctx.terminal_image_content = terminal_image.final_content
        ctx.terminal_image_model = terminal_image.resolved_model
    if tool_search_hits and not ctx.search_sources:
        ctx.search_sources = tool_search_hits


def _with_tool_verified(server: Any, tool: Any) -> Any:
    """The turn's verified block after the tool loop.

    A block the server built from the user's own text is never replaced by one
    the model's tool call produced: the model may have mistyped the problem.
    A maths block may gain a diagram the server did not draw; its answer stays.
    """
    if server is None:
        return tool
    if not isinstance(server, VerifiedMathBlock) or not isinstance(tool, VerifiedMathBlock):
        return server
    kinds = {
        fence.get("type") for fence in (server.canonical_fence, *server.canonical_fences) if fence
    }
    kinds.add("answer")
    extra: list[dict[str, Any]] = []
    for fence in (tool.canonical_fence, *tool.canonical_fences):
        if fence and fence.get("type") not in kinds:
            kinds.add(fence.get("type"))
            extra.append(fence)
    if not extra:
        return server
    return replace(server, canonical_fences=[*server.canonical_fences, *extra])


async def run_llm_token_stream(
    deps: ChatTurnDeps,
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    usage: dict[str, int],
    should_cancel: Callable[[], bool] | None,
    outcome: TurnOutcome | None,
    on_reasoning: StreamReasoningFn | None,
    accum: StreamAccum,
    on_status: StreamStatusFn | None = None,
) -> AsyncIterator[str]:
    stream_meta: dict[str, str] = {}
    requested_model = ctx.model
    started = time.perf_counter()
    stream_ok = False
    scaffold = ScaffoldFilter()
    if on_status is not None:
        # The model is writing now: a tool or search label must not linger.
        await on_status("composing")
    if ctx.timing is not None:
        # Reserve top-up and the tool loop have finished. The interval from
        # here includes gateway routing/retries, not only upstream inference.
        ctx.timing.mark_phase("gateway_request_start")
    llm_stream = deps.llm.stream_chat_completion(
        settings=settings,
        model_alias=ctx.model,
        messages=ctx.prompt_messages,
        max_tokens=ctx.max_output_tokens,
        usage=usage,
        fallback_aliases=ctx.fallback_models,
        stream_meta=stream_meta,
        on_reasoning=on_reasoning,
        thinking=ctx.thinking,
    )
    try:
        async for token in llm_stream:
            if should_cancel and should_cancel():
                accum.mark_user_stop()
                break
            if not accum.parts:
                # The user's row commits beside the provider's time to first
                # token. No token goes out before it has: a reply to a message
                # that never saved would be neither stored nor charged. The
                # model did answer, so a failed save is not its health sample.
                stream_ok = True
                await await_user_message_persist(ctx)
                if ctx.timing is not None:
                    ctx.timing.mark_first_token()
            accum.parts.append(token)
            if ctx.answer_photo is not None and ctx.answer_photo.watching:
                ctx.answer_photo.feed("".join(accum.parts))
            visible = scaffold.feed(token)
            if not visible:
                continue
            accum.shown.append(visible)
            yield visible
            # Stop can land while we are parked on this yield. The consumer
            # resumes us so we halt before the next provider read and save.
            if should_cancel and should_cancel():
                accum.mark_user_stop()
                break
        if not accum.was_cancelled and (tail := scaffold.flush()):
            accum.shown.append(tail)
            yield tail
        stream_ok = bool(accum.parts) or accum.was_cancelled
        finish = stream_meta.get("finish_reason")
        if finish in _INCOMPLETE_FINISH_REASONS and not accum.was_cancelled:
            accum.mark_truncated()
    except asyncio.CancelledError:
        clear_task_cancellation()
        accum.mark_user_stop()
        raise
    finally:
        close = getattr(llm_stream, "aclose", None)
        if close is not None:
            if accum.was_cancelled:
                # Closing the provider socket can outlive the stop. Do not
                # make the partial-reply save wait on it.
                create_background_task(
                    _close_stopped_stream(close),
                    name="close_stopped_stream",
                )
            else:
                await close()
        if not accum.was_cancelled:
            try:
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
    if outcome is not None and resolved and resolved != requested_model:
        outcome.fallback_used = True
