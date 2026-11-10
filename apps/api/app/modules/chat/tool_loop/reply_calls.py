"""The tools on the reply's own model call: ``web_search`` and ``recall_chats``.

Word rules used to decide search, and each one misfired on its look-alikes: "What is
going on" opening a chat matched a news pattern and was answered with a song. The
model writing the reply decided, carrying ``web_search`` on every turn; it answers at
once, or calls the tool and answers in a second call that reads the results. A fast read
of the message now decides first (``web_search.live_read``): live, and its query is
searched before the reply; settled, and the reply carries no ``web_search`` (GPT-6 Luna
searched how-tos and history it was offered the tool for). Only with no answer from the
read in time does the reply's model decide. ``recall_chats`` (``memory.recall_tool``) is offered the same way,
so the model, not a phrase list, decides when a turn reads the user's earlier chats.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, NamedTuple
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
from app.modules.web_search import TurnTavilyBudget, live_read_result

if TYPE_CHECKING:
    from app.modules.chat.turn_prep.context import StreamContext

logger = logging.getLogger(__name__)

REPLY_TOOL = "web_search"


class ReplyTurn(NamedTuple):
    """What the offer reads about a turn: its words, and what already answered it."""

    content: str
    lightweight: bool
    has_instant_reply: bool
    has_verified_math: bool
    has_search_sources: bool
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
    carries the user's switch), a quick reply or a verified solve answered the turn, or
    a search already ran. Whether the turn needs one is the model's call."""
    if not (
        settings.mcp_tool_loop_enabled
        and settings.reply_search_tool_enabled
        and settings.web_search_enabled
    ):
        return []
    if turn.lightweight or turn.has_instant_reply or turn.has_search_sources:
        return []
    if not open_parts(
        turn.content.strip(), has_verified_math=turn.has_verified_math, settings=settings
    ):
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


async def answer_into_turn(
    settings: Settings,
    redis: Redis,
    ctx: StreamContext,
    calls: list[dict[str, Any]],
    text_before: str,
    *,
    offered: frozenset[str],
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
) -> None:
    """Run the reply's tool calls; the next model call reads their results.

    The pages a search found become the turn's sources, so the reply gets their chips.
    A search that breaks leaves the prompt as it was: the reply answers without it.
    """
    try:
        answered = await answer_reply_calls(
            settings=settings,
            messages=ctx.prompt_messages,
            calls=calls,
            text_before=text_before,
            offered=offered,
            user=ctx.user,
            redis=redis,
            chat_id=ctx.chat_id,
            user_timezone=ctx.user_timezone,
            user_text=ctx.user_message_content,
            user_location=ctx.search_location,
            on_status=on_status,
            should_cancel=should_cancel,
        )
    except Exception:
        logger.exception("Reply tool calls failed chat_id=%s; answering without them", ctx.chat_id)
        return
    ctx.prompt_messages = answered.messages
    if answered.search_hits and not ctx.search_sources:
        ctx.search_sources = answered.search_hits


async def search_the_live_read(
    settings: Settings,
    redis: Redis,
    ctx: StreamContext,
    *,
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
) -> None:
    """A model read the message beside the prep (``web_search.live_read``). An answer that
    depends on facts that change is searched with the read's own query, so the reply
    answers from the results in one call, and so is one the user asked to search; with no
    query, the reply's call must search. A read that found nothing that changes takes
    ``web_search`` off the reply's call. With no answer in time, the reply keeps it."""
    if ctx.live_read is not None and not ctx.live_read.done() and on_status is not None:
        # A model is still reading the question: say so rather than show nothing. A search
        # it asks for shows next, with its query ("Searching — …").
        await on_status("thinking", None)
    read = await live_read_result(ctx.live_read, settings)
    if read is None:
        return
    if not read.searches:
        # One decider: the read found nothing that changes, so the reply has no search to
        # make. Told so and still offered the tool, GPT-6 Luna searched how-tos and the way
        # to a place the chat had named on about one turn in twelve (2026-11-09).
        ctx.reply_tools = _without_search(ctx.reply_tools)
        return
    if not read.query.strip():
        ctx.reply_requires = REPLY_TOOL
        return
    call = {
        "id": "live_read",
        "type": "function",
        "function": {
            "name": REPLY_TOOL,
            "arguments": json.dumps({"query": read.query.strip()}),
        },
    }
    before = ctx.prompt_messages
    await answer_into_turn(
        settings,
        redis,
        ctx,
        [call],
        "",
        offered=frozenset({REPLY_TOOL}),
        on_status=on_status,
        should_cancel=should_cancel,
    )
    if ctx.prompt_messages is before:
        # The search broke: the reply's model still decides.
        return
    # One search a turn: the reply reads these results and carries no second search.
    ctx.reply_tools = _without_search(ctx.reply_tools)


def _without_search(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The reply's tools less ``web_search`` (``recall_chats`` stays)."""
    return [tool for tool in tools if (tool.get("function") or {}).get("name") != REPLY_TOOL]
