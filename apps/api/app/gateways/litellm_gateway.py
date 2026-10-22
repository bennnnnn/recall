import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from typing import Any, NamedTuple, Self

from litellm import acompletion

from app.core.background_tasks import create_background_task
from app.core.config import Settings
from app.gateways import llm_spend, mock_llm
from app.gateways.reasoning import reasoning_body
from app.gateways.stream_signals import (
    REQUEST_FAULT,
    FirstReplyWatch,
    StreamAttempt,
    first_reply_cap,
    prompt_shape,
    provider_fault,
    reasoning_delta,
)

# The completion kinds split out of this module are part of its public surface
# (callers use ``litellm_gateway.complete_structured`` and friends). They reach
# this module's provider seams (``acompletion``, ``resolve_route``,
# ``_litellm_kwargs``) at call time, so a test patches each seam once, here.
from app.gateways.structured_completion import _fallback_alias
from app.gateways.structured_completion import complete_structured as complete_structured
from app.gateways.think_stripper import STRAY_THINK_LEAD_HOLD, ThinkStripper
from app.gateways.tool_completion import complete_with_tools as complete_with_tools
from app.gateways.vision_completion import vision_completion as vision_completion
from app.models import model_catalog
from app.models.model_catalog import ChatModel

logger = logging.getLogger(__name__)


