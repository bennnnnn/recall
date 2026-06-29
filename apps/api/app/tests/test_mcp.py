"""MCP adapter tests."""

import pytest

from app.core.config import Settings
from app.gateways.mcp.registry import get, invoke
from app.gateways.mcp.web_search_adapter import WebSearchAdapter
from app.gateways.mcp import setup_mcp_adapters


@pytest.mark.asyncio
async def test_web_search_adapter_missing_query():
    adapter = WebSearchAdapter(Settings())
    result = await adapter.invoke({})
    assert "Missing query" in result.content


def test_mcp_registry_setup():
    setup_mcp_adapters(Settings())
    assert get("web_search") is not None
    assert get("calendar") is not None
