"""Web search MCP adapter."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways.mcp.base import ToolResult
from app.models.orm import User
from app.models.schemas.tools import WebSearchToolInput
from app.modules.web_search.formatting import sources_payload
from app.modules.web_search.query_builders import (
    anchor_news_query_to_today,
    filter_hits_to_today,
    is_current_news_request,
    is_news_today_request,
)
from app.modules.web_search.search_cache import bind_tavily_turn_budget, run_cached_search
from app.services.prompt_safety import wrap_untrusted

_COUNT_WORDS = {
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
}


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

# Request-scoped quota/cache identity for concurrent chat turns sharing the
# process-global adapter registry. Set by the tool loop before invoke().
_search_user: ContextVar[User | None] = ContextVar("mcp_web_search_user", default=None)
_search_redis: ContextVar[Redis | None] = ContextVar("mcp_web_search_redis", default=None)
_search_bound: ContextVar[bool] = ContextVar("mcp_web_search_bound", default=False)
_search_invoke_count: ContextVar[int] = ContextVar("mcp_web_search_invokes", default=0)
_search_last_result: ContextVar[ToolResult | None] = ContextVar("mcp_web_search_last", default=None)
_search_user_query: ContextVar[str | None] = ContextVar("mcp_web_search_query", default=None)
_search_user_timezone: ContextVar[str | None] = ContextVar("mcp_web_search_timezone", default=None)


@contextmanager
def bind_search_quota_context(
    *,
    user: User | None = None,
    redis: Redis | None = None,
    settings: Settings | None = None,
    query: str | None = None,
    user_timezone: str | None = None,
) -> Iterator[None]:
    """Bind the calling turn's user/redis and one Tavily budget for the turn."""
    token_user = _search_user.set(user)
    token_redis = _search_redis.set(redis)
    token_bound = _search_bound.set(True)
    token_count = _search_invoke_count.set(0)
    token_last = _search_last_result.set(None)
    token_query = _search_user_query.set(query)
    token_timezone = _search_user_timezone.set(user_timezone)
    try:
        if settings is not None:
            with bind_tavily_turn_budget(settings=settings, user=user):
                yield
        else:
            yield
    finally:
        _search_user.reset(token_user)
        _search_redis.reset(token_redis)
        _search_bound.reset(token_bound)
        _search_invoke_count.reset(token_count)
        _search_last_result.reset(token_last)
        _search_user_query.reset(token_query)
        _search_user_timezone.reset(token_timezone)


class WebSearchAdapter:
    name = "web_search"
    input_schema = WebSearchToolInput

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def describe(self) -> str:
        return "Search the web for current information."

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.describe(),
                "parameters": WebSearchToolInput.model_json_schema(),
            },
        }

    async def invoke(self, args: dict[str, Any]) -> ToolResult:
        query = str(args.get("query") or "").strip()
        if not query:
            return ToolResult(name=self.name, content="Missing query.")
        user_query = _search_user_query.get() or ""
        current_news = is_current_news_request(user_query)
        news_today = is_news_today_request(user_query)
        if current_news:
            query = anchor_news_query_to_today(query, _search_user_timezone.get())
        prior_count = _search_invoke_count.get()
        if _search_bound.get() and prior_count >= 1:
            last = _search_last_result.get()
            if last is not None:
                return last
            return ToolResult(name=self.name, content="Already searched this turn.")
        # Same cache + per-user Tavily reservation as the heuristic search path
        # — model-initiated calls must not bypass the daily cap.
        hits, _tried = await run_cached_search(
            self.settings,
            [query],
            user=_search_user.get(),
            redis=_search_redis.get(),
        )
        if news_today:
            hits = filter_hits_to_today(hits, _search_user_timezone.get())
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
            _search_invoke_count.set(prior_count + 1)
            _search_last_result.set(result)
            return result
        if not hits:
            content = "No results."
            if news_today:
                content = (
                    "No search result explicitly verified an item for the user's current "
                    "local date. Say that no same-day developments could be verified; do not "
                    "substitute older news or invent items."
                )
            result = ToolResult(name=self.name, content=content)
        else:
            shown = hits[:5]
            lines = [f"- {hit.title}: {hit.url}\n  {hit.snippet}" for hit in shown]
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
                data={"hits": sources_payload(shown)},
            )
        _search_invoke_count.set(prior_count + 1)
        _search_last_result.set(result)
        return result
