"""The turn's tool rounds: search first, or one selection round and its calls.

Tool-call rounds stay non-streaming. After tools run, the caller streams the
user-visible answer (tools omitted): a leftover completion is never dumped as one
chunk, and never thrown away for a third model call. A round that ran tools hands
off at once — image generation already persisted its assistant row, and any
other answer streams.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.gateways.litellm_gateway import ModelUnavailableError
from app.gateways.mcp.base import ToolContext
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import User
from app.modules.chat.stream_status import StreamStatusFn
from app.modules.chat.tool_loop.calls import _execute_calls, _Round
from app.modules.chat.tool_loop.forced_search import _force_web_search_if_needed
from app.modules.chat.tool_loop.results import TerminalImageResult, ToolResults
from app.modules.chat.tool_loop.selection import (
    _last_user_content,
    _search_before_the_model,
    _tools_for_user,
    _user_texts,
)
from app.modules.chat.tool_loop.text_calls import _tool_calls_from_text
from app.modules.math.reply_policy import MATH_REPLY_POLICY
from app.modules.web_search import TurnTavilyBudget
from app.services import model_catalog
from app.services.solving import VerifiedMathBlock

logger = logging.getLogger(__name__)

# The first tool selector, then one retry on the next.
_SELECTION_ATTEMPTS = 2

_RoundsOutcome = tuple[
    list[dict[str, Any]],
    VerifiedMathBlock | None,
    TerminalImageResult | None,
    list[WebSearchHit],
]


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
    user_timezone: str | None = None,
    user_text: str | None = None,
    user_location: str | None = None,
    has_verified_math: bool = False,
    search_parts: list[str] | None = None,
) -> _RoundsOutcome:
    """Mutate a copy of *messages* through up to ``mcp_tool_loop_max_rounds`` tool rounds.

    Returns ``(messages, verified_math, terminal_image, search_hits)``. Tool-call
    rounds stay non-streaming. After tools execute, the caller streams the
    user-visible answer (tools omitted) instead of a discarded leftover completion.
    ``verified_math`` holds only tool results whose input matches ``user_text``
    (the user's own message; the last user prompt message when omitted).
    ``has_verified_math``: the server already solved the turn's maths part.
    ``search_parts``: the requests a classifier said need live results, when the
    message holds more than one (``tool_loop.parts``); each is searched for itself.
    """
    if not settings.mcp_tool_loop_enabled:
        return messages, None, None, []

    # The caller's text is the user's own words; the prompt's last user
    # message can also carry attached file text.
    own_text = user_text if user_text is not None else _last_user_content(messages)
    tools = _tools_for_user(settings, user, user_text=own_text)
    if not tools:
        return messages, None, None, []

    user_text = _last_user_content(messages)
    # One context for the turn: every tool call and the forced search share
    # its Tavily budget.
    ctx = ToolContext(
        user=user,
        redis=redis,
        chat_id=chat_id,
        user_timezone=user_timezone,
        user_query=user_text,
        tavily_budget=TurnTavilyBudget(settings=settings, user=user),
        user_location=user_location,
    )
    # An obvious lookup used to spend a model round deciding to call
    # web_search, then a second round writing the answer. Search first
    # and let the caller stream the reply once. Math and image turns
    # still need the selection round.
    if _search_before_the_model(
        user_text,
        settings,
        user,
        web_search=web_search,
        has_verified_math=has_verified_math,
    ):
        working, hits = await _force_web_search_if_needed(
            settings=settings,
            messages=messages,
            search_hits=[],
            ctx=ctx,
            on_status=on_status,
            should_cancel=should_cancel,
            search_required=True,
            search_parts=search_parts,
            has_verified_math=has_verified_math,
        )
        return working, None, None, hits

    working, verified, terminal, hits = await _run_rounds(
        settings=settings,
        model_alias=model_alias,
        messages=messages,
        usage=usage,
        tools=tools,
        ctx=ctx,
        on_status=on_status,
        should_cancel=should_cancel,
        user_texts=_user_texts(messages, user_text),
    )
    working, hits = await _force_web_search_if_needed(
        settings=settings,
        messages=working,
        search_hits=hits,
        ctx=ctx,
        on_status=on_status,
        should_cancel=should_cancel,
        search_required=web_search is True,
        search_parts=search_parts,
        has_verified_math=has_verified_math,
    )
    return working, verified, terminal, hits


async def _run_rounds(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    usage: dict[str, int],
    tools: list[dict[str, Any]],
    ctx: ToolContext,
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
    user_texts: list[str] | None = None,
) -> _RoundsOutcome:
    """Selection round → execute its calls (merging results) → stop → hand off.

    Bounded by ``mcp_tool_loop_max_rounds``, but a round with no calls streams and a
    round that ran calls hands off, so at most one round runs. The selection model
    comes from the catalog's tool selectors, whatever ``model_alias`` answers.
    """
    del model_alias
    turn = _Round(
        settings=settings,
        offered=frozenset(str((tool.get("function") or {}).get("name") or "") for tool in tools),
        ctx=ctx,
        on_status=on_status,
        should_cancel=should_cancel,
        user_texts=_user_texts(messages, None) if user_texts is None else user_texts,
        user_text=_last_user_content(messages),
    )
    working: list[dict[str, Any]] = [dict(m) for m in messages]
    collected = ToolResults()
    for _ in range(max(1, settings.mcp_tool_loop_max_rounds)):
        tool_calls = await _select_tool_calls(turn, tools, working, usage)
        if not tool_calls:
            break
        working.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
        await _execute_calls(turn, tool_calls, working, collected)
        # Image gen already persisted the assistant row — stop before another
        # completion round invents prose around the marker. Otherwise hand off
        # to the token stream instead of a leftover complete_with_tools that we
        # would throw away (search used to wait on that extra round).
        break
    return _hand_off(working, len(messages), collected)


async def _select_tool_calls(
    turn: _Round,
    tools: list[dict[str, Any]],
    working: list[dict[str, Any]],
    usage: dict[str, int],
) -> list[dict[str, Any]]:
    """One non-streaming selection round: the calls to run, or none to stream now.

    A failed or cut-off round leaves a note that tool selection was unavailable.
    """
    if turn.cancelled():
        return []
    msg = await _complete_selection(turn, tools, working, usage)
    if msg is None:
        if not turn.cancelled():
            working.append(_tool_selection_unavailable_message())
        return []
    if turn.cancelled():
        return []
    if msg.get("finish_reason") in ("length", "content_filter", "error"):
        working.append(_tool_selection_unavailable_message())
        return []
    # No calls is an explicit no-tool decision; the caller streams the answer.
    tool_calls: list[dict[str, Any]] = msg.get("tool_calls") or _tool_calls_from_text(
        msg.get("content"), tools
    )
    return tool_calls


def _hand_off(
    working: list[dict[str, Any]], prompt_len: int, collected: ToolResults
) -> _RoundsOutcome:
    """The messages the visible stream gets, and what the tools produced."""
    # A cancel can land after the assistant's tool_calls are recorded but before
    # every tool result is appended. Providers reject a message list where a
    # tool_calls turn isn't fully answered, so truncate back to the last valid
    # (fully-answered) prefix before handing off to the visible stream.
    cut = _first_unanswered_assistant_idx(working)
    if cut is not None:
        logger.info("Tool loop cancelled mid-round; trimming unanswered tool_calls turn")
        working = working[:cut]

    verified = collected.verified_math()
    if any(
        (call.get("function") or {}).get("name") == "sympy"
        for message in working[prompt_len:]
        if message.get("role") == "assistant"
        for call in message.get("tool_calls") or []
        if isinstance(call, dict)
    ):
        # Tool content is supporting data, not a request for a worked tutorial.
        # Append after completed results; cancelled/unanswered rounds were trimmed.
        working.append({"role": "system", "content": MATH_REPLY_POLICY})
    return working, verified, collected.terminal_image, collected.search_hits


async def _complete_selection(
    turn: _Round,
    tools: list[dict[str, Any]],
    working: list[dict[str, Any]],
    usage: dict[str, int],
) -> dict[str, Any] | None:
    """The selection decision from the first tool selector that gives one, else None.

    No tool runs before a complete decision, so asking the next selector after a
    failed or invalid one is safe. A timeout is not retried: it already spent the
    turn's selection budget, and the reply streams without tools instead.
    """
    settings = turn.settings
    selectors = model_catalog.tool_selector_aliases()[:_SELECTION_ATTEMPTS]
    for index, alias in enumerate(selectors):
        if index and turn.cancelled():
            return None
        last = index == len(selectors) - 1
        try:
            return await litellm_gateway.complete_with_tools(
                settings=settings,
                model_alias=alias,
                messages=working,
                tools=tools,
                max_tokens=max(1, settings.mcp_tool_loop_probe_max_tokens),
                usage=usage,
                timeout_seconds=settings.mcp_tool_loop_timeout_seconds,
                should_cancel=turn.should_cancel,
            )
        except ModelUnavailableError as exc:
            timed_out = isinstance(exc.__cause__, TimeoutError)
            logger.warning(
                "Tool selection failed alias=%s code=%s timed_out=%s", alias, exc.code, timed_out
            )
            if last or timed_out:
                return None
        except Exception:
            logger.exception("Tool selection failed alias=%s", alias)
            if last:
                return None
    return None


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
