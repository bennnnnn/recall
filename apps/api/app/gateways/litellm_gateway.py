import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from typing import Any, NamedTuple, Self

# Re-exported: the completion gateways call the provider through this module.
from litellm import acompletion as acompletion

from app.core.background_tasks import create_background_task
from app.core.config import Settings
from app.gateways import llm_spend, mock_llm
from app.gateways.prompt_cache import with_cache_breakpoint
from app.gateways.reasoning import reasoning_body
from app.gateways.stream_signals import (
    REQUEST_FAULT,
    THOUGHT_OUT,
    FirstReplyWatch,
    StreamAttempt,
    first_reply_cap,
    prompt_shape,
    provider_fault,
    reasoning_delta,
)
from app.gateways.stream_thinking import (
    AttemptThinking,
    StreamClock,
    ThinkingPlan,
    as_attempt,
)
from app.gateways.stream_tool_calls import StreamedToolCalls, ToolOffer
from app.gateways.stream_usage import apply_usage, merge_attempt_usage

# The completion kinds split out of this module are its public surface too. They call
# the provider through this module (``acompletion``, ``resolve_route``, ``_litellm_kwargs``),
# imported at call time (at load, a cycle), so a test patches each seam once, here.
from app.gateways.structured_completion import complete_structured as complete_structured
from app.gateways.text_completion import complete_text as complete_text
from app.gateways.text_tool_calls import TextToolCalls
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


# There is no model picker in the composer: another model is chosen in Settings (MODEL-13).
_CHAT_MODEL_UNAVAILABLE_MSG = (
    "That model isn't responding right now. Try again, or choose another model in "
    "Settings > Models."
)


def resolve_route(alias: str) -> ChatModel:
    return model_catalog.get(alias)


def _litellm_kwargs(
    settings: Settings,
    route: ChatModel,
    *,
    latency_sensitive: bool = False,
    thinking: bool | str | None = None,
    reasoning_budget: int = 0,
) -> dict[str, Any]:
    # No retries inside LiteLLM or the provider SDK: the fallback policy here is the only one.
    kwargs: dict[str, Any] = {"num_retries": 0, "max_retries": 0}
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
    reasoning = reasoning_body(route, thinking, budget=reasoning_budget)
    if reasoning is not None:
        kwargs.setdefault("extra_body", {})
        kwargs["extra_body"]["reasoning"] = reasoning
    return kwargs


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
    tools: list[dict[str, Any]] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    require_tool: str | None = None,
) -> AsyncIterator[str]:
    """Stream one reply, moving down ``fallback_aliases`` until a model answers.

    ``attempts`` records each model tried: which failed (before its text, or partway) and
    how fast it started. ``on_thinking`` runs when one reasons before its text; ``may_try``
    is asked before each but the last (False passes it by). ``tools`` go to a model that
    takes them, its calls land on ``tool_calls`` (a call answers too), and it must call
    ``require_tool`` when one is named.
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
    plan = ThinkingPlan(settings, thinking)

    for index, alias in enumerate(aliases):
        has_next = index < len(aliases) - 1
        if has_next and may_try is not None and not await may_try(alias):
            logger.info("Chat stream %s passed over: another turn is probing it", alias)
            continue
        # Buffer until the first non-whitespace token: a whitespace-only "success" stream
        # (a flaky provider's quirk) falls through instead of locking in an empty reply.
        pending: list[str] = []
        started = False
        # Only a kept attempt merges into `usage`; a discarded one counts as global spend.
        attempt_usage: dict[str, int] = {}
        attempt_calls: list[dict[str, Any]] = []
        think = plan.attempt(route := resolve_route(alias), has_next=has_next)
        cap = first_reply_cap(settings, alias, think.level, has_next=has_next, prompt=shape)
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
                thinking=think,
                first_content_timeout_seconds=cap,
                open_timeout_seconds=_open_wait(settings, has_next=has_next),
                attempt=attempt,
                on_thinking=on_thinking,
                tools=ToolOffer(tools, require_tool) if tools else None,
                tool_calls=attempt_calls,
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
            if started or attempt_calls:
                _keep(attempt, usage, attempt_usage, tool_calls, attempt_calls, stream_meta)
                return
            raise _answered_nothing(alias, aliases[index + 1] if has_next else None, attempt, think)
        except ModelUnavailableError as exc:
            last_error = exc
            attempt.end(failed=True, cause=exc.cause)
            # Text already shown: a fallback would join two replies into one saved reply.
            if started:
                merge_attempt_usage(usage, attempt_usage)
                raise
            if exc.cause == THOUGHT_OUT and plan.drop(aliases, route, last=not has_next):
                continue
            if has_next:
                logger.warning("Chat stream %s unavailable; trying %s", alias, aliases[index + 1])
                continue
            if _try_again(aliases, exc, attempt, settings, stream_meta):
                continue
            failed = exc.failed_alias or alias
            if stream_meta is not None:
                stream_meta["model_alias"] = failed
            raise ModelUnavailableError.for_alias(failed, cause=exc.cause) from exc
        finally:
            if not started and not attempt_calls:  # started: finalize charges it
                llm_spend.meter_discarded_attempt(alias, attempt_usage, shape.chars, attempt.cause)

    if last_error is not None:
        raise last_error


def _keep(
    attempt: StreamAttempt,
    usage: dict[str, int] | None,
    attempt_usage: dict[str, int],
    tool_calls: list[dict[str, Any]] | None,
    attempt_calls: list[dict[str, Any]],
    stream_meta: dict[str, str] | None,
) -> None:
    """The attempt answered: its usage and calls are the reply's, and its model named."""
    attempt.end(failed=False)
    merge_attempt_usage(usage, attempt_usage)
    if tool_calls is not None:
        tool_calls.extend(attempt_calls)
    if stream_meta is not None:
        stream_meta["model_alias"] = attempt.alias


