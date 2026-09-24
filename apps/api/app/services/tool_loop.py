"""Model-initiated MCP tool rounds via LiteLLM ``tools=``.

When ``mcp_tool_loop_enabled`` is on, run bounded non-streaming tool rounds
before the user-visible stream — **only if the turn likely needs a tool**.
Ordinary Q&A streams immediately. After tools run, the visible answer is
**streamed** (tools omitted) — we do not dump a leftover completion as one
chunk, and we do not throw it away and call the model a third time.

SymPy tool results that carry a ``canonical_fence`` in ``ToolResult.data`` are
collected so ``validate_math_fences`` can still overwrite/densify geometry and
graph fences the same way the heuristic math_tools path does.

``generate_image`` is terminal: on success the stream skips the visible LLM
pass and uses the already-persisted ``[Image: …]`` assistant row.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.gateways.litellm_gateway import ModelUnavailableError
from app.gateways.mcp import registry as mcp_registry
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import User
from app.modules.images.gen_tool import bind_image_gen_context
from app.modules.images.search_tool import bind_image_search_context
from app.modules.integrations.tool import bind_calendar_context
from app.modules.job_search.tool import JOB_DIRECT_REPLY_PREFIX, bind_job_search_context
from app.modules.math.reply_policy import MATH_REPLY_POLICY
from app.modules.math.tools import VerifiedMathBlock
from app.modules.math.tools.extract import trig_domain_would_be_dropped
from app.services import plan as plan_service
from app.services.chat.stream_status import StreamStatusFn, clip_status_detail
from app.services.mcp.web_search_adapter import bind_search_quota_context

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TerminalImageResult:
    """Successful model-initiated image gen — stream must not create another row."""

    message_id: str
    final_content: str
    resolved_model: str


def _status_for_tool(name: str) -> str | None:
    if name in ("web_search", "job_search"):
        return "searching"
    if name == "sympy":
        return "calculating"
    if name in ("generate_image", "search_image"):
        return "image_gen"
    return None


def _canonical_from_tool_result(result: Any) -> dict[str, Any] | None:
    data = getattr(result, "data", None)
    if not isinstance(data, dict):
        return None
    fence = data.get("canonical_fence")
    return fence if isinstance(fence, dict) else None


def _canonical_answer_from_tool_result(result: Any) -> str | None:
    data = getattr(result, "data", None)
    if not isinstance(data, dict):
        return None
    answer = data.get("canonical_answer")
    return answer.strip() if isinstance(answer, str) and answer.strip() else None


def _search_hits_from_tool_result(result: Any) -> list[WebSearchHit]:
    data = getattr(result, "data", None)
    if not isinstance(data, dict):
        return []
    raw = data.get("hits")
    if not isinstance(raw, list):
        return []
    hits: list[WebSearchHit] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        url = str(item.get("url") or "")
        snippet = str(item.get("snippet") or "")
        if title or url:
            hits.append(WebSearchHit(title=title, url=url, snippet=snippet))
    return hits


def _last_user_content(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            return content.strip() if isinstance(content, str) else ""
    return ""


def _sympy_solve_drops_trig_domain(name: str, raw_args: Any, user_text: str) -> bool:
    if name != "sympy":
        return False
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except (TypeError, ValueError):
        return False  # Let the registry report malformed arguments normally.
    if not isinstance(args, dict) or str(args.get("action") or "solve").strip().lower() != "solve":
        return False
    return trig_domain_would_be_dropped(
        f"{args.get('lhs') or ''} {args.get('rhs') or ''}", user_text
    )


def _web_search_was_called(messages: list[dict[str, Any]]) -> bool:
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for call in msg.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            name = str((call.get("function") or {}).get("name") or "")
            if name == "web_search":
                return True
    return False


def _merge_search_hits(existing: list[WebSearchHit], incoming: list[WebSearchHit]) -> None:
    seen = {hit.url.strip().lower() or hit.title.strip().lower() for hit in existing}
    for hit in incoming:
        key = hit.url.strip().lower() or hit.title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        existing.append(hit)


async def _force_web_search_if_needed(
    *,
    settings: Settings,
    messages: list[dict[str, Any]],
    search_hits: list[WebSearchHit],
    user: User | None,
    redis: Redis | None,
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
    search_required: bool = False,
) -> tuple[list[dict[str, Any]], list[WebSearchHit]]:
    """If the model skipped web_search on a turn that needs live results, search once.

    ``search_required`` preserves a classifier-yes decision. The sync heuristic
    alone would otherwise drop that turn (silent answer from training data).
    Empty hits still inject a no-results block so the model cannot look current.
    """
    if search_hits:
        return messages, search_hits
    if should_cancel and should_cancel():
        return messages, search_hits
    if not settings.web_search_enabled:
        return messages, search_hits
    user_text = _last_user_content(messages)
    if not user_text:
        return messages, search_hits
    from app.services.prompt_inject import inject_before_last_user
    from app.services.prompt_safety import wrap_untrusted
    from app.services.web_search.detection import needs_web_search
    from app.services.web_search.formatting import format_search_block, format_search_empty_block
    from app.services.web_search.search_cache import run_cached_search

    already_searched = _web_search_was_called(messages)
    if not search_required and not already_searched and not needs_web_search(user_text):
        return messages, search_hits

    tried = [user_text]
    if not already_searched:
        if on_status is not None:
            await on_status("searching", clip_status_detail(user_text))
        hits, tried = await run_cached_search(
            settings,
            [user_text],
            user=user,
            redis=redis,
        )
        if hits:
            block = wrap_untrusted("web search", format_search_block(hits))
            return inject_before_last_user(messages, block), hits

    empty = format_search_empty_block(tried or [user_text])
    return inject_before_last_user(messages, empty), search_hits


def _terminal_image_from_tool_result(result: Any) -> TerminalImageResult | None:
    data = getattr(result, "data", None)
    if not isinstance(data, dict) or not data.get("terminal"):
        return None
    marker = data.get("image_marker")
    message_id = data.get("assistant_message_id")
    if not isinstance(marker, str) or not marker.startswith("[Image:"):
        return None
    if not isinstance(message_id, str) or not message_id.strip():
        return None
    model = data.get("resolved_model")
    resolved = model if isinstance(model, str) and model.strip() else "image-gen-model"
    return TerminalImageResult(
        message_id=message_id.strip(),
        final_content=marker.strip(),
        resolved_model=resolved,
    )


def _status_detail_for_tool(name: str, raw_args: str) -> str | None:
    """Surface the tool's subject (e.g. the search query) for the status label."""
    if name in ("web_search", "search_image"):
        key = "query"
    elif name == "generate_image":
        key = "prompt"
    else:
        return None
    try:
        args = json.loads(raw_args)
    except (TypeError, ValueError):
        return None
    if not isinstance(args, dict):
        return None
    value = args.get(key)
    return clip_status_detail(value) if isinstance(value, str) else None


