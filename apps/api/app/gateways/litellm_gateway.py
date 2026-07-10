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
    ProjectActionItem,
    ProjectExtractionResult,
    TodoExtractionResult,
    WebSearchClassification,
)
from app.services import model_catalog
from app.services.chat_titles import normalize_chat_title
from app.services.context_window import SUMMARY_SYSTEM_PROMPT, cap_summary
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
    "That model isn't responding right now. Pick a different model and try again."
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
            async for token in _stream_chat_once(
                settings=settings,
                model_alias=alias,
                messages=messages,
                max_tokens=max_tokens,
                usage=usage,
                on_reasoning=on_reasoning,
            ):
                yield token
            if stream_meta is not None:
                stream_meta["model_alias"] = alias
            return
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


async def classify_web_search_need(
    settings: Settings,
    user_message: str,
    *,
    prior_user_messages: list[str] | None = None,
) -> WebSearchClassification | None:
    """Cheap structured gate for ambiguous turns — regex handles obvious cases."""
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_web_search_classification(
            user_message,
            prior_user_messages=prior_user_messages,
        )

    context_lines: list[str] = []
    if prior_user_messages:
        for msg in prior_user_messages[-2:]:
            stripped = msg.strip()
            if stripped:
                context_lines.append(f"- {stripped[:200]}")
    context_block = "\n".join(context_lines) if context_lines else "(none)"

    messages = [
        {
            "role": "system",
            "content": (
                "You decide if a personal chat assistant should run a live web search "
                "before answering. Return ONLY JSON: "
                '{"needs_search": true|false, "query": "optional concise search query"}.\n\n'
                "When needs_search is true, set query to a short web search string "
                "(5-12 words) that would find the answer — not the user's full message.\n\n"
                "Search YES for: current events, live scores, prices, people/org facts "
                "that change over time, product release info, weather, local venues, "
                "anything needing up-to-date data from the internet.\n\n"
                "Search NO for: coding help, writing/editing, math, trivia the model "
                "knows, personal planning/todos, app settings, translating, summarizing "
                "pasted text, opinions, creative writing, general explanations of "
                "stable concepts.\n\n"
                "When unsure, prefer false unless the answer likely changed in the last year."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Recent user messages:\n{context_block}\n\n"
                f"Latest message:\n{user_message.strip()[:500]}"
            ),
        },
    ]
    return await complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=WebSearchClassification,
        max_tokens=64,
    )


async def generate_title(
    settings: Settings,
    user_message: str,
    assistant_message: str,
) -> str | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_title(user_message)

    messages = [
        {
            "role": "system",
            "content": (
                "You title conversations in 3-6 words. Reply with ONLY the title. "
                "Never use generic labels like 'New chat', 'Untitled', or 'Chat'."
            ),
        },
        {"role": "user", "content": user_message[:300]},
        {"role": "assistant", "content": assistant_message[:300]},
        {"role": "user", "content": "Title?"},
    ]
    response = await _acompletion_with_fallback(
        settings, "title-model", messages=messages, max_tokens=20
    )
    if response is None:
        return None
    try:
        raw = (response.choices[0].message.content or "").strip().strip('"').strip("'")
        return normalize_chat_title(raw)
    except Exception:
        logger.exception("Title generation failed to parse response")
        return None


async def revise_memory_sections(
    settings: Settings,
    transcript: str,
    *,
    existing_sections: dict[str, str] | None = None,
) -> MemorySectionUpdateResult | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_memory_sections(transcript, existing_sections or {})

    import json

    existing = existing_sections or {}
    existing_block = json.dumps(existing, ensure_ascii=False) if existing else "{}"

    messages = [
        {
            "role": "system",
            "content": (
                "You maintain long-term memory about the user as up to five section summaries. "
                "Return ONLY JSON (no markdown): "
                '{"sections": [{"type": "profile|preference|project|fact|focus", '
                '"summary": "2-4 sentence paragraph in third person", "confidence": 0.0-1.0}]}. '
                "Section meanings:\n"
                "- profile: name, identity, job, employer, location\n"
                "- preference: how they like to learn, communicate, or use the app\n"
                "- project: active personal projects (not the separate Projects feature)\n"
                "- fact: stable misc facts\n"
                "- focus: current priorities\n\n"
                "Rules:\n"
                "- Return ONLY sections that changed or are new this turn.\n"
                "- Each summary is ONE merged paragraph — never a bullet list.\n"
                "- Rewrite the full section when updating; merge duplicates; drop stale facts.\n"
                "- Skip small talk. Return empty sections array if nothing changed."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Existing section summaries JSON:\n{existing_block}\n\n"
                f"New conversation:\n{transcript}"
            ),
        },
    ]
    return await complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=MemorySectionUpdateResult,
        max_tokens=1024,
    )


