from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways.mcp import registry as mcp_registry
from app.gateways.mcp.web_search_adapter import WebSearchAdapter
from app.services import tool_loop


def _settings(**kwargs: object) -> Settings:
    s = Settings()
    for key, value in kwargs.items():
        setattr(s, key, value)
    return s


@pytest.fixture
def web_search_registered():
    mcp_registry.clear()
    mcp_registry.register(WebSearchAdapter(_settings()))
    yield
    mcp_registry.clear()


@pytest.mark.asyncio
async def test_tool_loop_disabled_passthrough():
    messages = [{"role": "user", "content": "hi"}]
    out, verified = await tool_loop.run_tool_rounds(
        settings=_settings(mcp_tool_loop_enabled=False),
        model_alias="free-chat",
        messages=messages,
        usage={},
    )
    assert out == messages
    assert verified is None


@pytest.mark.asyncio
async def test_tool_loop_single_web_search_round(web_search_registered):
    messages = [{"role": "user", "content": "search the latest news"}]
    usage: dict[str, int] = {}

    complete = AsyncMock(
        side_effect=[
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query": "latest news"}',
                        },
                    }
                ],
            },
            {"content": "Here are the results.", "tool_calls": []},
        ]
    )
    invoke = AsyncMock(return_value=MagicMock(content="- Example: https://example.com\n  snippet"))
    statuses: list[str] = []

    async def on_status(phase: str) -> None:
        statuses.append(phase)

    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.services.tool_loop.mcp_registry.invoke_validated", invoke),
    ):
        out, verified = await tool_loop.run_tool_rounds(
            settings=_settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=3),
            model_alias="free-chat",
            messages=messages,
            usage=usage,
            on_status=on_status,
        )

    assert complete.await_count == 2
    invoke.assert_awaited_once()
    assert statuses == ["searching"]
    assert any(m.get("role") == "tool" for m in out)
    assert any(m.get("role") == "assistant" and m.get("tool_calls") for m in out)
    assert verified is None


@pytest.mark.asyncio
async def test_tool_loop_max_rounds(web_search_registered):
    messages = [{"role": "user", "content": "search forever"}]
    tool_call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "web_search", "arguments": '{"query": "x"}'},
    }
    complete = AsyncMock(
        return_value={"content": None, "tool_calls": [tool_call]},
    )
    invoke = AsyncMock(return_value=MagicMock(content="ok"))

    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.services.tool_loop.mcp_registry.invoke_validated", invoke),
    ):
        await tool_loop.run_tool_rounds(
            settings=_settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=2),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )

    assert complete.await_count == 2
    assert invoke.await_count == 2


@pytest.mark.asyncio
async def test_tool_loop_collects_sympy_canonical_fence(web_search_registered):
    """When sympy returns a diagram fence in ToolResult.data, surface it as
    VerifiedMathBlock so post-stream validate_math_fences can overwrite."""
    messages = [{"role": "user", "content": "graph y=x^2"}]
    fence = {
        "type": "function",
        "expr": "x**2",
        "variable": "x",
        "x_min": -10.0,
        "x_max": 10.0,
        "points": [[-1.0, 1.0], [0.0, 0.0], [1.0, 1.0]],
        "segments": [],
    }
    complete = AsyncMock(
        side_effect=[
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "s1",
                        "type": "function",
                        "function": {
                            "name": "sympy",
                            "arguments": '{"action": "graph", "expr": "x**2"}',
                        },
                    }
                ],
            },
            {"content": "plotted", "tool_calls": []},
        ]
    )
    invoke = AsyncMock(
        return_value=MagicMock(
            content="sampled",
            data={"canonical_fence": fence},
        )
    )

    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.services.tool_loop.mcp_registry.invoke_validated", invoke),
    ):
        _out, verified = await tool_loop.run_tool_rounds(
            settings=_settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=3),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )

    assert verified is not None
    assert verified.canonical_fence == fence


@pytest.mark.asyncio
async def test_invoke_validated_rejects_bad_json(web_search_registered):
    result = await mcp_registry.invoke_validated("web_search", "{not-json")
    assert result is not None
    assert "Invalid JSON" in result.content


@pytest.mark.asyncio
async def test_invoke_validated_rejects_empty_query(web_search_registered):
    result = await mcp_registry.invoke_validated("web_search", '{"query": ""}')
    assert result is not None
    assert "Invalid arguments" in result.content