def _tool_loop_completion_alias(model_alias: str) -> str:
    """Use one fast, function-capable selector independent of chat choice."""
    del model_alias
    return "gemini-flash"


_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
}

_UNFILTERED_JOB_SEARCH_WORDS = {
    "a",
    "again",
    "current",
    "find",
    "for",
    "job",
    "jobs",
    "look",
    "match",
    "matches",
    "me",
    "more",
    "my",
    "new",
    "now",
    "opening",
    "openings",
    "please",
    "profile",
    "role",
    "roles",
    "saved",
    "search",
    "searching",
    "start",
    "the",
    "using",
}


def _requested_job_limit(text: str) -> int | None:
    match = re.search(
        r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen)\b",
        text.casefold(),
    )
    if match is None:
        return None
    raw = match.group(1)
    value = int(raw) if raw.isdigit() else _NUMBER_WORDS.get(raw)
    return value if value is not None and 1 <= value <= 15 else None


def _is_unfiltered_job_search(text: str) -> bool:
    """Only bypass the selector when the request adds no search filters."""
    normalized = "".join(character if character.isalnum() else " " for character in text.casefold())
    words = normalized.split()
    return all(
        word.isdigit() or word in _NUMBER_WORDS or word in _UNFILTERED_JOB_SEARCH_WORDS
        for word in words
    )


