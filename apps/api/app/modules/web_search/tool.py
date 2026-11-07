"""Web search MCP adapter."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.gateways.mcp.base import ToolContext, ToolResult
from app.models.schemas.tools import WebSearchToolInput
from app.modules.web_search.formatting import NEWEST_SOURCE_RULE, sources_payload
from app.modules.web_search.geo_intent import is_geo_query
from app.modules.web_search.query_builders import (
    anchor_news_query_to_today,
    anchor_to_location,
    filter_hits_to_today,
    is_current_news_request,
    is_news_today_request,
)
from app.modules.web_search.recency import wants_dated_results
from app.modules.web_search.search_cache import run_cached_search
from app.modules.web_search.source_dates import (
    local_today,
    mark_dates,
    published_note,
    stale_note,
)
from app.modules.web_search.source_tables import tables_as_rows
from app.services.number_text import NUMBER_WORDS
from app.services.prompt_safety import wrap_untrusted

# The tool result the model reads: a search that errored is not one that found nothing.
_NO_RESULTS = (
    "No results: the search ran and found nothing for this query. Say you couldn't find "
    "it; do not fill in from memory."
)
_SEARCH_FAILED = (
    "Search failed: the search service didn't respond, so nothing was retrieved. Say the "
    "search didn't work just now; do not say nothing exists, and do not present an answer "
    "from memory as checked."
)

# A small explicit list size: one to ten, from number_text's one table.
_COUNT_WORDS = {word: value for word, value in NUMBER_WORDS.items() if 1 <= value <= 10}


def _requested_news_count(text: str) -> int | None:
    """Read a small explicit list size without treating dates as counts."""
    lowered = text.casefold()
    for word, count in _COUNT_WORDS.items():
        if f" {word} " in f" {lowered} ":
            return count
    for token in lowered.replace("?", " ").replace(",", " ").split():
        if token.isdigit():
            count = int(token)
            if 1 <= count <= 10:
                return count
    return None


_SHOWN = 8


class WebSearchAdapter:
    name = "web_search"
    input_schema = WebSearchToolInput

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def describe(self) -> str:
        # The date where the model decides: told only in the system prompt, it answered
        # "who won the last world cup" with 2022's final in November 2026.
        today = datetime.now(UTC).strftime("%B %Y")
        return (
            f"Today is {today}. "
            "Search the web for current information. Call it before you write anything "
            "when the answer may have changed since you were trained: who holds an office "
            "or a title, winners, results and scores, records and rankings, prices, rates "
            "and figures that move (a population, a statistic), releases and versions, "
            "news, events and schedules, laws and rules, and anything about this year or "
            "the latest. Your training stopped well before today's date (the prompt has "
            "it): when the answer could have changed since, such as the most recent winner, "
            "whether something has come out yet, or what comes next, search rather than "
            "answer from memory. Call it whenever the user asks you to search, look something up, "
            "google it or check online. Do not call it for a greeting or small talk, for what "
            "stays true (definitions, history, science, maths, how things work, code, "
            "writing, advice), for what the user tells you about their own life, for work on "
            "this conversation itself (a summary of it, another practice problem, explaining "
            "something again, made-up sample data), or for the date or time anywhere (the "
            "prompt has the user's clock). A short opener such as "
            "'what's going on?' or 'what's up?' with nothing named is a hello: answer it as "
            "a friend would. A question about what you can do ('can you search the web?') is "
            "answered, not searched. Never tell the user why you did or did not search. "
            "The query must stand alone: spell out who or what "
            "the conversation is about (a full name, a place), never 'it', 'her' or 'do a "
            "search'. Write it as a person types into a search engine, with no month or "
            "year unless the question names one; set recent to false for a question about "
            "the past."
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.describe(),
                "parameters": WebSearchToolInput.model_json_schema(),
            },
        }

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query = str(args.get("query") or "").strip()
        if not query:
            return ToolResult(name=self.name, content="Missing query.")
        user_query = ctx.user_query
        current_news = is_current_news_request(user_query)
        news_today = is_news_today_request(user_query)
        if current_news:
            query = anchor_news_query_to_today(query, ctx.user_timezone)
        if ctx.user_location and is_geo_query(user_query):
            query = anchor_to_location(query, ctx.user_location)
        # One search per turn: a repeat call gets the first call's result.
        first = ctx.first_results.get(self.name)
        if first is not None:
            return first
        # Same cache + per-user Tavily reservation as the heuristic search path
        # — model-initiated calls must not bypass the daily cap.
        hits, _tried = await run_cached_search(
            self.settings,
            [query],
            user=ctx.user,
            redis=ctx.redis,
            budget=ctx.tavily_budget,
            # The tool is for what changes, so its pages are from the last year unless the
            # model says the question is about the past: "who is top of the premier league
            # table" named no time, was searched with none, and read a mid-October table
            # (2026-11-05). The news search beside it stays for asks about now in the
            # user's words ("latest", "right now"); it costs a second search.
            dated=wants_dated_results(user_query),
            recent=args.get("recent") is not False,
        )
        if news_today:
            hits = filter_hits_to_today(hits, ctx.user_timezone)
        requested_count = _requested_news_count(user_query) if news_today else None
        if requested_count is not None and len(hits) < requested_count:
            result = ToolResult(
                name=self.name,
                content=(
                    f"Only {len(hits)} independently dated same-day result(s) were found, "
                    f"fewer than the {requested_count} requested. Do not use the result details, "
                    "split one source into multiple developments, substitute older news, or invent "
                    "items. Tell the user the requested same-day list could not be verified."
                ),
            )
            ctx.first_results[self.name] = result
            return result
        if not hits:
            content = _NO_RESULTS
            if ctx.tavily_budget.search_failed:
                content = _SEARCH_FAILED
            elif news_today:
                content = (
                    "No search result explicitly verified an item for the user's current "
                    "local date. Say that no same-day developments could be verified; do not "
                    "substitute older news or invent items."
                )
            result = ToolResult(name=self.name, content=content)
        else:
            # The general results and the dated pages beside them (``search_cache``).
            shown = hits[:_SHOWN]
            today = local_today(ctx.user_timezone)
            lines = [
                f"- {hit.title}: {hit.url}\n  {published_note(hit.published, today, ctx.user_timezone)}"
                f"{stale_note(hit.snippet, today)}{tables_as_rows(mark_dates(hit.snippet, today))}"
                for hit in shown
            ]
            lines.insert(0, NEWEST_SOURCE_RULE)
            if current_news:
                lines.insert(
                    0,
                    "The search was anchored to the user's current local date. "
                    f"Only {len(shown)} matching result(s) were verified. Only describe an item "
                    "as today's when its result explicitly supports that date, and do not invent "
                    "extra items to satisfy a requested count.",
                )
            result = ToolResult(
                name=self.name,
                content=wrap_untrusted("web search", "\n".join(lines)),
                # ``hits`` are the source chips; ``pages`` what the reply read, which the
                # turn keeps as its sources (``tool_loop.results``): a claim checked against
                # the chips' 280 characters looked unsupported when the page held it.
                data={"hits": sources_payload(shown), "pages": [asdict(hit) for hit in shown]},
            )
        ctx.first_results[self.name] = result
        return result
