import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Self

# Re-exported: the completion gateways call the provider through this module.
from litellm import acompletion as acompletion

from app.core.background_tasks import create_background_task
from app.core.config import Settings
from app.gateways import mock_llm
from app.gateways.reasoning import reasoning_body

# The completion kinds split out of this module are part of its public surface
# (callers use ``litellm_gateway.complete_structured`` and friends). They make
# their provider calls through this module (``acompletion``, ``resolve_route``,
# ``_litellm_kwargs``), importing it at call time: at load it would be a cycle.
from app.gateways.stream_tool_calls import StreamedToolCalls
from app.gateways.structured_completion import complete_structured as complete_structured
from app.gateways.text_completion import complete_text as complete_text
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
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.failed_alias = failed_alias

    @classmethod
    def for_alias(cls, alias: str, *, code: str = "model_unavailable") -> Self:
        """The user-facing "model isn't responding" error for one failed alias."""
        return cls(_CHAT_MODEL_UNAVAILABLE_MSG, code=code, failed_alias=alias)


_CHAT_MODEL_UNAVAILABLE_MSG = (
    "That model isn't responding right now. Try again — or pick a different model."
)


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
        raise ModelUnavailableError.for_alias(route.id)
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


@dataclass(frozen=True, slots=True)
class StreamAttempt:
    """One alias the stream tried: did it answer, and how long until its first content.

    The model-health sample used to follow only the alias that produced content, so a
    primary that failed before a fallback answered was never recorded, a failure after
    the first token counted as a success, and the whole reply's time read as latency.
    """

    alias: str
    ok: bool
    first_content_ms: float


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
    tools: list[dict[str, Any]] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
) -> AsyncIterator[str]:
    """The reply from the first alias that answers. ``tools`` go to an alias that takes
    them, and the calls its reply makes land on ``tool_calls``: a call answers too."""
    if mock_llm.should_mock_llm(settings):
        logger.info("Using mock LLM stream for alias=%s", model_alias)
        if stream_meta is not None:
            stream_meta["model_alias"] = model_alias
        async for token in mock_llm.mock_stream(messages=messages):
            yield token
        return

    aliases = [model_alias, *(fallback_aliases or [])]
    last_error: ModelUnavailableError | None = None

    for index, alias in enumerate(aliases):
        # Buffer until the first non-whitespace token so whitespace-only
        # "success" streams (common flaky provider quirk) still fall through
        # to the next alias instead of locking in an empty reply.
        pending: list[str] = []
        started = False
        # Discarded attempts must not add provider tokens onto the caller's
        # daily quota. Tool-loop usage already lives on `usage`; only merge
        # the attempt that actually produced content.
        attempt_usage: dict[str, int] = {}
        attempt_calls: list[dict[str, Any]] = []
        attempt_started = time.perf_counter()
        first_content_ms: float | None = None
        # "ok" answered, "failed" did not, "closed" was stopped before its first content.
        result = "failed"
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
                first_content_timeout_seconds=_first_content_timeout(
                    settings, alias, last=index == len(aliases) - 1
                ),
                tools=tools,
                tool_calls=attempt_calls,
            ):
                if not started:
                    pending.append(token)
                    if not "".join(pending).strip():
                        continue
                    started = True
                    first_content_ms = (time.perf_counter() - attempt_started) * 1000
                    for piece in pending:
                        yield piece
                    pending.clear()
                    continue
                yield token
            if started or attempt_calls:
                result = "ok"
                _merge_attempt_usage(usage, attempt_usage)
                if tool_calls is not None:
                    tool_calls.extend(attempt_calls)
                if stream_meta is not None:
                    stream_meta["model_alias"] = alias
                return
            logger.warning(
                "Chat stream %s returned no content%s",
                alias,
                f"; retrying with fallback {aliases[index + 1]}"
                if index < len(aliases) - 1
                else "",
            )
            raise ModelUnavailableError.for_alias(alias)
        except ModelUnavailableError as exc:
            last_error = exc
            # Mid-stream failure: client already has partial tokens — falling
            # back would concatenate partial + full into one persisted reply.
            if started:
                _merge_attempt_usage(usage, attempt_usage)
                raise
            if index < len(aliases) - 1:
                logger.warning(
                    "Chat stream %s unavailable; retrying with fallback %s",
                    alias,
                    aliases[index + 1],
                )
                continue
            failed = exc.failed_alias or alias
            if stream_meta is not None:
                stream_meta["model_alias"] = failed
            raise ModelUnavailableError.for_alias(failed) from exc
        except (GeneratorExit, asyncio.CancelledError):
            # The caller stopped reading (a user stop, a closed socket): an alias that
            # had answered counts as answering; one stopped before its first content
            # says nothing about the provider.
            result = "ok" if started else "closed"
            raise
        finally:
            if result != "closed":
                _note_attempt(attempts, alias, result == "ok", attempt_started, first_content_ms)

    if last_error is not None:
        raise last_error


def _first_content_timeout(settings: Settings, alias: str, *, last: bool) -> float | None:
    """A thinking alias with a fallback after it must show content in time, or yield."""
    if last or not model_catalog.is_reasoning_alias(alias):
        return None
    return settings.chat_stream_first_content_timeout_seconds


def _note_attempt(
    attempts: list[StreamAttempt] | None,
    alias: str,
    ok: bool,
    started_at: float,
    first_content_ms: float | None,
) -> None:
    """Record one alias's attempt, timed to its first content (or to its end)."""
    if attempts is None:
        return
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    attempts.append(
        StreamAttempt(
            alias=alias,
            ok=ok,
            first_content_ms=first_content_ms if first_content_ms is not None else elapsed_ms,
        )
    )


