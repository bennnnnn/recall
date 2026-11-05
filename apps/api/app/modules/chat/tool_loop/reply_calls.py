"""The tools on the reply's own model call: ``web_search`` and ``recall_chats``.

Word rules alone decided search in production: the classifier round that read the
rest cost every turn a model call before its first word, so it was turned off, and
"who won the champions league" or "what's the population of Ethiopia" was answered
from training data. A turn the rules neither searched nor ruled out now offers the
tool to the model writing the reply. It answers at once, or calls ``web_search`` and
answers in a second call that reads the results. A reply that needs no search costs
nothing more. ``recall_chats`` (``memory.recall_tool``) is offered the same way,
so the model, not a phrase list, decides when a turn reads the user's earlier chats.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, NamedTuple
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways.mcp import registry as mcp_registry
from app.gateways.mcp.base import ToolContext
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import User
from app.modules.chat.stream_status import StreamStatusFn
from app.modules.chat.tool_loop.calls import CallRound, execute_calls
from app.modules.chat.tool_loop.parts import open_parts
from app.modules.chat.tool_loop.results import ToolResults
from app.modules.chat.tool_loop.rounds import first_unanswered_tool_turn
from app.modules.chat.tool_loop.selection import last_user_content, user_words
from app.modules.memory.recall_tool import RECALL_TOOL
from app.modules.turn_reading.coding import has_code_syntax
from app.modules.turn_reading.conversation import is_social_opener
from app.modules.turn_reading.school_question import has_nothing_to_look_up
from app.modules.web_search import TurnTavilyBudget, web_search_skip
from app.services.time_context import is_remote_time_question

REPLY_TOOL = "web_search"


class ReplyTurn(NamedTuple):
    """What the offer reads about a turn: its words, and what already answered it."""

    content: str
    lightweight: bool
    has_instant_reply: bool
    has_verified_math: bool
    has_search_sources: bool
    prior_user_messages: list[str] | None
    prior_assistant: str | None
    # Memory is on and the prompt holds no earlier-chat snippets already.
    may_recall: bool = False


def reply_tools(settings: Settings, turn: ReplyTurn) -> list[dict[str, Any]]:
    """The tools the reply's model call may use: ``web_search``, ``recall_chats``, both
    or neither."""
    return [*_search_tools(settings, turn), *_recall_tools(settings, turn)]


def _recall_tools(settings: Settings, turn: ReplyTurn) -> list[dict[str, Any]]:
    """``recall_chats`` while memory is on, unless a quick reply or a verified solve
    answered the turn."""
    if not (turn.may_recall and settings.mcp_tool_loop_enabled):
        return []
    if not settings.chat_history_rag_enabled:
        return []
    if turn.lightweight or turn.has_instant_reply or turn.has_verified_math:
        return []
    adapter = mcp_registry.get(RECALL_TOOL)
    to_tool = getattr(adapter, "to_openai_tool", None)
    return [to_tool()] if callable(to_tool) else []


def _search_tools(settings: Settings, turn: ReplyTurn) -> list[dict[str, Any]]:
    """``web_search``, or nothing when search is off (``web_search_enabled`` already
    carries the user's switch), a quick reply or a verified solve answered the turn, a
    search already ran, or no open request has anything to look up
    (``_nothing_to_look_up``)."""
    if not (
        settings.mcp_tool_loop_enabled
        and settings.reply_search_tool_enabled
        and settings.web_search_enabled
    ):
        return []
    if turn.lightweight or turn.has_instant_reply or turn.has_search_sources:
        return []
    parts = open_parts(
        turn.content.strip(), has_verified_math=turn.has_verified_math, settings=settings
    )
    # One request reads the chat's earlier turns; parts of one message stand alone.
    earlier = turn if len(parts) == 1 else None
    if all(_nothing_to_look_up(part, earlier) for part in parts):
        return []
    return web_search_tool(settings)


def offers_search(tools: list[dict[str, Any]]) -> bool:
    """These reply tools include ``web_search``."""
    return any((tool.get("function") or {}).get("name") == REPLY_TOOL for tool in tools)


def web_search_tool(settings: Settings) -> list[dict[str, Any]]:
    """``web_search`` as the reply's call carries it, while its switches are on."""
    if not (
        settings.mcp_tool_loop_enabled
        and settings.reply_search_tool_enabled
        and settings.web_search_enabled
    ):
        return []
    adapter = mcp_registry.get(REPLY_TOOL)
    to_tool = getattr(adapter, "to_openai_tool", None)
    return [to_tool()] if callable(to_tool) else []


def _nothing_to_look_up(part: str, turn: ReplyTurn | None) -> bool:
    """A request the rules never search (chitchat, the user's own facts, a reminder, a
    sum), a greeting, a question about the code it pastes, the time somewhere else (the
    user's clock, moved to that place's zone, answers it), or a textbook question: "The
    lowest temperature at which a substance catches fire is called its a) … b) …" was
    answered from a YouTube comment (2026-10-30), though its note said not to search."""
    if is_social_opener(part) or has_code_syntax(part) or is_remote_time_question(part):
        return True
    if has_nothing_to_look_up(part):
        return True
    return web_search_skip(
        part,
        prior_user_messages=turn.prior_user_messages if turn else None,
        prior_assistant=turn.prior_assistant if turn else None,
    )


def tool_names(tools: list[dict[str, Any]]) -> frozenset[str]:
    """The names of the tools a reply round offered."""
    return frozenset(str(tool.get("function", {}).get("name") or "") for tool in tools) - {""}


class ReplyCallsOutcome(NamedTuple):
    """The messages the reply's next call reads, and the pages the search found."""

    messages: list[dict[str, Any]]
    search_hits: list[WebSearchHit]


async def answer_reply_calls(
    *,
    settings: Settings,
    messages: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    text_before: str,
    offered: frozenset[str],
    user: User | None,
    redis: Redis | None,
    chat_id: UUID | None,
    user_timezone: str | None,
    user_text: str,
    user_location: str | None,
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
) -> ReplyCallsOutcome:
    """Run the reply's calls: one tool message each, refused unless ``offered`` this round.

    The calls share one turn budget, like the tool loop's. A stop during the search
    trims the unanswered call, so the list stays one a provider accepts.
    """
    prompt_user_text = last_user_content(messages)
    ctx = ToolContext(
        user=user,
        redis=redis,
        chat_id=chat_id,
        user_timezone=user_timezone,
        user_query=prompt_user_text,
        tavily_budget=TurnTavilyBudget(settings=settings, user=user),
        user_location=user_location,
        deadline=time.monotonic() + settings.mcp_tool_loop_total_timeout_seconds,
    )
    turn = CallRound(
        settings=settings,
        # Only the tools this round sent: a stray web_search with search switched off, or a
        # recall when the prompt already holds the snippets, is refused, never run.
        offered=offered & {REPLY_TOOL, RECALL_TOOL},
        ctx=ctx,
        on_status=on_status,
        should_cancel=should_cancel,
        user_texts=user_words(messages, user_text),
        user_text=prompt_user_text,
    )
    working = [dict(message) for message in messages]
    working.append({"role": "assistant", "content": text_before or None, "tool_calls": calls})
    collected = ToolResults()
    await execute_calls(turn, calls, working, collected)
    cut = first_unanswered_tool_turn(working)
    if cut is not None:
        working = working[:cut]
    return ReplyCallsOutcome(working, collected.search_hits)
