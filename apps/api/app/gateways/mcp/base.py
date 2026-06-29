"""MCP-style tool adapter base types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolResult:
    name: str
    content: str
    data: dict[str, Any] | None = None


class ToolAdapter(Protocol):
    name: str

    def describe(self) -> str: ...

    async def invoke(self, args: dict[str, Any]) -> ToolResult: ...
