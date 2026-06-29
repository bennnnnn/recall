"""Calendar MCP adapter — wraps calendar service actions."""

from __future__ import annotations

from typing import Any

from app.gateways.mcp.base import ToolResult
from app.services import calendar as calendar_service


class CalendarAdapter:
    name = "calendar"

    def describe(self) -> str:
        return "List calendar conflicts or summarize scheduling context."

    async def invoke(self, args: dict[str, Any]) -> ToolResult:
        action = str(args.get("action") or "conflicts")
        if action == "conflicts":
            events = args.get("events") or []
            due_at = args.get("due_at")
            if not due_at:
                return ToolResult(name=self.name, content="Missing due_at.")
            from app.services.calendar import datetime_from_iso

            conflicts = calendar_service.find_conflicting_events(
                events,
                datetime_from_iso(str(due_at)),
            )
            if not conflicts:
                return ToolResult(name=self.name, content="No conflicts.")
            lines = [f"- {e.title} at {e.start.isoformat()}" for e in conflicts]
            return ToolResult(name=self.name, content="\n".join(lines))
        return ToolResult(name=self.name, content=f"Unknown action: {action}")
