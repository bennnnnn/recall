"""Tool adapter registry."""

from __future__ import annotations

from app.gateways.mcp.base import ToolAdapter, ToolResult

_REGISTRY: dict[str, ToolAdapter] = {}


def register(adapter: ToolAdapter) -> None:
    _REGISTRY[adapter.name] = adapter


def get(name: str) -> ToolAdapter | None:
    return _REGISTRY.get(name)


def list_adapters() -> list[ToolAdapter]:
    return list(_REGISTRY.values())


async def invoke(name: str, args: dict) -> ToolResult | None:
    adapter = get(name)
    if adapter is None:
        return None
    return await adapter.invoke(args)