async def merge_memory_section(
    settings: Settings,
    *,
    section_type: str,
    prior_text: str,
) -> MemorySectionItem | None:
    """Merge duplicate facts in one section without dropping distinct facts."""
    clean = prior_text.strip()
    if not clean:
        return None
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_merge_memory_section(section_type, clean)

    import json

    messages = [
        {
            "role": "system",
            "content": (
                "You merge long-term memory facts for a personal AI assistant. "
                "Return ONLY JSON (no markdown): "
                '{"type": "profile|preference|project|fact|focus", '
                '"summary": "2-6 sentence paragraph in third person", "confidence": 0.0-1.0}. '
                "Rules:\n"
                "- Preserve EVERY distinct fact from the draft — do not drop names, orgs, "
                "emails, numbers, or preferences.\n"
                "- Deduplicate near-duplicate sentences; merge contradictions sensibly.\n"
                "- Output ONE paragraph (not a bullet list).\n"
                "- Do not invent facts not supported by the draft.\n"
                f"- The section type must remain `{section_type}`."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Section type: {section_type}\n"
                f"Draft facts JSON:\n{json.dumps({'text': clean}, ensure_ascii=False)}"
            ),
        },
    ]
    return await complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=MemorySectionItem,
        max_tokens=1024,
    )


async def rewrite_memory_sections(
    settings: Settings,
    sections: dict[str, str],
) -> MemorySectionUpdateResult | None:
    """Rewrite bloated or duplicate section drafts into concise paragraphs.

    Prefer :func:`merge_memory_section` for production consolidation (merge-not-replace).
    """
    if not sections:
        return None
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_rewrite_memory_sections(sections)

    import json

    messages = [
        {
            "role": "system",
            "content": (
                "You clean up long-term memory section drafts for a personal AI assistant. "
                "Return ONLY JSON (no markdown): "
                '{"sections": [{"type": "profile|preference|project|fact|focus", '
                '"summary": "2-4 sentence paragraph in third person", "confidence": 0.0-1.0}]}. '
                "Section meanings:\n"
                "- profile: name, identity, job, employer, location\n"
                "- preference: how they like to learn, communicate, or use the app\n"
                "- project: active personal projects\n"
                "- fact: stable misc facts\n"
                "- focus: current priorities\n\n"
                "Rules:\n"
                "- Return EVERY input section, rewritten.\n"
                "- Each summary is ONE merged paragraph — never a bullet list.\n"
                "- Remove duplicate or near-duplicate sentences; merge contradictions sensibly.\n"
                "- Keep only stable, useful facts; drop noise and repetition.\n"
                "- Do not invent facts not supported by the draft."
            ),
        },
        {
            "role": "user",
            "content": f"Draft section text JSON:\n{json.dumps(sections, ensure_ascii=False)}",
        },
    ]
    return await complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=MemorySectionUpdateResult,
        max_tokens=2048,
    )


async def extract_todo_actions(
    settings: Settings,
    transcript: str,
    current_todos: list[dict[str, object]],
    *,
    user_timezone: str | None = None,
) -> TodoExtractionResult | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_todo_actions(transcript, current_todos)

    import json

    snapshot = json.dumps(current_todos, ensure_ascii=False)
    tz_note = user_timezone or "UTC"
    messages = [
        {
            "role": "system",
            "content": (
                "Extract todo list changes requested in this conversation turn. "
                f"User timezone: {tz_note}. "
                "Current todos JSON:\n"
                f"{snapshot}\n\n"
                "Return ONLY JSON (no markdown): "
                '{"actions": [{"action": "add|complete|uncheck|delete|delete_list|set_due|clear_due", '
                '"topic": "list title", "content": "item text (omit for delete_list)", '
                '"due_at": "ISO-8601 datetime or null"}]}. '
                "Rules:\n"
                "- For add: only when the user gave a clear list title AND item text. "
                "If they want a new list but no title yet, return empty actions.\n"
                "- For add: topic must be the agreed list name (e.g. Groceries, Taxes). "
                "Never invent titles or default to General.\n"
                "- For add/set_due: due_at optional on add; required on set_due. "
                "Interpret relative dates in the user's timezone (tomorrow, Friday 5pm).\n"
                "- Bulk reschedule (all reminders due today → tomorrow): emit one set_due "
                'per affected item, OR a single set_due with content="*" when moving every '
                "open item due today.\n"
                "- If the user says you missed some / only moved one, emit set_due for every "
                "remaining item still due today in the snapshot.\n"
                "- For clear_due: remove due date from the matched item.\n"
                "- For complete/uncheck/delete: match existing items; use their topic.\n"
                "- For delete_list: when the user clearly wants to remove an entire list, emit one "
                "action per list title; leave content empty. Skipped server-side if open items remain.\n"
                "- Only emit actions the user clearly requested this turn.\n"
                "- Return empty actions array if none."
            ),
        },
        {"role": "user", "content": transcript},
    ]
    return await complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=TodoExtractionResult,
        max_tokens=512,
    )