# A reply the provider ended itself, at the length limit or a filter: the same request
# ends the same way.
_FINAL_FINISH_REASONS = frozenset({"length", "max_tokens", "content_filter"})
_LENGTH_FINISH_REASONS = frozenset({"length", "max_tokens"})
# A retry gives a reply that never got going a second chance, not a second full reply.
# Thinking that ran out was already tried again without (``ThinkingPlan.drop``).
_NO_RETRY_CAUSES = frozenset({REQUEST_FAULT, "rate_limit", THOUGHT_OUT})


def _try_again(
    aliases: list[str],
    exc: ModelUnavailableError,
    attempt: StreamAttempt,
    settings: Settings,
    stream_meta: dict[str, str] | None,
) -> bool:
    """The last model failed before any text: it is tried once more (appended to ``aliases``),
    as a one-model user has no backup. Not when the provider refused or rate-limited the
    request, ended the reply itself, a wait timed out past the connect timeout (a hung provider
    kept a one-model user 60 to 120 s, 2026-11-01), or it ran longer than a stalled start."""
    alias = attempt.alias
    if exc.cause in _NO_RETRY_CAUSES or (len(aliases) > 1 and aliases[-2] == alias):
        return False
    if stream_meta is not None and stream_meta.get("finish_reason") in _FINAL_FINISH_REASONS:
        return False
    elapsed = (attempt.elapsed_ms or 0) / 1000
    stalled_start = _open_wait(settings, has_next=False) + settings.chat_stream_timeout_seconds
    timed_out = exc.cause == "timeout" and elapsed > settings.chat_stream_connect_timeout_seconds
    if timed_out or elapsed > stalled_start:
        return False
    logger.warning("Chat stream %s answered nothing; trying it once more", alias)
    aliases.append(alias)
    return True


def _open_wait(settings: Settings, *, has_next: bool) -> float:
    """How long one attempt waits for its stream to open: short, so the next model can take
    over; the last model has none (a slow opening is a slow reply), so it gets the idle one."""
    if has_next:
        return settings.chat_stream_connect_timeout_seconds
    return max(settings.chat_stream_connect_timeout_seconds, settings.chat_stream_timeout_seconds)