class ModelUnavailableError(Exception):
    """Primary (and optional fallback) chat models could not stream."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "model_unavailable",
        failed_alias: str | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.failed_alias = failed_alias
        # Why the model call failed (``stream_signals.StreamAttempt.cause``).
        self.cause = cause

    @classmethod
    def for_alias(
        cls, alias: str, *, code: str = "model_unavailable", cause: str | None = None
    ) -> Self:
        """The user-facing "model isn't responding" error for one failed alias."""
        return cls(_CHAT_MODEL_UNAVAILABLE_MSG, code=code, failed_alias=alias, cause=cause)


_CHAT_MODEL_UNAVAILABLE_MSG = (
    "That model isn't responding right now. Try again — or pick a different model."
)


async def _acompletion_with_fallback(
    settings: Settings,
    primary_alias: str,
    *,
    messages: list[dict[str, str]],
    max_tokens: int,
    response_format: dict[str, str] | None = None,
) -> Any | None:
    """Run acompletion against the primary background alias; on provider outage
    retry once against the fallback alias. Returns the LiteLLM response object,
    or None if both fail. Used by the background paths (titles, summaries,
    project extraction) so a single-provider DeepSeek incident doesn't silently
    stall every background pipeline.
    """
    fallback = _fallback_alias(settings, primary_alias)
    for alias in (primary_alias, fallback):
        if alias is None:
            continue
        try:
            route = resolve_route(alias)
            kwargs = _litellm_kwargs(settings, route, thinking=False)
            params: dict[str, Any] = dict(
                model=route.model, messages=messages, max_tokens=max_tokens, **kwargs
            )
            if response_format is not None:
                params["response_format"] = response_format
            async with asyncio.timeout(settings.background_llm_timeout_seconds):
                response = await acompletion(**params)
            llm_spend.meter_model_call(alias, response)
            return response
        except TimeoutError:
            if alias == primary_alias and fallback is not None:
                logger.warning(
                    "Background LLM %s timed out after %ss; retrying with fallback %s",
                    primary_alias,
                    settings.background_llm_timeout_seconds,
                    fallback,
                )
                continue
            logger.warning(
                "Background LLM %s timed out after %ss",
                alias,
                settings.background_llm_timeout_seconds,
            )
            return None
        except Exception:
            if alias == primary_alias and fallback is not None:
                logger.warning(
                    "Background LLM %s unavailable; retrying with fallback %s",
                    primary_alias,
                    fallback,
                )
                continue
            logger.exception("Background LLM %s failed", alias)
            return None
    return None


def resolve_route(alias: str) -> ChatModel:
    return model_catalog.get(alias)


def _litellm_kwargs(
    settings: Settings,
    route: ChatModel,
    *,
    latency_sensitive: bool = False,
    thinking: bool | str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    api_key = getattr(settings, route.api_key_field, "")
    if not api_key:
        raise ModelUnavailableError.for_alias(route.id, cause=REQUEST_FAULT)
    kwargs["api_key"] = api_key
    if route.api_base:
        kwargs["api_base"] = route.api_base
    if route.model.startswith("openrouter/"):
        kwargs.setdefault(
            "extra_headers",
            {
                "HTTP-Referer": "https://github.com/bennnnnn/recall",
                "X-Title": "Recall",
            },
        )
        # OpenRouter's default route is price-weighted. The user-visible token
        # stream values TTFT more than small provider-price differences, so ask
        # OpenRouter to prefer the endpoint with the lowest observed latency.
        # Background jobs keep the default routing; tool selection is also
        # on the critical path before the user-visible stream.
        if latency_sensitive:
            kwargs["extra_body"] = {"provider": {"sort": "latency"}}
    # Ordinary questions must not wait on a thinking pass; a hard one gets the
    # cheapest level that thinks, and a disputed answer one level more. Each
    # value is one the model lists, so an unsupported level is never sent.
    reasoning = reasoning_body(route, thinking)
    if reasoning is not None:
        kwargs.setdefault("extra_body", {})
        kwargs["extra_body"]["reasoning"] = reasoning
    return kwargs


def _apply_usage(usage: dict[str, int] | None, source: Any) -> None:
    """Add a stream chunk's or a whole response's reported tokens onto ``usage``."""
    if usage is None:
        return
    source_usage = getattr(source, "usage", None)
    if not source_usage:
        return
    prompt = getattr(source_usage, "prompt_tokens", None)
    completion = getattr(source_usage, "completion_tokens", None)
    if prompt is not None:
        usage["input"] = usage.get("input", 0) + int(prompt)
    if completion is not None:
        usage["output"] = usage.get("output", 0) + int(completion)


def _merge_attempt_usage(usage: dict[str, int] | None, attempt: dict[str, int]) -> None:
    """Charge the caller for one stream attempt (only an attempt that produced content)."""
    if usage is None:
        return
    usage["input"] = usage.get("input", 0) + attempt.get("input", 0)
    usage["output"] = usage.get("output", 0) + attempt.get("output", 0)


async def stream_chat_completion(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    usage: dict[str, int] | None = None,
    fallback_aliases: list[str] | None = None,
    stream_meta: dict[str, str] | None = None,
    on_reasoning: Callable[[str], Awaitable[None]] | None = None,
    thinking: bool | str | None = None,
    attempts: list[StreamAttempt] | None = None,
    on_thinking: Callable[[], Awaitable[None]] | None = None,
    may_try: Callable[[str], Awaitable[bool]] | None = None,
) -> AsyncIterator[str]:
    """Stream one reply, moving down ``fallback_aliases`` until a model answers.

    ``attempts`` gets one record per model tried, in order: which failed (before
    its text, or partway), and how fast each provider started. ``on_thinking``
    runs when a model is seen reasoning before any of its text. ``may_try`` is
    asked before each model but the last; False passes it by untried.
    """
    if mock_llm.should_mock_llm(settings):
        logger.info("Using mock LLM stream for alias=%s", model_alias)
        if stream_meta is not None:
            stream_meta["model_alias"] = model_alias
        async for token in mock_llm.mock_stream(messages=messages):
            yield token
        return

    aliases = [model_alias, *(fallback_aliases or [])]
    shape = prompt_shape(messages)
    last_error: ModelUnavailableError | None = None

    for index, alias in enumerate(aliases):
        has_next = index < len(aliases) - 1
        if has_next and may_try is not None and not await may_try(alias):
            # A recovering model that another turn is trying (model health's probe).
            logger.info("Chat stream %s passed over: another turn is trying it", alias)
            continue
        # Buffer until the first non-whitespace token so whitespace-only
        # "success" streams (common flaky provider quirk) still fall through
        # to the next alias instead of locking in an empty reply.
        pending: list[str] = []
        started = False
        # Discarded attempts must not add provider tokens onto the caller's
        # daily quota. Tool-loop usage already lives on `usage`; only merge
        # the attempt that actually produced content.
        attempt_usage: dict[str, int] = {}
        cap = first_reply_cap(settings, alias, thinking, has_next=has_next, prompt=shape)
        attempt = StreamAttempt(alias)
        if attempts is not None:
            attempts.append(attempt)
        try:
            if stream_meta is not None:
                stream_meta.pop("finish_reason", None)
            async for token in _stream_chat_once(
                settings=settings,
                model_alias=alias,
                messages=messages,
                max_tokens=max_tokens,
                usage=attempt_usage,
                on_reasoning=on_reasoning,
                stream_meta=stream_meta,
                thinking=thinking,
                first_content_timeout_seconds=cap,
                attempt=attempt,
                on_thinking=on_thinking,
            ):
                if not started:
                    pending.append(token)
                    if not "".join(pending).strip():
                        continue
                    started = True
                    for piece in pending:
                        yield piece
                    pending.clear()
                    continue
                yield token
            if started:
                attempt.end(failed=False)
                _merge_attempt_usage(usage, attempt_usage)
                if stream_meta is not None:
                    stream_meta["model_alias"] = alias
                return
            logger.warning(
                "Chat stream %s returned no content%s",
                alias,
                f"; retrying with fallback {aliases[index + 1]}" if has_next else "",
            )
            raise ModelUnavailableError.for_alias(alias, cause="empty")
        except ModelUnavailableError as exc:
            last_error = exc
            attempt.end(failed=True, cause=exc.cause)
            # Mid-stream failure: client already has partial tokens — falling
            # back would concatenate partial + full into one persisted reply.
            if started:
                _merge_attempt_usage(usage, attempt_usage)
                raise
            if has_next:
                logger.warning(
                    "Chat stream %s unavailable; retrying with fallback %s",
                    alias,
                    aliases[index + 1],
                )
                continue
            failed = exc.failed_alias or alias
            if stream_meta is not None:
                stream_meta["model_alias"] = failed
            raise ModelUnavailableError.for_alias(failed, cause=exc.cause) from exc

    if last_error is not None:
        raise last_error


_PROVIDER_CLOSE_TIMEOUT_SECONDS = 2.0


async def _close_provider_stream(close: Callable[[], Awaitable[None]]) -> None:
    """Close the provider socket after a stop without blocking the caller."""
    with suppress(Exception, asyncio.CancelledError):
        await asyncio.wait_for(close(), _PROVIDER_CLOSE_TIMEOUT_SECONDS)


class _ChunkRead(NamedTuple):
    # Reply text the chunk releases (the think filter may hold some back).
    text: str
    # The model is seen thinking: reasoning on its own channel, or text held as one.
    thinking: bool
    # The provider sent reasoning or text at all.
    delta: bool


def _read_chunk(
    chunk: Any,
    *,
    usage: dict[str, int] | None,
    stream_meta: dict[str, str] | None,
    stripper: ThinkStripper,
) -> _ChunkRead:
    """What one provider chunk shows."""
    _apply_usage(usage, chunk)
    choices = getattr(chunk, "choices", None) or []
    if not choices:
        return _ChunkRead("", thinking=False, delta=False)
    reason = getattr(choices[0], "finish_reason", None)
    if reason and stream_meta is not None:
        stream_meta["finish_reason"] = str(reason)
    delta = getattr(choices[0], "delta", None)
    reasoning = reasoning_delta(delta)
    if reasoning:
        # Text after reasoning on its own channel is most likely the answer.
        stripper.reasoning_streamed()
    content = getattr(delta, "content", None) or "" if delta is not None else ""
    text = stripper.feed(content) if content else ""
    return _ChunkRead(text, reasoning or stripper.holding_thought, reasoning or bool(content))


async def _tell_thinking(on_thinking: Callable[[], Awaitable[None]], model_alias: str) -> None:
    """Best-effort: a status that fails to reach the client is not the model's failure."""
    try:
        await on_thinking()
    except Exception:
        logger.warning("Thinking status failed for alias=%s", model_alias, exc_info=True)


