import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from typing import Any, cast, get_args, get_origin

from litellm import acompletion
from pydantic import BaseModel

from app.core.config import Settings
from app.gateways import mock_llm
from app.models.schemas import (
    MemorySectionItem,
    MemorySectionUpdateResult,
)
from app.services import model_catalog
from app.services.model_catalog import ChatModel

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


_CHAT_MODEL_UNAVAILABLE_MSG = (
    "That model isn't responding right now. Try again — or pick a different model."
)


# DeepSeek-R1 (smart-chat) emits ... reasoning blocks inline in the
# `content` stream (and in a separate `reasoning_content` delta field). We strip
# both so users never see raw chain-of-thought and reasoning tokens don't count
# against the displayed reply.
_THINK_OPEN = "\x3credacted_thinking\x3e"
_THINK_CLOSE = "\x3c/redacted_thinking\x3e"
# Safety cap: if an opened think block never closes, drop the buffer rather than
# swallow the rest of the reply.
_THINK_MAX_OPEN_BUFFER = 4096


class _ThinkStripper:
    """Stateful filter that removes redacted-thinking blocks from a token stream.

    Handles open/close tags split across chunks. Emits text outside think blocks
    unchanged; discards text inside. An unclosed think block is dropped on flush.
    """

    def __init__(self) -> None:
        self._buf = ""
        self._in_think = False

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out: list[str] = []
        while True:
            if self._in_think:
                idx = self._buf.find(_THINK_CLOSE)
                if idx == -1:
                    if len(self._buf) > _THINK_MAX_OPEN_BUFFER:
                        # Model forgot to close — give up on this block.
                        self._buf = ""
                        self._in_think = False
                    break
                self._buf = self._buf[idx + len(_THINK_CLOSE) :]
                self._in_think = False
            else:
                idx = self._buf.find(_THINK_OPEN)
                if idx == -1:
                    # Hold back enough trailing chars that a split open tag can't leak.
                    safe = len(self._buf) - (len(_THINK_OPEN) - 1)
                    if safe > 0:
                        out.append(self._buf[:safe])
                        self._buf = self._buf[safe:]
                    break
                out.append(self._buf[:idx])
                self._buf = self._buf[idx + len(_THINK_OPEN) :]
                self._in_think = True
        return "".join(out)

    def flush(self) -> str:
        if self._in_think:
            self._buf = ""
            self._in_think = False
            return ""
        out = self._buf
        self._buf = ""
        return out


def resolve_model(alias: str) -> str:
    return model_catalog.get(alias).model


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
            kwargs = _litellm_kwargs(settings, route)
            params: dict[str, Any] = dict(
                model=route.model, messages=messages, max_tokens=max_tokens, **kwargs
            )
            if response_format is not None:
                params["response_format"] = response_format
            async with asyncio.timeout(settings.background_llm_timeout_seconds):
                return await acompletion(**params)
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


def _litellm_kwargs(settings: Settings, route: ChatModel) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    api_key = getattr(settings, route.api_key_field, "")
    if not api_key:
        raise ModelUnavailableError(
            _CHAT_MODEL_UNAVAILABLE_MSG,
            failed_alias=route.id,
        )
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
    return kwargs


def _apply_usage(usage: dict[str, int] | None, chunk: Any) -> None:
    if usage is None:
        return
    chunk_usage = getattr(chunk, "usage", None)
    if not chunk_usage:
        return
    prompt = getattr(chunk_usage, "prompt_tokens", None)
    completion = getattr(chunk_usage, "completion_tokens", None)
    if prompt is not None:
        usage["input"] = int(prompt)
    if completion is not None:
        usage["output"] = int(completion)


def _apply_usage_from_response(usage: dict[str, int] | None, response: Any) -> None:
    if usage is None:
        return
    resp_usage = getattr(response, "usage", None)
    if not resp_usage:
        return
    prompt = getattr(resp_usage, "prompt_tokens", None)
    completion = getattr(resp_usage, "completion_tokens", None)
    if prompt is not None:
        usage["input"] = usage.get("input", 0) + int(prompt)
    if completion is not None:
        usage["output"] = usage.get("output", 0) + int(completion)


