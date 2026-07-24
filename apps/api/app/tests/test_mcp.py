"""MCP adapter tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

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


@pytest.mark.asyncio
async def test_web_search_adapter_uses_cached_search_with_quota_context(fake_redis):
    """Model-initiated web_search must go through search_cache (Tavily quota)."""
    from app.gateways.mcp.web_search_adapter import bind_search_quota_context
    from app.gateways.web_search_gateway import WebSearchHit

    user = MagicMock()
    user.id = uuid4()
    adapter = WebSearchAdapter(Settings(web_search_enabled=True, mock_llm_enabled=True))
    hit = WebSearchHit(title="T", url="https://example.com", snippet="s")

    with (
        patch(
            "app.gateways.mcp.web_search_adapter.run_cached_search",
            AsyncMock(return_value=([hit], ["q"])),
        ) as cached,
        bind_search_quota_context(user=user, redis=fake_redis),
    ):
        result = await adapter.invoke({"query": "latest news"})

    cached.assert_awaited_once()
    assert cached.await_args.args[1] == ["latest news"]
    assert cached.await_args.kwargs["user"] is user
    assert cached.await_args.kwargs["redis"] is fake_redis
    assert result.content == "- T: https://example.com\n  s"


@pytest.mark.asyncio
async def test_web_search_adapter_does_not_call_gateway_directly():
    """Regression: adapter must not bypass quota via web_search_gateway.search_web."""
    adapter = WebSearchAdapter(Settings(web_search_enabled=True, mock_llm_enabled=True))
    with (
        patch(
            "app.gateways.mcp.web_search_adapter.run_cached_search",
            AsyncMock(return_value=([], ["q"])),
        ),
        patch("app.gateways.web_search_gateway.search_web", AsyncMock()) as direct,
    ):
        result = await adapter.invoke({"query": "anything"})
    direct.assert_not_awaited()
    assert result.content == "No results."


def test_mcp_registry_setup():
    setup_mcp_adapters(Settings())
    assert get("web_search") is not None
    assert get("calendar") is not None


def test_mcp_registry_sympy_absent_when_math_tools_disabled():
    """PR 5: math_tools_enabled=False must unregister the model-callable
    "sympy" MCP tool — without this gate, the model could still reach SymPy
    via the tool even when the operator disabled math_tools_enabled (which
    otherwise gates only the pre-stream augment_prompt_messages path)."""
    from app.gateways.mcp.registry import clear

    clear()
    setup_mcp_adapters(Settings(math_tools_enabled=False))
    assert get("sympy") is None

    clear()
    setup_mcp_adapters(Settings(math_tools_enabled=True))
    assert get("sympy") is not None


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
@pytest.mark.parametrize(
    "action, expr, variable, expected_result",
    [
        ("simplify", "x + x", "x", "2*x"),
        ("diff", "x**2", "x", "2*x"),
        ("integrate", "2*x", "x", "x**2"),
    ],
)
async def test_sympy_adapter_dispatches_simplify_diff_integrate(
    action, expr, variable, expected_result
):
    """BUG FIX: tool_schemas.py declared "simplify"/"diff"/"integrate" as
    valid actions, but invoke() had no branch for them — a model call with
    one of these actions fell through to the free-text intent-extraction
    fallback instead of calling the already-implemented math_service
    functions."""
    adapter = SympyAdapter(Settings())
    result = await adapter.invoke({"action": action, "expr": expr, "variable": variable})
    assert result.content == expected_result


@pytest.mark.asyncio
async def test_sympy_adapter_dispatches_parity_actions():
    """BUG FIX (math audit): the MCP tool surface was smaller than the heuristic
    path — system/limit/series/newton had no structured action, so the model
    couldn't call them directly. They now route to the existing verified
    math_service functions."""
    adapter = SympyAdapter(Settings())

    limit_res = await adapter.invoke(
        {"action": "limit", "expr": "sin(x)/x", "variable": "x", "point": "0"}
    )
    assert limit_res.content == "1"

    series_res = await adapter.invoke(
        {"action": "series", "expr": "x", "variable": "x", "start": "1", "end": "10"}
    )
    assert series_res.content == "55"

    newton_res = await adapter.invoke(
        {"action": "newton", "expr": "x**2 - 2", "variable": "x", "guess": 1.0}
    )
    assert "converged=True" in newton_res.content
    assert "1.41" in newton_res.content  # √2 ≈ 1.4142…

    system_res = await adapter.invoke(
        {
            "action": "system",
            "equations": [["x + y", "3"], ["x - y", "1"]],
            "variables": ["x", "y"],
        }
    )
    # x = 2, y = 1.
    assert "2" in system_res.content
    assert "1" in system_res.content


@pytest.mark.asyncio
async def test_sympy_adapter_simplify_times_out_instead_of_blocking(
    thread_sympy_executor: None,
):
    """Uses the in-process thread executor so the local ``_hang`` closure is
    callable (closures aren't picklable across a subprocess boundary). The
    production ProcessPoolSympyExecutor's hard-kill-on-timeout is exercised
    separately in test_sympy_executor.py."""
    settings = Settings(math_solve_timeout_seconds=0.05)
    adapter = SympyAdapter(settings)

    def _hang(expr, variable):
        import time

        time.sleep(1)
        raise AssertionError("should have been cancelled by the timeout")

    with patch(
        "app.gateways.mcp.sympy_adapter.math_service.simplify_expression", side_effect=_hang
    ):
        result = await asyncio.wait_for(
            adapter.invoke({"action": "simplify", "expr": "x + x", "variable": "x"}),
            timeout=5,
        )
    assert "timed out" in result.content


@pytest.mark.asyncio
async def test_sympy_adapter_solve_times_out_instead_of_blocking(
    monkeypatch: pytest.MonkeyPatch,
    thread_sympy_executor: None,
):
    """BUG FIX (was silent): this adapter used to call math_service directly,
    synchronously, with no timeout — unlike every chat-path caller. A hung
    expression must now time out instead of blocking the worker forever.

    Uses the in-process thread executor so the local ``_hang`` closure is
    callable (closures aren't picklable across a subprocess boundary)."""
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


@pytest.mark.asyncio
async def test_sympy_adapter_rectangle_includes_canonical_fence():
    adapter = SympyAdapter(Settings())
    result = await adapter.invoke({"action": "rectangle", "width": 8, "height": 5, "unit": "cm"})
    assert result.data is not None
    fence = result.data["canonical_fence"]
    assert fence["type"] == "rectangle"
    assert fence["width"] == 8.0
    assert fence["height"] == 5.0
    assert "```geometry" in result.content


@pytest.mark.asyncio
async def test_sympy_adapter_graph_includes_canonical_fence():
    adapter = SympyAdapter(Settings())
    result = await adapter.invoke({"action": "graph", "expr": "x**2", "x_min": -2, "x_max": 2})
    assert result.data is not None
    fence = result.data["canonical_fence"]
    assert fence["type"] == "function"
    assert fence["expr"] == "x**2"
    assert len(fence["points"]) >= 2
    assert "```graph" in result.content