async def _stream_chat_once(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    usage: dict[str, int] | None = None,
    on_reasoning: Callable[[str], Awaitable[None]] | None = None,
    stream_meta: dict[str, str] | None = None,
    first_content_timeout_seconds: float | None = None,
    thinking: bool | str | None = None,
    attempt: StreamAttempt | None = None,
    on_thinking: Callable[[], Awaitable[None]] | None = None,
) -> AsyncIterator[str]:
    """One model's stream. ``first_content_timeout_seconds`` caps the wait for its
    first text or reasoning (``stream_signals.first_reply_cap``)."""
    route = resolve_route(model_alias)
    kwargs = _litellm_kwargs(settings, route, latency_sensitive=True, thinking=thinking)
    stripper = ThinkStripper(lead_hold=STRAY_THINK_LEAD_HOLD if route.stray_think_guard else 0)
    # Signature kept so WS/SSE callers stay unchanged; CoT is not forwarded.
    _ = on_reasoning
    watch = FirstReplyWatch(first_content_timeout_seconds)
    response = None
    try:
        # A first-reply cap also bounds the wait for the stream to open.
        async with asyncio.timeout(watch.bound(settings.chat_stream_connect_timeout_seconds)):
            response = await acompletion(
                model=route.model,
                messages=messages,
                stream=True,
                max_tokens=max_tokens,
                stream_options={"include_usage": True},
                **kwargs,
            )
        # Idle timeout per chunk, plus a hard wall-clock cap on the whole reply.
        idle_seconds = settings.chat_stream_timeout_seconds
        max_seconds = max(1, settings.chat_stream_max_seconds)
        deadline = time.monotonic() + max_seconds
        stream_iter = response.__aiter__()

        async def _next_chunk() -> Any | None:
            try:
                return await stream_iter.__anext__()
            except StopAsyncIteration:
                return None

        def stop_reason() -> tuple[str, str] | None:
            """(what ran out, the failure's cause), or None while the stream may go on."""
            if time.monotonic() >= deadline:
                return f"wall-clock {max_seconds}s", "timeout"
            cap = watch.expired()
            return (cap, "cap") if cap is not None else None

        while True:
            if (stop := stop_reason()) is not None:
                raise _gave_up(model_alias, *stop)
            remaining = deadline - time.monotonic()
            try:
                chunk = await asyncio.wait_for(
                    _next_chunk(),
                    timeout=watch.bound(min(idle_seconds, remaining)),
                )
            except TimeoutError as exc:
                stop = stop_reason() or (f"idle {idle_seconds}s", "timeout")
                raise _gave_up(model_alias, *stop) from exc
            if chunk is None:
                break
            read = _read_chunk(chunk, usage=usage, stream_meta=stream_meta, stripper=stripper)
            if read.delta and attempt is not None:
                attempt.delta()
            if watch.saw(text=read.text, thinking=read.thinking) and on_thinking is not None:
                await _tell_thinking(on_thinking, model_alias)
            if read.text:
                yield read.text
        tail = stripper.flush()
        if tail:
            yield tail
    except TimeoutError as exc:
        # Only the wait for the stream to open raises one here.
        cap = watch.expired()
        logger.warning(
            "LiteLLM stream for alias=%s did not open: %s",
            model_alias,
            cap or f"connect {settings.chat_stream_connect_timeout_seconds}s",
        )
        cause = "cap" if cap is not None else "timeout"
        raise ModelUnavailableError.for_alias(model_alias, cause=cause) from exc
    except ModelUnavailableError:
        raise
    except Exception as exc:
        logger.exception("LiteLLM streaming failed for alias=%s", model_alias)
        raise ModelUnavailableError.for_alias(model_alias, cause=provider_fault(exc)) from exc
    finally:
        close = getattr(response, "aclose", None)
        if close is not None:
            # A stop cancels this task. Awaiting the socket close here either
            # raises again immediately or waits out the provider, and the
            # partial reply never gets saved. Close in the background.
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                create_background_task(
                    _close_provider_stream(close),
                    name="close_provider_stream",
                )
            else:
                with suppress(Exception):
                    await close()


def _gave_up(model_alias: str, ran_out: str, cause: str) -> ModelUnavailableError:
    logger.warning("LiteLLM stream for alias=%s gave up: %s", model_alias, ran_out)
    return ModelUnavailableError.for_alias(model_alias, cause=cause)


async def complete_text(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, str]],
    max_tokens: int = 256,
) -> str | None:
    """Return assistant text content from a non-streaming completion (or None)."""
    if mock_llm.should_mock_llm(settings):
        return None
    response = await _acompletion_with_fallback(
        settings, model_alias, messages=messages, max_tokens=max_tokens
    )
    if response is None:
        return None
    try:
        return (response.choices[0].message.content or "").strip() or None
    except Exception:
        logger.exception("Text completion failed to parse response for %s", model_alias)
        return None