_PROVIDER_CLOSE_TIMEOUT_SECONDS = 2.0


async def _close_provider_stream(close: Callable[[], Awaitable[None]]) -> None:
    """Close the provider socket after a stop without blocking the caller."""
    with suppress(Exception, asyncio.CancelledError):
        await asyncio.wait_for(close(), _PROVIDER_CLOSE_TIMEOUT_SECONDS)


async def _close_response(response: Any) -> None:
    close = getattr(response, "aclose", None)
    if close is None:
        return
    # A stop cancels this task. Awaiting the socket close here either
    # raises again immediately or waits out the provider, and the
    # partial reply never gets saved. Close in the background.
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        create_background_task(_close_provider_stream(close), name="close_provider_stream")
    else:
        with suppress(Exception):
            await close()


def _read_chunk(
    chunk: Any,
    usage: dict[str, int] | None,
    stream_meta: dict[str, str] | None,
    calls: StreamedToolCalls | None,
) -> tuple[str, bool]:
    """A chunk's text, and whether it carried a tool call; its usage and finish noted.

    ``calls`` is None when the request offered no tools: a stray call is not read."""
    _apply_usage(usage, chunk)
    choices = getattr(chunk, "choices", None) or []
    if not choices:
        return "", False
    reason = getattr(choices[0], "finish_reason", None)
    if reason and stream_meta is not None:
        stream_meta["finish_reason"] = str(reason)
    delta = getattr(choices[0], "delta", None)
    if delta is None:
        return "", False
    called = calls is not None and calls.fold(getattr(delta, "tool_calls", None))
    return getattr(delta, "content", None) or "", called


def _no_content_in_time(alias: str, seconds: float | None) -> ModelUnavailableError:
    logger.warning(
        "LiteLLM stream produced no visible content for alias=%s within %ss", alias, seconds
    )
    return ModelUnavailableError.for_alias(alias)


def _over_wall_clock(alias: str, max_seconds: float) -> ModelUnavailableError:
    logger.warning("LiteLLM stream wall-clock timed out for alias=%s (max=%ss)", alias, max_seconds)
    return ModelUnavailableError.for_alias(alias)


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
    tools: list[dict[str, Any]] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
) -> AsyncIterator[str]:
    route = resolve_route(model_alias)
    kwargs = _litellm_kwargs(settings, route, latency_sensitive=True, thinking=thinking)
    calls = StreamedToolCalls() if tools and route.supports_tools else None
    if calls is not None:
        kwargs.update(tools=tools, tool_choice="auto")
    stripper = ThinkStripper(lead_hold=STRAY_THINK_LEAD_HOLD if route.stray_think_guard else 0)
    # Signature kept so WS/SSE callers stay unchanged; CoT is not forwarded.
    _ = on_reasoning
    response = None
    first_content_deadline = (
        time.monotonic() + max(0.1, first_content_timeout_seconds)
        if first_content_timeout_seconds is not None
        else None
    )
    # A tool call counts as content: the model chose to call instead of writing.
    visible_content_started = False
    try:
        async with asyncio.timeout(settings.chat_stream_connect_timeout_seconds):
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

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _over_wall_clock(model_alias, max_seconds)
            first_content_remaining: float | None = None
            if not visible_content_started and first_content_deadline is not None:
                first_content_remaining = first_content_deadline - time.monotonic()
                if first_content_remaining <= 0:
                    raise _no_content_in_time(model_alias, first_content_timeout_seconds)
            read_timeout = min(idle_seconds, remaining)
            if first_content_remaining is not None:
                read_timeout = min(read_timeout, first_content_remaining)
            try:
                chunk = await asyncio.wait_for(
                    _next_chunk(),
                    timeout=read_timeout,
                )
            except TimeoutError as exc:
                now = time.monotonic()
                if (
                    not visible_content_started
                    and first_content_deadline is not None
                    and now >= first_content_deadline
                ):
                    raise _no_content_in_time(model_alias, first_content_timeout_seconds) from exc
                if now >= deadline:
                    raise _over_wall_clock(model_alias, max_seconds) from exc
                logger.warning(
                    "LiteLLM stream idle timed out for alias=%s (idle=%ss)",
                    model_alias,
                    idle_seconds,
                )
                raise ModelUnavailableError.for_alias(model_alias) from exc
            if chunk is None:
                break
            content, called = _read_chunk(chunk, usage, stream_meta, calls)
            visible_content_started = visible_content_started or called
            if content:
                cleaned = stripper.feed(content)
                if cleaned:
                    if cleaned.strip():
                        visible_content_started = True
                    yield cleaned
        tail = stripper.flush()
        if tail:
            if tail.strip():
                visible_content_started = True
            yield tail
        if tool_calls is not None and calls is not None:
            tool_calls.extend(calls.calls())
    except TimeoutError as exc:
        logger.warning(
            "LiteLLM stream timed out for alias=%s (connect=%ss idle=%ss)",
            model_alias,
            settings.chat_stream_connect_timeout_seconds,
            settings.chat_stream_timeout_seconds,
        )
        raise ModelUnavailableError.for_alias(model_alias) from exc
    except ModelUnavailableError:
        raise
    except Exception as exc:
        logger.exception("LiteLLM streaming failed for alias=%s", model_alias)
        raise ModelUnavailableError.for_alias(model_alias) from exc
    finally:
        await _close_response(response)
