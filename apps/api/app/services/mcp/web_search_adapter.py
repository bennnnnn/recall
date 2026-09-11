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
from app.services.prompt_safety import wrap_untrusted
from app.services.web_search.formatting import sources_payload
from app.services.web_search.search_cache import bind_tavily_turn_budget, run_cached_search

# Request-scoped quota/cache identity for concurrent chat turns sharing the
# process-global adapter registry. Set by the tool loop before invoke().
_search_user: ContextVar[User | None] = ContextVar("mcp_web_search_user", default=None)
_search_redis: ContextVar[Redis | None] = ContextVar("mcp_web_search_redis", default=None)
_search_bound: ContextVar[bool] = ContextVar("mcp_web_search_bound", default=False)
_search_invoke_count: ContextVar[int] = ContextVar("mcp_web_search_invokes", default=0)
_search_last_result: ContextVar[ToolResult | None] = ContextVar("mcp_web_search_last", default=None)


@contextmanager
def bind_search_quota_context(
    *,
    user: User | None = None,
    redis: Redis | None = None,
    settings: Settings | None = None,
) -> Iterator[None]:
    """Bind the calling turn's user/redis and one Tavily budget for the turn."""
    token_user = _search_user.set(user)
    token_redis = _search_redis.set(redis)
    token_bound = _search_bound.set(True)
    token_count = _search_invoke_count.set(0)
    token_last = _search_last_result.set(None)
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
        if not hits:
            result = ToolResult(name=self.name, content="No results.")
        else:
            shown = hits[:5]
            lines = [f"- {hit.title}: {hit.url}\n  {hit.snippet}" for hit in shown]
            result = ToolResult(
                name=self.name,
                content=wrap_untrusted("web search", "\n".join(lines)),
                data={"hits": sources_payload(shown)},
            )
        _search_invoke_count.set(prior_count + 1)
        _search_last_result.set(result)
        return result