def _answered_nothing(
    alias: str, fallback: str | None, attempt: StreamAttempt, think: AttemptThinking
) -> ModelUnavailableError:
    """No text came. When the attempt thought and the provider ended it at the length limit,
    its thinking used the reply's tokens: the next attempt goes without (``THOUGHT_OUT``)."""
    thought_out = think.budget > 0 and attempt.finish_reason in _LENGTH_FINISH_REASONS
    logger.warning(
        "Chat stream %s returned no content%s%s",
        alias,
        " (thinking used its tokens)" if thought_out else "",
        f"; retrying with fallback {fallback}" if fallback else "",
    )
    return ModelUnavailableError.for_alias(alias, cause=THOUGHT_OUT if thought_out else "empty")


def _call_kwargs(
    settings: Settings,
    route: ChatModel,
    thinking: AttemptThinking | bool | str | None,
    offer: ToolOffer | None,
) -> tuple[dict[str, Any], StreamedToolCalls | None]:
    """The streamed call's provider arguments, and where its tool calls fold: None when
    the model was offered none (one that takes no tools gets none). A bare level sends
    no thinking budget."""
    thinking = as_attempt(thinking)
    kwargs = _litellm_kwargs(
        settings,
        route,
        latency_sensitive=True,
        thinking=thinking.level,
        reasoning_budget=thinking.budget,
    )
    calls = StreamedToolCalls() if offer and offer.tools and route.supports_tools else None
    if offer is not None and calls is not None:
        kwargs.update(tools=offer.tools, tool_choice=offer.choice())
    return kwargs, calls


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
    # The chunk carried a tool call.
    called: bool = False
    # The provider's finish_reason on this chunk, if any.
    finish: str | None = None
    # How much reasoning text the chunk carried.
    reasoned: int = 0