def _is_one_off_job_search(text: str) -> bool:
    lower = text.casefold()
    has_search = bool(re.search(r"\b(search|find|look\s+for|start\s+searching)\b", lower))
    temporary = bool(
        re.search(
            r"\b(just this once|one[ -]?time|do not change|don't change|"
            r"without changing|keep my saved)\b",
            lower,
        )
    )
    return has_search and temporary


def _is_saved_job_update(text: str) -> bool:
    lower = text.casefold()
    if _is_one_off_job_search(text):
        return False
    has_mutation = bool(re.search(r"\b(restore|change|update|set|switch|edit|replace)\b", lower))
    has_subject = "my job" in lower or "job search" in lower
    has_preference = any(
        cue in lower
        for cue in (
            "saved",
            "preference",
            "profile",
            "location",
            "experience",
            "work mode",
            "remote",
            "hybrid",
            "on-site",
            "onsite",
            "target role",
            "skill",
            "salary",
            "frequency",
        )
    )
    return has_mutation and has_subject and has_preference


def _protect_one_off_job_search(
    name: str,
    raw_args: str,
    user_text: str,
) -> str:
    """Prevent temporary searches from mutating the saved My Job profile."""
    if name != "job_search" or not _is_one_off_job_search(user_text):
        return raw_args
    try:
        args = json.loads(raw_args)
    except (TypeError, ValueError):
        return raw_args
    if not isinstance(args, dict) or args.get("action") not in {"update_profile", "search_now"}:
        return raw_args
    args["action"] = "search_now"
    requested_limit = _requested_job_limit(user_text)
    if requested_limit is not None:
        args["result_limit"] = requested_limit
    return json.dumps(args)


def _protect_saved_job_update(name: str, raw_args: str, user_text: str) -> str:
    """Keep explicit saved-search edits from becoming temporary searches."""
    if name != "job_search" or not _is_saved_job_update(user_text):
        return raw_args
    try:
        args = json.loads(raw_args)
    except (TypeError, ValueError):
        return raw_args
    if (
        not isinstance(args, dict)
        or args.get("action") != "search_now"
        or args.get("preferences") is None
    ):
        return raw_args
    args["action"] = "update_profile"
    args.pop("result_limit", None)
    return json.dumps(args)