def _tool_calls_to_jsonable(tool_calls: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for call in tool_calls:
        if isinstance(call, dict):
            out.append(call)
            continue
        fn = getattr(call, "function", None)
        out.append(
            {
                "id": getattr(call, "id", None) or "",
                "type": getattr(call, "type", None) or "function",
                "function": {
                    "name": getattr(fn, "name", None) or "",
                    "arguments": getattr(fn, "arguments", None) or "{}",
                },
            }
        )
    return out


async def complete_with_tools(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    usage: dict[str, int] | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Non-streaming completion that may return ``tool_calls``.

    Returns a plain dict: ``{content, tool_calls}`` where ``tool_calls`` is a
    list of OpenAI-shaped tool call dicts (empty when the model answers directly).
    """
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_complete_with_tools(messages=messages, tools=tools)

    route = resolve_route(model_alias)
    kwargs = _litellm_kwargs(settings, route)
    try:
        async with asyncio.timeout(timeout_seconds):
            response = await acompletion(
                model=route.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=False,
                **kwargs,
            )
    except TimeoutError as exc:
        raise ModelUnavailableError(
            _CHAT_MODEL_UNAVAILABLE_MSG,
            failed_alias=model_alias,
        ) from exc
    except Exception as exc:
        logger.warning("complete_with_tools failed alias=%s: %s", model_alias, exc)
        raise ModelUnavailableError(
            _CHAT_MODEL_UNAVAILABLE_MSG,
            failed_alias=model_alias,
        ) from exc

    _apply_usage_from_response(usage, response)
    choices = getattr(response, "choices", None) or []
    if not choices:
        return {"content": None, "tool_calls": []}
    message = choices[0].message
    raw_calls = getattr(message, "tool_calls", None) or []
    return {
        "content": getattr(message, "content", None),
        "tool_calls": _tool_calls_to_jsonable(list(raw_calls)),
    }


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
) -> AsyncIterator[str]:
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
        try:
            # Buffer until the first non-whitespace token so whitespace-only
            # "success" streams (common flaky provider quirk) still fall through
            # to the next alias instead of locking in an empty reply.
            pending: list[str] = []
            started = False
            async for token in _stream_chat_once(
                settings=settings,
                model_alias=alias,
                messages=messages,
                max_tokens=max_tokens,
                usage=usage,
                on_reasoning=on_reasoning,
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
            raise ModelUnavailableError(
                _CHAT_MODEL_UNAVAILABLE_MSG,
                failed_alias=alias,
            )
        except ModelUnavailableError as exc:
            last_error = exc
            if index < len(aliases) - 1:
                logger.warning(
                    "Chat stream %s unavailable; retrying with fallback %s",
                    alias,
                    aliases[index + 1],
                )
                continue
            raise ModelUnavailableError(
                _CHAT_MODEL_UNAVAILABLE_MSG,
                failed_alias=model_alias,
            ) from exc

    if last_error is not None:
        raise last_error


async def _stream_chat_once(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    usage: dict[str, int] | None = None,
    on_reasoning: Callable[[str], Awaitable[None]] | None = None,
) -> AsyncIterator[str]:
    route = resolve_route(model_alias)
    kwargs = _litellm_kwargs(settings, route)
    stripper = _ThinkStripper()
    response = None
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
        # Idle timeout per chunk — not a wall-clock cap on the whole reply.
        idle_seconds = settings.chat_stream_timeout_seconds
        stream_iter = response.__aiter__()

        async def _next_chunk() -> Any | None:
            try:
                return await stream_iter.__anext__()
            except StopAsyncIteration:
                return None

        while True:
            try:
                chunk = await asyncio.wait_for(_next_chunk(), timeout=idle_seconds)
            except TimeoutError as exc:
                logger.warning(
                    "LiteLLM stream idle timed out for alias=%s (idle=%ss)",
                    model_alias,
                    idle_seconds,
                )
                raise ModelUnavailableError(
                    _CHAT_MODEL_UNAVAILABLE_MSG,
                    failed_alias=model_alias,
                ) from exc
            if chunk is None:
                break
            _apply_usage(usage, chunk)
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = choices[0].delta
            reasoning = getattr(delta, "reasoning_content", None) or ""
            if reasoning and on_reasoning is not None:
                await on_reasoning(reasoning)
            content = getattr(delta, "content", None) or ""
            if content:
                cleaned = stripper.feed(content)
                if cleaned:
                    yield cleaned
        tail = stripper.flush()
        if tail:
            yield tail
    except TimeoutError as exc:
        logger.warning(
            "LiteLLM stream timed out for alias=%s (connect=%ss idle=%ss)",
            model_alias,
            settings.chat_stream_connect_timeout_seconds,
            settings.chat_stream_timeout_seconds,
        )
        raise ModelUnavailableError(
            _CHAT_MODEL_UNAVAILABLE_MSG,
            failed_alias=model_alias,
        ) from exc
    except ModelUnavailableError:
        raise
    except Exception as exc:
        logger.exception("LiteLLM streaming failed for alias=%s", model_alias)
        raise ModelUnavailableError(
            _CHAT_MODEL_UNAVAILABLE_MSG,
            failed_alias=model_alias,
        ) from exc
    finally:
        close = getattr(response, "aclose", None)
        if close is not None:
            with suppress(Exception):
                await close()


def _list_field_name(schema: type[BaseModel]) -> str | None:
    """Name of the schema's first list-typed field, if any (for bare-list wrapping)."""
    for name, field in schema.model_fields.items():
        ann = field.annotation
        if get_origin(ann) is list or any(get_origin(a) is list for a in get_args(ann)):
            return name
    return None


def _fallback_alias(settings: Settings, primary: str) -> str | None:
    """The alias to retry against when the primary background model is down.

    Returns None when mock mode is on, when no fallback is configured, or when
    the primary IS the fallback (don't retry against itself).
    """
    if mock_llm.should_mock_llm(settings):
        return None
    fb = settings.memory_fallback_model_alias.strip()
    if not fb or fb == primary:
        return None
    return fb


async def _complete_structured_once[T: BaseModel](
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, str]],
    schema: type[T],
    max_tokens: int,
) -> T | None:
    """One structured attempt. Raises on provider outage; returns None on bad output."""
    route = resolve_route(model_alias)
    kwargs = _litellm_kwargs(settings, route)  # ModelUnavailableError if no key
    async with asyncio.timeout(settings.background_llm_timeout_seconds):
        response = await acompletion(  # provider/network errors propagate for retry
            model=route.model,
            messages=messages,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            **kwargs,
        )
    raw = (response.choices[0].message.content or "{}").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError:
        logger.debug("Structured completion: bad JSON for %s", model_alias)
        return None  # call succeeded but output was unparseable — retry won't help
    # Models occasionally return a bare array for a single-list schema; wrap it.
    if isinstance(data, list):
        list_field = _list_field_name(schema)
        if list_field is None:
            logger.debug(
                "Structured completion: bare list returned for %s with no list field",
                schema.__name__,
            )
            return None
        data = {list_field: data}
    try:
        return schema.model_validate(data)
    except Exception:
        if schema is MemorySectionUpdateResult and isinstance(data, dict):
            partial = _parse_memory_sections_partial(data)
            if partial is not None:
                return cast(T, partial)
        logger.debug("Structured completion: validation failed for %s", model_alias)
        return None