async def extract_project_actions(
    settings: Settings,
    transcript: str,
    snapshot: dict[str, object],
) -> ProjectExtractionResult | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_project_actions(transcript, snapshot)

    state = json.dumps(snapshot, ensure_ascii=False)
    messages = [
        {
            "role": "system",
            "content": (
                "Extract learning-topic workspace changes from this conversation turn "
                "(user message + assistant reply). "
                "Current state JSON:\n"
                f"{state}\n\n"
                "Return ONLY JSON (no markdown): "
                '{"actions": [{"action": '
                '"create_project|delete_project|set_description|set_level|add|start_learning|'
                'master|unmaster|delete|delete_list", '
                '"project_title": "must match a topic title from state when possible", '
                '"kind": "language|programming|trivia|learning|general (use language for English/vocab)", '
                '"level": "level1-level6 (for language topics)", '
                '"description": "optional description", '
                '"list_title": "group/list name (e.g. Travel, General)", '
                '"content": "one word/phrase per add action", '
                '"definition": "meaning in plain English", '
                '"example_sentence": "example using the word", '
                '"note": "alias for example_sentence"}]}. '
                "Rules:\n"
                "- Do NOT emit create_project for software products, apps to build, repos, or "
                "codebases (e.g. 'dating app project', 'my React app') — GitHub coding projects "
                "are a separate future feature.\n"
                "- For programming learning topics: list_title = journey topic (Variables, "
                "Functions, …); content = concept name; use master/start_learning when the user "
                "learns it in chat.\n"
                "- add: ONE action per vocabulary word. Use list_title=General unless the user "
                "named a specific list.\n"
                "- add: emit when user asked OR assistant listed new words to add this turn. "
                "Only add words appropriate for the topic's level (level1=beginner basics only).\n"
                "- start_learning / master / unmaster: update word status.\n"
                "- master: ONLY when the user answered a vocabulary quiz correctly this turn. "
                "NEVER emit master if the user picked the wrong letter, the assistant said their "
                "answer was wrong, or the assistant corrected them to a different option.\n"
                "- set_level: when user moves up (level1=beginner … level6=fluent English skill).\n"
                "- Return empty actions array if nothing should change."
            ),
        },
        {"role": "user", "content": transcript},
    ]

    response = await _acompletion_with_fallback(
        settings,
        "memory-model",
        messages=messages,
        max_tokens=768,
        response_format={"type": "json_object"},
    )
    if response is None:
        return None
    try:
        raw = (response.choices[0].message.content or "{}").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        actions: list[ProjectActionItem] = []
        for item in data.get("actions") or []:
            if not isinstance(item, dict):
                continue
            try:
                actions.append(ProjectActionItem.model_validate(item))
            except Exception:
                logger.warning("Skipping invalid project action: %s", item)
        return ProjectExtractionResult(actions=actions)
    except Exception:
        logger.exception("Project action extraction failed to parse response")
        return None


async def summarize_conversation(
    settings: Settings,
    prior_summary: str | None,
    messages: list[dict[str, str]],
) -> str | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_summary(prior_summary, messages)

    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    parts: list[str] = []
    if prior_summary:
        parts.append(f"Existing summary:\n{prior_summary}")
    parts.append(f"New messages to fold in:\n{transcript}")

    msgs = [
        {
            "role": "system",
            "content": SUMMARY_SYSTEM_PROMPT,
        },
        {"role": "user", "content": "\n\n".join(parts)},
    ]
    response = await _acompletion_with_fallback(
        settings, "memory-model", messages=msgs, max_tokens=settings.summary_max_tokens
    )
    if response is None:
        return None
    try:
        text = (response.choices[0].message.content or "").strip()
        return cap_summary(text) if text else None
    except Exception:
        logger.exception("Conversation summarization failed to parse response")
        return None