def _read_chunk(
    chunk: Any,
    *,
    usage: dict[str, int] | None,
    stream_meta: dict[str, str] | None,
    stripper: ThinkStripper,
    calls: StreamedToolCalls | None = None,
    text_calls: TextToolCalls | None = None,
) -> _ChunkRead:
    """What one provider chunk shows. ``calls`` is None when the request offered no
    tools: a stray call is not read. ``text_calls`` holds a call written as text."""
    apply_usage(usage, chunk)
    choices = getattr(chunk, "choices", None) or []
    if not choices:
        return _ChunkRead("", thinking=False, delta=False)
    reason = getattr(choices[0], "finish_reason", None)
    finish = str(reason) if reason else None
    if finish and stream_meta is not None:
        stream_meta["finish_reason"] = finish
    delta = getattr(choices[0], "delta", None)
    reasoning = reasoning_delta(delta)
    if reasoning:
        # Text after reasoning on its own channel is most likely the answer.
        stripper.reasoning_streamed()
    content = getattr(delta, "content", None) or "" if delta is not None else ""
    text = stripper.feed(content) if content else ""
    if text and text_calls is not None:
        found_before = text_calls.found
        text = text_calls.feed(text)
        called_in_text = text_calls.found and not found_before
    else:
        called_in_text = False
    called = calls is not None and calls.fold(getattr(delta, "tool_calls", None))
    called = called or (called_in_text and calls is not None)
    delta_seen = reasoning or bool(content) or called
    reasoned = len(getattr(delta, "reasoning_content", "")) if reasoning else 0
    thinking = reasoning or stripper.holding_thought
    return _ChunkRead(text, thinking, delta_seen, called, finish, reasoned)


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
    open_timeout_seconds: float | None = None,
    thinking: AttemptThinking | bool | str | None = None,
    attempt: StreamAttempt | None = None,
    on_thinking: Callable[[], Awaitable[None]] | None = None,
    tools: ToolOffer | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
) -> AsyncIterator[str]:
    """One model's stream. ``first_content_timeout_seconds`` caps the wait for its
    first text or reasoning (``stream_signals.first_reply_cap``); a tool call ends
    it too. ``open_timeout_seconds`` (default the connect timeout) bounds the open.
    A ``thinking`` attempt's budget adds to ``max_tokens``, and its ceiling bounds the
    wait for its first text (``stream_thinking``)."""
    open_seconds = open_timeout_seconds or settings.chat_stream_connect_timeout_seconds
    route = resolve_route(model_alias)
    think = as_attempt(thinking)
    answer_by = think.answer_by()
    kwargs, calls = _call_kwargs(settings, route, think, tools)
    stripper = ThinkStripper(lead_hold=STRAY_THINK_LEAD_HOLD if route.stray_think_guard else 0)
    text_calls = TextToolCalls(calls)
    # Signature kept so WS/SSE callers stay unchanged; CoT is not forwarded.
    _ = on_reasoning
    watch = FirstReplyWatch(first_content_timeout_seconds)
    response = None
    try:
        # A first-reply cap also bounds the wait for the stream to open.
        async with asyncio.timeout(watch.bound(open_seconds)):
            response = await acompletion(
                model=route.model,
                messages=with_cache_breakpoint(
                    messages, route, enabled=settings.prompt_cache_breakpoints_enabled
                ),
                stream=True,
                max_tokens=max_tokens + think.budget,
                stream_options={"include_usage": True},
                **kwargs,
            )
        clock = StreamClock(settings, watch, answer_by, think)
        stream_iter = response.__aiter__()

        async def _next_chunk() -> Any | None:
            try:
                return await stream_iter.__anext__()
            except StopAsyncIteration:
                return None

        while True:
            if (stop := clock.stop_reason()) is not None:
                raise _cut_off(model_alias, stop, clock, usage)
            try:
                chunk = await asyncio.wait_for(_next_chunk(), timeout=clock.next_wait())
            except TimeoutError as exc:
                stop = clock.stop_reason() or clock.idle_reason()
                raise _cut_off(model_alias, stop, clock, usage) from exc
            if chunk is None:
                break
            read = _read_chunk(
                chunk,
                usage=usage,
                stream_meta=stream_meta,
                stripper=stripper,
                calls=calls,
                text_calls=text_calls,
            )
            if attempt is not None:
                attempt.saw(delta=read.delta, finish=read.finish)
            clock.reasoned(read.reasoned)
            watch.shown_text = watch.shown_text or read.called  # a call begins the reply
            if watch.saw(text=read.text, thinking=read.thinking) and on_thinking is not None:
                await _tell_thinking(on_thinking, model_alias)
            if read.text:
                yield read.text
        tail = text_calls.feed(stripper.flush()) + text_calls.flush()
        if tail:
            yield tail
        if tool_calls is not None and calls is not None:
            tool_calls.extend(calls.calls())
    except TimeoutError as exc:
        # Only the wait for the stream to open raises one here.
        raise _did_not_open(model_alias, watch.expired(), open_seconds) from exc
    except ModelUnavailableError:
        raise
    except Exception as exc:
        logger.exception("LiteLLM streaming failed for alias=%s", model_alias)
        raise ModelUnavailableError.for_alias(model_alias, cause=provider_fault(exc)) from exc
    finally:
        await _close_response(response)


async def _close_response(response: Any) -> None:
    """Close a provider stream. A stop cancels the reply's task: awaiting the socket close
    then either raises again at once or waits out the provider, and the partial reply
    never gets saved, so it closes in the background."""
    close = getattr(response, "aclose", None)
    if close is None:
        return
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        create_background_task(_close_provider_stream(close), name="close_provider_stream")
    else:
        with suppress(Exception):
            await close()


def _did_not_open(model_alias: str, cap: str | None, open_seconds: float) -> ModelUnavailableError:
    """The stream never opened: within the first-reply ``cap``, when one ran out."""
    reason = cap or f"connect {open_seconds}s"
    logger.warning("LiteLLM stream for alias=%s did not open: %s", model_alias, reason)
    cause = "cap" if cap is not None else "timeout"
    return ModelUnavailableError.for_alias(model_alias, cause=cause)


def _cut_off(
    model_alias: str, stop: tuple[str, str], clock: StreamClock, usage: dict[str, int] | None
) -> ModelUnavailableError:
    """We ended the stream: what it reasoned counts toward spend, as the provider billed it."""
    clock.meter_cut(usage)
    return _gave_up(model_alias, *stop)


def _gave_up(model_alias: str, ran_out: str, cause: str) -> ModelUnavailableError:
    logger.warning("LiteLLM stream for alias=%s gave up: %s", model_alias, ran_out)
    return ModelUnavailableError.for_alias(model_alias, cause=cause)