def _parse_memory_sections_partial(data: dict[str, object]) -> MemorySectionUpdateResult | None:
    raw_sections = data.get("sections")
    if not isinstance(raw_sections, list):
        return None
    valid: list[MemorySectionItem] = []
    for item in raw_sections:
        if not isinstance(item, dict):
            continue
        try:
            valid.append(MemorySectionItem.model_validate(item))
        except Exception:
            logger.debug("Skipping invalid memory section item", exc_info=True)
    if not valid:
        return None
    return MemorySectionUpdateResult(sections=valid)


async def complete_structured[T: BaseModel](
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, str]],
    schema: type[T],
    max_tokens: int = 256,
) -> T | None:
    if mock_llm.should_mock_llm(settings):
        return None

    fallback = _fallback_alias(settings, model_alias)
    try:
        result = await _complete_structured_once(
            settings=settings,
            model_alias=model_alias,
            messages=messages,
            schema=schema,
            max_tokens=max_tokens,
        )
        if result is not None:
            return result
        return None  # output parse/validation failed — retrying won't help
    except Exception:
        if fallback is None:
            logger.exception("Background LLM %s failed and no fallback configured", model_alias)
            return None
        logger.warning(
            "Background LLM %s unavailable; retrying with fallback %s", model_alias, fallback
        )
        try:
            return await _complete_structured_once(
                settings=settings,
                model_alias=fallback,
                messages=messages,
                schema=schema,
                max_tokens=max_tokens,
            )
        except Exception:
            logger.exception("Background LLM fallback %s also failed", fallback)
            return None


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
