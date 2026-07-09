"""Web search MCP adapter."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.gateways import web_search_gateway
from app.gateways.mcp.base import ToolResult
from app.models.tool_schemas import WebSearchToolInput


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
        hits = await web_search_gateway.search_web(self.settings, query)
        if not hits:
            return ToolResult(name=self.name, content="No results.")
        lines = [f"- {hit.title}: {hit.url}\n  {hit.snippet}" for hit in hits[:5]]
        return ToolResult(name=self.name, content="\n".join(lines))