def _direct_job_tool_args(text: str) -> dict[str, Any] | None:
    """Return safe My Job actions that need no model interpretation.

    This keeps common reads and unambiguous preference edits reliable during a
    model-provider outage. More complex edits still use the structured selector.
    """
    lower = text.casefold()
    if not lower.strip():
        return None
    if _is_one_off_job_search(text):
        # Let the structured selector extract temporary role/location filters;
        # the invoke path below guarantees they cannot become a profile edit.
        return None
    match_id = re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        lower,
    )
    match_status = next(
        (
            status
            for status in (
                "saved",
                "applied",
                "interviewing",
                "offer",
                "rejected",
                "hidden",
                "new",
            )
            if re.search(rf"\b{status}\b", lower)
        ),
        None,
    )
    if (
        match_id is not None
        and match_status is not None
        and any(cue in lower for cue in ("mark", "move", "set", "change", "update"))
    ):
        return {
            "action": "update_match",
            "match_id": match_id.group(0),
            "match_status": match_status,
        }
    if "http://" in lower or "https://" in lower:
        if any(cue in lower for cue in ("check", "analyze", "analyse", "compare", "fit")):
            starts = [
                index for index in (lower.find("https://"), lower.find("http://")) if index >= 0
            ]
            if starts:
                start = min(starts)
                url = text[start:].split()[0].rstrip('.,;:!?)"]}')
                return {"action": "analyze_job", "job_url": url}
    if "pause" in lower and ("my job" in lower or "job search" in lower):
        return {"action": "update_status", "search_status": "paused"}
    if "resume" in lower and ("my job" in lower or "job search" in lower):
        return {"action": "update_status", "search_status": "active"}
    mutation_cues = (
        "change",
        "restore",
        "update",
        "set ",
        "switch",
        "make it",
        "prefer",
        "only want",
    )
    if any(cue in lower for cue in mutation_cues):
        # Arbitrary role/location/skill/salary edits need the structured tool
        # selector. Handling only the easy fragment (for example, experience)
        # would silently ignore the requested role while claiming full success.
        complex_change = any(
            cue in lower
            for cue in (
                "target role",
                "job type",
                "skill",
                "salary",
                "location",
                "sponsorship",
                "excluded",
                "company",
            )
        ) or bool(re.search(r"\b(?:my job|job search)\s+to\b", lower))
        if complex_change:
            return None
        preferences: dict[str, Any] = {}
        work_modes = [
            mode
            for mode, patterns in (
                ("remote", ("remote",)),
                ("hybrid", ("hybrid",)),
                ("onsite", ("onsite", "on-site", "on site")),
            )
            if any(pattern in lower for pattern in patterns)
        ]
        if work_modes:
            preferences["work_modes"] = work_modes
        experience_levels = [
            level
            for level, patterns in (
                ("internship", ("internship", "intern level")),
                ("entry", ("entry level", "entry-level")),
                ("mid", ("mid level", "mid-level")),
                ("senior", ("senior",)),
            )
            if any(pattern in lower for pattern in patterns)
        ]
        if experience_levels:
            preferences["experience_levels"] = experience_levels
        frequency = next(
            (
                value
                for value, patterns in (
                    ("weekdays", ("weekdays", "every weekday")),
                    ("daily", ("daily", "every day")),
                    ("weekly", ("weekly", "every week")),
                    ("monthly", ("monthly", "every month")),
                )
                if any(pattern in lower for pattern in patterns)
            ),
            None,
        )
        if frequency is not None:
            preferences["frequency"] = frequency
        if preferences:
            return {"action": "update_profile", "preferences": preferences}
    if any(cue in lower for cue in ("preference", "setting", "profile")) and (
        "my job" in lower or "job search" in lower
    ):
        return {"action": "get_profile"}
    if any(cue in lower for cue in ("match", "listing", "saved job", "applied job")) and (
        "job" in lower or "role" in lower
    ):
        return {"action": "list"}
    if re.search(r"\b(search|find|look\s+for|start\s+searching)\b", lower):
        if not _is_unfiltered_job_search(text):
            # Role, location, level, work mode, and other filters belong to the
            # structured selector. A direct search here would silently use the
            # saved profile and ignore the user's requested filters.
            return None
        search_args: dict[str, Any] = {"action": "search_now"}
        requested_limit = _requested_job_limit(text)
        if requested_limit is not None:
            search_args["result_limit"] = requested_limit
        return search_args
    return None


def _job_tool_unavailable_message() -> dict[str, Any]:
    return {
        "role": "system",
        "content": (
            "This request requires the My Job tool, but no verified My Job tool result "
            "was produced. Never infer saved preferences, matches, schedules, or job-search "
            "state from memories or past conversation. Briefly say My Job could not be "
            "checked or changed right now and ask the user to retry."
        ),
    }


def direct_tool_reply(messages: list[dict[str, Any]]) -> str | None:
    """Extract an authoritative tool reply from a tool-role message only."""
    for message in reversed(messages):
        if message.get("role") != "tool":
            continue
        content = message.get("content")
        if not isinstance(content, str) or not content.startswith(JOB_DIRECT_REPLY_PREFIX):
            continue
        reply = content.removeprefix(JOB_DIRECT_REPLY_PREFIX).strip()
        return reply or None
    return None


