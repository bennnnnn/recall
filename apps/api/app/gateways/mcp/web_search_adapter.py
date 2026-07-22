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
from app.models.tool_schemas import WebSearchToolInput
from app.services.web_search.search_cache import run_cached_search

# Request-scoped quota/cache identity for concurrent chat turns sharing the
# process-global adapter registry. Set by the tool loop before invoke().
_search_user: ContextVar[User | None] = ContextVar("mcp_web_search_user", default=None)
_search_redis: ContextVar[Redis | None] = ContextVar("mcp_web_search_redis", default=None)


@contextmanager
def bind_search_quota_context(
    *,
    user: User | None = None,
    redis: Redis | None = None,
) -> Iterator[None]:
    """Bind the calling turn's user/redis for Tavily quota + search cache."""
    token_user = _search_user.set(user)
    token_redis = _search_redis.set(redis)
    try:
        yield
    finally:
        _search_user.reset(token_user)
        _search_redis.reset(token_redis)


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
        # Same cache + per-user Tavily reservation as the heuristic search path
        # — model-initiated calls must not bypass the daily cap.
        hits, _tried = await run_cached_search(
            self.settings,
            [query],
            user=_search_user.get(),
            redis=_search_redis.get(),
        )
        if not hits:
            return ToolResult(name=self.name, content="No results.")
        lines = [f"- {hit.title}: {hit.url}\n  {hit.snippet}" for hit in hits[:5]]
        return ToolResult(name=self.name, content="\n".join(lines))
