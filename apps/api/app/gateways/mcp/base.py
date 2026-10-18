"""MCP-style tool adapter base types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from redis.asyncio import Redis

if TYPE_CHECKING:
    # Type only: loading app.models.orm at run time would load product modules.
    from app.models.orm.user import User


@dataclass(frozen=True)
class ToolResult:
    name: str
    content: str
    data: dict[str, Any] | None = None


class TavilyBudget(Protocol):
    """One Tavily reservation for every web search in a turn.

    ``app.modules.web_search.TurnTavilyBudget`` implements it; this protocol lets
    a ``ToolContext`` carry it without the gateway importing a product module.
    """

    async def skip_tavily(self, redis: Redis) -> bool: ...


@dataclass(frozen=True, kw_only=True)
class ToolContext:
    """The turn a tool runs in, passed to every ``invoke`` with its arguments.

    The tool loop and live talk build one per turn. ``tavily_budget`` and
    ``first_results`` are shared by reference by every call in that turn.
    """

    user: User | None
    redis: Redis | None
    chat_id: UUID | None
    user_timezone: str | None
    # The user's own message (the prompt's last user turn), not the tool's arguments.
    user_query: str
    tavily_budget: TavilyBudget
    # A tool that runs once per turn keeps its first result here, by tool name.
    first_results: dict[str, ToolResult] = field(default_factory=dict)


class ToolAdapter(Protocol):
    name: str

    def describe(self) -> str: ...

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult: ...