def _tool_calls_from_text(
    content: object,
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Recover a provider-emitted ``!function_call`` as a validated tool call.

    Some OpenAI-compatible providers occasionally serialize the function call
    into assistant text even when ``tools`` were supplied. Only offered tool
    names are accepted here; the normal registry validation still owns the
    arguments before invocation.
    """
    if not isinstance(content, str):
        return []
    marker = "!function_call:"
    start = content.find(marker)
    if start < 0:
        return []
    raw = content[start + len(marker) :].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    name = payload.get("call") or payload.get("name")
    offered = {
        str((tool.get("function") or {}).get("name") or "")
        for tool in tools
        if isinstance(tool, dict)
    }
    if not isinstance(name, str) or name not in offered:
        return []
    arguments = payload.get("arguments", {})
    if isinstance(arguments, dict):
        encoded_arguments = json.dumps(arguments)
    elif isinstance(arguments, str):
        try:
            parsed_arguments = json.loads(arguments)
        except (TypeError, ValueError):
            return []
        if not isinstance(parsed_arguments, dict):
            return []
        encoded_arguments = json.dumps(parsed_arguments)
    else:
        return []
    call_id = payload.get("id")
    return [
        {
            "id": call_id if isinstance(call_id, str) and call_id else f"text_{name}",
            "type": "function",
            "function": {"name": name, "arguments": encoded_arguments},
        }
    ]


def _has_whole_word(lower: str, word: str) -> bool:
    start = 0
    n = len(word)
    length = len(lower)
    while True:
        idx = lower.find(word, start)
        if idx == -1:
            return False
        before_ok = idx == 0 or not lower[idx - 1].isalpha()
        after_ok = idx + n == length or not lower[idx + n].isalpha()
        if before_ok and after_ok:
            return True
        start = idx + 1


def leftover_math_after_verified(content: str) -> bool:
    """Heuristic SymPy took one clause; the user still asked for another.

    Skip the MCP loop only for a single-clause verified ask. Graph + solve
    (or a second ``=`` next to a graph cue) still needs tools.
    """
    lower = content.lower()
    has_viz = any(_has_whole_word(lower, w) for w in ("graph", "plot", "sketch"))
    has_solve = _has_whole_word(lower, "solve")
    if has_viz and has_solve:
        return True
    if has_viz and lower.count("=") >= 2:
        return True
    return False


def turn_needs_tool_loop(
    content: str,
    *,
    lightweight: bool = False,
    has_instant_reply: bool = False,
    has_verified_math: bool = False,
    has_search_sources: bool = False,
    web_search: bool | None = None,
    job_search_turn: bool = False,
    settings: Settings | None = None,
    user: User | None = None,
) -> bool:
    """True when a pre-stream ``complete_with_tools`` round is worth the TTFT cost.

    Heuristic SymPy / Tavily already inject on the prompt path. Paying a full
    non-streaming LLM round on every other turn (then discarding the answer and
    streaming a second call) is what made ordinary chat sit on typing dots for
    ~6s. Skip unless this message still looks like search, unsolved math,
    calendar create, or Pro image gen.

    ``web_search``: optional classifier override (None = sync heuristic).
    """
    if settings is not None and not settings.mcp_tool_loop_enabled:
        return False
    if has_instant_reply:
        return False
    text = content.strip() if isinstance(content, str) else ""
    if not text:
        return False
    if job_search_turn:
        return True
    if lightweight:
        return False
    if has_verified_math and not leftover_math_after_verified(text):
        return False

    from app.modules.images.gen_intent import extract_image_gen_prompt
    from app.modules.images.lookup_intent import extract_image_lookup_query
    from app.modules.job_search.chat_intent import wants_job_search
    from app.modules.math.tools import needs_symbolic_math
    from app.services.web_search.detection import needs_web_search

    if web_search is True:
        return True
    if web_search is not False and not has_search_sources and needs_web_search(text):
        return True
    if wants_job_search(text):
        return True
    math_on = settings is None or settings.math_tools_enabled
    if math_on and needs_symbolic_math(text):
        from app.modules.math.tools.extract import extract_math_intent

        # Detection without an extractor is the 7*8 trap: the sympy tool
        # calls the same extractor and burns the round timeout for nothing.
        if extract_math_intent(text) is None:
            return False
        return True
    # Reference-photo lookup ("show me an ear") is checked before generation
    # so its disjoint trigger phrasing (show / let … see / what does … look
    # like) never competes with generation's own verbs — see
    # image_lookup_intent's module docstring.
    lookup_on = settings is None or settings.image_search_enabled
    if lookup_on and extract_image_lookup_query(text):
        return True
    image_on = settings is None or settings.image_generation_enabled
    if (
        image_on
        and user is not None
        and plan_service.is_pro(user)
        and extract_image_gen_prompt(text)
    ):
        return True
    return False


def _tools_for_user(settings: Settings, user: User | None) -> list[dict[str, Any]]:
    """OpenAI tool payloads; omit image gen for free users / when disabled."""
    tools = mcp_registry.build_openai_tools()
    if not settings.image_search_enabled:
        tools = [t for t in tools if (t.get("function") or {}).get("name") != "search_image"]
    if settings.image_generation_enabled and user is not None and plan_service.is_pro(user):
        return tools
    return [t for t in tools if (t.get("function") or {}).get("name") != "generate_image"]


async def run_tool_rounds(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    usage: dict[str, int],
    on_status: StreamStatusFn | None = None,
    should_cancel: Callable[[], bool] | None = None,
    user: User | None = None,
    redis: Redis | None = None,
    chat_id: UUID | None = None,
    web_search: bool | None = None,
) -> tuple[
    list[dict[str, Any]],
    VerifiedMathBlock | None,
    TerminalImageResult | None,
    list[WebSearchHit],
]:
    """Mutate a copy of *messages* through up to ``mcp_tool_loop_max_rounds`` tool rounds.

    Returns ``(messages, verified_math, terminal_image, search_hits)``. Tool-call
    rounds stay non-streaming. After tools execute, the caller streams the
    user-visible answer (tools omitted) instead of a discarded leftover completion.
    """
    if not settings.mcp_tool_loop_enabled:
        return messages, None, None, []

    tools = _tools_for_user(settings, user)
    if not tools:
        return messages, None, None, []

    # A classified My Job turn must never spill into calendar, reminders, web,
    # or another tool family. Restricting the selector is both more accurate
    # and prevents an unrelated side effect when the request is an edit.
    from app.modules.job_search.chat_intent import wants_job_search_turn

    if wants_job_search_turn(messages):
        tools = [tool for tool in tools if (tool.get("function") or {}).get("name") == "job_search"]
        if not tools:
            return [*messages, _job_tool_unavailable_message()], None, None, []

    with (
        bind_search_quota_context(user=user, redis=redis, settings=settings),
        bind_image_gen_context(user=user, redis=redis, chat_id=chat_id),
        bind_image_search_context(user=user, redis=redis, chat_id=chat_id),
        bind_calendar_context(user=user, redis=redis, settings=settings),
        bind_job_search_context(user=user, redis=redis, settings=settings),
    ):
        working, verified, terminal, hits = await _run_tool_rounds_bound(
            settings=settings,
            model_alias=model_alias,
            messages=messages,
            usage=usage,
            tools=tools,
            on_status=on_status,
            should_cancel=should_cancel,
        )
        working, hits = await _force_web_search_if_needed(
            settings=settings,
            messages=working,
            search_hits=hits,
            user=user,
            redis=redis,
            on_status=on_status,
            should_cancel=should_cancel,
            search_required=web_search is True,
        )
        return working, verified, terminal, hits


async def _run_tool_rounds_bound(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    usage: dict[str, int],
    tools: list[dict[str, Any]],
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
) -> tuple[
    list[dict[str, Any]],
    VerifiedMathBlock | None,
    TerminalImageResult | None,
    list[WebSearchHit],
]:
    working: list[dict[str, Any]] = [dict(m) for m in messages]
    user_text = _last_user_content(messages)
    from app.modules.job_search.chat_intent import wants_job_search_turn

    job_search_turn = wants_job_search_turn(messages)
    direct_job_args = _direct_job_tool_args(user_text) if job_search_turn else None
    if direct_job_args is not None:
        call_id = "job_search_direct"
        result = await mcp_registry.invoke_validated("job_search", direct_job_args)
        content = result.content if result else "My Job is unavailable right now."
        working.extend(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": "job_search",
                                "arguments": json.dumps(direct_job_args),
                            },
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": call_id, "content": content},
            ]
        )
        return working, None, None, []
    max_rounds = max(1, settings.mcp_tool_loop_max_rounds)
    # Collect canonical fences across rounds keyed by type so a geometry
    # fence from round 1 isn't lost when round 2 produces a graph fence.
    canonical_by_type: dict[str, dict[str, Any]] = {}
    canonical_answer: str | None = None
    terminal_image: TerminalImageResult | None = None
    search_hits: list[WebSearchHit] = []

    for _ in range(max_rounds):
        if should_cancel and should_cancel():
            break
        try:
            msg = await litellm_gateway.complete_with_tools(
                settings=settings,
                model_alias=_tool_loop_completion_alias(model_alias),
                messages=working,
                tools=tools,
                max_tokens=max(1, settings.mcp_tool_loop_probe_max_tokens),
                usage=usage,
                timeout_seconds=settings.mcp_tool_loop_timeout_seconds,
                should_cancel=should_cancel,
            )
        except ModelUnavailableError:
            logger.warning("Tool-loop completion failed; falling through to stream")
            working.append(_tool_selection_unavailable_message())
            if job_search_turn:
                working.append(_job_tool_unavailable_message())
            break
        except Exception:
            logger.exception("Tool-loop completion failed; falling through to stream")
            working.append(_tool_selection_unavailable_message())
            if job_search_turn:
                working.append(_job_tool_unavailable_message())
            break

        if should_cancel and should_cancel():
            break
        if msg.get("finish_reason") in ("length", "content_filter", "error"):
            working.append(_tool_selection_unavailable_message())
            break
        tool_calls = msg.get("tool_calls") or _tool_calls_from_text(msg.get("content"), tools)
        if not tool_calls:
            # Explicit no-tool decision; the caller streams the answer.
            if job_search_turn:
                working.append(_job_tool_unavailable_message())
            break

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        }
        working.append(assistant_msg)

        max_calls = max(1, settings.mcp_tool_loop_max_calls_per_round)
        invoke_deadline = time.monotonic() + max(0.0, settings.mcp_tool_loop_invoke_timeout_seconds)
        for index, call in enumerate(tool_calls):
            if should_cancel and should_cancel():
                break
            fn = call.get("function") or {}
            name = str(fn.get("name") or "")
            raw_args = fn.get("arguments") or "{}"
            raw_args = _protect_one_off_job_search(name, raw_args, user_text)
            raw_args = _protect_saved_job_update(name, raw_args, user_text)
            call_id = str(call.get("id") or name)
            if index >= max_calls:
                working.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": "Too many tool calls in one round.",
                    }
                )
                continue
            if time.monotonic() >= invoke_deadline:
                working.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": "Tool round timed out.",
                    }
                )
                continue
            if _sympy_solve_drops_trig_domain(name, raw_args, user_text):
                # This solver owns all-real trig solutions. The tool schema
                # cannot express the requested interval or alternative domain;
                # do not reintroduce an answer rejected during turn preparation.
                # Other computations and tool calls remain available.
                working.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": (
                            "This trig solve cannot verify the domain requested by the user. "
                            "No solution was certified. Preserve the requested domain when "
                            "answering; do not substitute an unrestricted real solution."
                        ),
                    }
                )
                continue
            phase = _status_for_tool(name) if name else None
            if on_status is not None and phase is not None:
                await on_status(phase, _status_detail_for_tool(name, raw_args))
            result = await mcp_registry.invoke_validated(name, raw_args)
            content = result.content if result else f"Unknown tool: {name}"
            if (
                job_search_turn
                and name == "job_search"
                and content.startswith(("Invalid arguments:", "Invalid JSON arguments."))
            ):
                content = (
                    f"{JOB_DIRECT_REPLY_PREFIX}I could not apply that My Job change "
                    "because part of the request was invalid. Nothing was changed."
                )
            fence = _canonical_from_tool_result(result) if result else None
            if fence is not None:
                # Merge by type so earlier rounds' fences survive later ones.
                fence_type = str(fence.get("type") or "")
                if fence_type:
                    canonical_by_type[fence_type] = fence
            answer = _canonical_answer_from_tool_result(result) if result else None
            if answer:
                canonical_answer = answer
            image = _terminal_image_from_tool_result(result) if result else None
            if image is not None:
                terminal_image = image
            if result is not None:
                _merge_search_hits(search_hits, _search_hits_from_tool_result(result))
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": content,
                }
            )

        # Image gen already persisted the assistant row — stop before another
        # completion round invents prose around the marker. Otherwise hand off
        # to the token stream instead of a leftover complete_with_tools that we
        # would throw away (search used to wait on that extra round).
        break

    # A cancel can land after the assistant's tool_calls are recorded but before
    # every tool result is appended. Providers reject a message list where a
    # tool_calls turn isn't fully answered, so truncate back to the last valid
    # (fully-answered) prefix before handing off to the visible stream.
    cut = _first_unanswered_assistant_idx(working)
    if cut is not None:
        logger.info("Tool loop cancelled mid-round; trimming unanswered tool_calls turn")
        working = working[:cut]

    all_fences = list(canonical_by_type.values())
    primary = all_fences[0] if all_fences else None
    verified = (
        VerifiedMathBlock(
            text="",
            canonical_fence=primary,
            canonical_fences=all_fences,
            canonical_answer=canonical_answer,
        )
        if all_fences or canonical_answer
        else None
    )
    if any(
        (call.get("function") or {}).get("name") == "sympy"
        for message in working[len(messages) :]
        if message.get("role") == "assistant"
        for call in message.get("tool_calls") or []
        if isinstance(call, dict)
    ):
        # Tool content is supporting data, not a request for a worked tutorial.
        # Append after completed results; cancelled/unanswered rounds were trimmed.
        working.append({"role": "system", "content": MATH_REPLY_POLICY})
    return working, verified, terminal_image, search_hits


def _tool_selection_unavailable_message() -> dict[str, Any]:
    return {
        "role": "system",
        "content": (
            "Tool selection was unavailable for this turn. No actions were performed by it. "
            "Use only tool results actually provided; if the request still requires an "
            "unavailable tool, briefly explain that it could not be completed."
        ),
    }


def _first_unanswered_assistant_idx(msgs: list[dict[str, Any]]) -> int | None:
    """Index of the newest assistant tool_calls turn missing a tool reply, else None."""
    for i in range(len(msgs) - 1, -1, -1):
        m = msgs[i]
        if m.get("role") != "assistant" or not m.get("tool_calls"):
            continue
        answered = {t.get("tool_call_id") for t in msgs[i + 1 :] if t.get("role") == "tool"}
        needed = {str(c.get("id") or "") for c in m["tool_calls"]}
        needed.discard("")
        if not needed.issubset(answered):
            return i
    return None
