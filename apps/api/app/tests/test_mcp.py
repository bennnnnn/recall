"""MCP adapter tests."""

import asyncio
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.gateways.mcp import setup_mcp_adapters
from app.gateways.mcp.registry import get
from app.gateways.mcp.sympy_adapter import SympyAdapter
from app.gateways.mcp.web_search_adapter import WebSearchAdapter


@pytest.mark.asyncio
async def test_web_search_adapter_missing_query():
    adapter = WebSearchAdapter(Settings())
    result = await adapter.invoke({})
    assert "Missing query" in result.content


def test_mcp_registry_setup():
    setup_mcp_adapters(Settings())
    assert get("web_search") is not None
    assert get("calendar") is not None


@pytest.mark.asyncio
async def test_sympy_adapter_rejects_rce_payload_via_solve():
    """The model can call this tool directly — it must not be a second,
    unguarded path to the same eval() gadget the direct math_service fix
    blocks (see test_math_service.py's parametrized RCE test)."""
    adapter = SympyAdapter(Settings())
    result = await adapter.invoke(
        {
            "action": "solve",
            "lhs": "x.__class__.__bases__[0].__subclasses__()[400]('id')",
            "rhs": "0",
            "variables": ["x"],
        }
    )
    assert "Math error" in result.content


@pytest.mark.asyncio
async def test_sympy_adapter_solve_times_out_instead_of_blocking(monkeypatch):
    """BUG FIX (was silent): this adapter used to call math_service directly,
    synchronously, with no timeout — unlike every chat-path caller. A hung
    expression must now time out instead of blocking the worker forever."""
    settings = Settings(math_solve_timeout_seconds=0.05)
    adapter = SympyAdapter(settings)

    def _hang(data):
        import time

        time.sleep(1)
        raise AssertionError("should have been cancelled by the timeout")

    with patch("app.gateways.mcp.sympy_adapter.math_service.solve_equation", side_effect=_hang):
        result = await asyncio.wait_for(
            adapter.invoke({"action": "solve", "lhs": "x", "rhs": "0", "variables": ["x"]}),
            timeout=5,
        )
    assert "timed out" in result.content
