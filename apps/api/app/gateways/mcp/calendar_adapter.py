"""Calendar MCP adapter — wraps calendar service actions."""

from __future__ import annotations

from typing import Any

from app.gateways.google_calendar_gateway import CalendarEvent
from app.gateways.mcp.base import ToolResult
from app.models.tool_schemas import CalendarConflictsInput
from app.services import calendar as calendar_service


def _parse_calendar_events(raw_events: object) -> list[CalendarEvent]:
    if not isinstance(raw_events, list):
        return []
    parsed: list[CalendarEvent] = []
    for raw in raw_events:
        if isinstance(raw, CalendarEvent):
            parsed.append(raw)
            continue
        if not isinstance(raw, dict):
            continue
        start_raw = raw.get("start")
        if not start_raw:
            continue
        try:
            start = calendar_service.datetime_from_iso(str(start_raw))
        except (TypeError, ValueError):
            continue
        end_raw = raw.get("end")
        end = None
        if end_raw:
            try:
                end = calendar_service.datetime_from_iso(str(end_raw))
            except (TypeError, ValueError):
                end = None
        parsed.append(
            CalendarEvent(
                id=str(raw.get("id") or ""),
                title=str(raw.get("title") or "Event"),
                start=start,
                end=end,
                location=str(raw.get("location") or "") or None,
                all_day=bool(raw.get("all_day")),
                calendar_name=str(raw.get("calendar_name") or "") or None,
            )
        )
    return parsed


class CalendarAdapter:
    name = "calendar"
    input_schema = CalendarConflictsInput

    def describe(self) -> str:
        return "List calendar conflicts or summarize scheduling context."

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.describe(),
                "parameters": CalendarConflictsInput.model_json_schema(),
            },
        }

    async def invoke(self, args: dict[str, Any]) -> ToolResult:
        action = str(args.get("action") or "conflicts")
        if action == "conflicts":
            events = _parse_calendar_events(args.get("events") or [])
            due_at = args.get("due_at")
            if not due_at:
                return ToolResult(name=self.name, content="Missing due_at.")
            conflicts = calendar_service.find_conflicting_events(
                events,
                calendar_service.datetime_from_iso(str(due_at)),
            )
            if not conflicts:
                return ToolResult(name=self.name, content="No conflicts.")
            lines = [f"- {e.title} at {e.start.isoformat()}" for e in conflicts]
            return ToolResult(name=self.name, content="\n".join(lines))
        return ToolResult(name=self.name, content=f"Unknown action: {action}")
