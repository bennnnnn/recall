"""Tool-loop rounds, image tools, and per-user tool lists."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateways.mcp import registry as mcp_registry
from app.gateways.mcp.base import ToolResult
from app.gateways.web_search_gateway import WebSearchHit
from app.services import tool_loop

from .tool_loop_support import settings


def test_status_for_tool_omits_generic_thinking():
    assert tool_loop._status_for_tool("web_search") == "searching"
    assert tool_loop._status_for_tool("sympy") == "calculating"
    assert tool_loop._status_for_tool("generate_image") == "image_gen"
    assert tool_loop._status_for_tool("search_image") == "image_gen"
    assert tool_loop._status_for_tool("calendar") is None
    assert tool_loop._status_for_tool("") is None


def test_status_detail_for_tool_uses_query_for_search_image():
    assert (
        tool_loop._status_detail_for_tool("search_image", '{"query": "human ear"}') == "human ear"
    )
    assert tool_loop._status_detail_for_tool("generate_image", '{"prompt": "a fox"}') == "a fox"


@pytest.mark.asyncio
async def test_tool_loop_disabled_passthrough():
    messages = [{"role": "user", "content": "hi"}]
    out, verified, terminal, _hits = await tool_loop.run_tool_rounds(
        settings=settings(mcp_tool_loop_enabled=False),
        model_alias="free-chat",
        messages=messages,
        usage={},
    )
    assert out == messages
    assert verified is None
    assert terminal is None


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
        ]
    )
    invoke = AsyncMock(
        return_value=ToolResult(
            name="web_search",
            content="- Example: https://example.com\n  snippet",
            data={
                "hits": [
                    {
                        "title": "Example",
                        "url": "https://example.com",
                        "snippet": "snippet",
                    }
                ]
            },
        )
    )
    statuses: list[tuple[str, str | None]] = []

    async def on_status(phase: str, detail: str | None = None) -> None:
        statuses.append((phase, detail))

    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.services.tool_loop.mcp_registry.invoke_validated", invoke),
    ):
        out, verified, terminal, hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=3),
            model_alias="free-chat",
            messages=messages,
            usage=usage,
            on_status=on_status,
        )

    assert complete.await_count == 1
    invoke.assert_awaited_once()
    # The search query rides along as status detail for the client label.
    assert statuses == [("searching", "latest news")]
    assert any(m.get("role") == "tool" for m in out)
    assert any(m.get("role") == "assistant" and m.get("tool_calls") for m in out)
    assert verified is None
    assert terminal is None
    assert hits == [WebSearchHit(title="Example", url="https://example.com", snippet="snippet")]


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
            settings=settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=2),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )

    assert complete.await_count == 1
    assert invoke.await_count == 1


@pytest.mark.asyncio
async def test_tool_loop_caps_calls_per_round(web_search_registered):
    messages = [{"role": "user", "content": "search a lot"}]
    tool_calls = [
        {
            "id": f"c{i}",
            "type": "function",
            "function": {"name": "web_search", "arguments": '{"query": "x"}'},
        }
        for i in range(6)
    ]
    complete = AsyncMock(return_value={"content": None, "tool_calls": tool_calls})
    invoke = AsyncMock(return_value=MagicMock(content="ok", data=None))

    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.services.tool_loop.mcp_registry.invoke_validated", invoke),
    ):
        out, _verified, _terminal, _hits = await tool_loop.run_tool_rounds(
            settings=settings(
                mcp_tool_loop_enabled=True,
                mcp_tool_loop_max_calls_per_round=4,
            ),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )

    assert invoke.await_count == 4
    skipped = [m for m in out if m.get("content") == "Too many tool calls in one round."]
    assert len(skipped) == 2


@pytest.mark.asyncio
async def test_tool_loop_invoke_timeout_skips_remaining(web_search_registered):
    messages = [{"role": "user", "content": "search"}]
    tool_calls = [
        {
            "id": "c1",
            "type": "function",
            "function": {"name": "web_search", "arguments": '{"query": "a"}'},
        },
        {
            "id": "c2",
            "type": "function",
            "function": {"name": "web_search", "arguments": '{"query": "b"}'},
        },
    ]
    complete = AsyncMock(return_value={"content": None, "tool_calls": tool_calls})
    invoke = AsyncMock(return_value=MagicMock(content="ok", data=None))

    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.services.tool_loop.mcp_registry.invoke_validated", invoke),
        patch("app.services.tool_loop.time.monotonic", side_effect=[0.0, 0.0, 30.0]),
    ):
        out, _verified, _terminal, _hits = await tool_loop.run_tool_rounds(
            settings=settings(
                mcp_tool_loop_enabled=True,
                mcp_tool_loop_invoke_timeout_seconds=1.0,
            ),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )

    assert invoke.await_count == 1
    assert any(m.get("content") == "Tool round timed out." for m in out)


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
        _out, verified, terminal, _hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=3),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )

    assert verified is not None
    assert verified.canonical_fence == fence
    assert terminal is None


@pytest.mark.asyncio
async def test_tool_loop_cancel_mid_round_trims_unanswered_tool_calls(web_search_registered):
    """Stop after assistant tool_calls but before tool results → trim that turn."""
    messages = [{"role": "user", "content": "search news"}]
    complete = AsyncMock(
        return_value={
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": '{"query": "news"}'},
                },
                {
                    "id": "c2",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": '{"query": "more"}'},
                },
            ],
        }
    )
    # Round-start cancel check must pass; cancel on the first tool iteration
    # so the assistant tool_calls turn is recorded with zero tool replies.
    cancel_calls = {"n": 0}

    def should_cancel() -> bool:
        cancel_calls["n"] += 1
        return cancel_calls["n"] > 1

    invoke = AsyncMock(return_value=MagicMock(content="ok"))

    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.services.tool_loop.mcp_registry.invoke_validated", invoke),
    ):
        out, _verified, terminal, _hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=3),
            model_alias="free-chat",
            messages=messages,
            usage={},
            should_cancel=should_cancel,
        )

    complete.assert_awaited_once()
    invoke.assert_not_awaited()
    assert out == messages
    assert terminal is None
    assert not any(m.get("role") == "assistant" and m.get("tool_calls") for m in out)


def test_first_unanswered_assistant_idx_detects_partial_tools():
    msgs = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "tool_calls": [
                {"id": "a", "function": {"name": "web_search"}},
                {"id": "b", "function": {"name": "web_search"}},
            ],
        },
        {"role": "tool", "tool_call_id": "a", "content": "ok"},
    ]
    assert tool_loop._first_unanswered_assistant_idx(msgs) == 1
    msgs.append({"role": "tool", "tool_call_id": "b", "content": "ok"})
    assert tool_loop._first_unanswered_assistant_idx(msgs) is None


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


@pytest.mark.asyncio
async def test_tool_loop_generate_image_is_terminal():
    """Successful generate_image stops further completion rounds."""
    from app.gateways.mcp.base import ToolResult
    from app.modules.images.gen_tool import ImageGenAdapter

    mcp_registry.clear()
    mcp_registry.register(ImageGenAdapter(settings(image_generation_enabled=True)))
    try:
        messages = [{"role": "user", "content": "draw a watercolor fox"}]
        marker = "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]"
        complete = AsyncMock(
            return_value={
                "content": None,
                "tool_calls": [
                    {
                        "id": "img1",
                        "type": "function",
                        "function": {
                            "name": "generate_image",
                            "arguments": '{"prompt": "watercolor fox"}',
                        },
                    }
                ],
            }
        )
        invoke = AsyncMock(
            return_value=ToolResult(
                name="generate_image",
                content="ok",
                data={
                    "terminal": True,
                    "image_marker": marker,
                    "assistant_message_id": "01900000-0000-7000-8000-000000000001",
                    "resolved_model": "image-gen-model",
                },
            )
        )
        statuses: list[tuple[str, str | None]] = []

        async def on_status(phase: str, detail: str | None = None) -> None:
            statuses.append((phase, detail))

        pro_user = MagicMock()
        with (
            patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
            patch("app.services.tool_loop.mcp_registry.invoke_validated", invoke),
            patch("app.services.tool_loop.plan_service.is_pro", return_value=True),
        ):
            _out, verified, terminal, _hits = await tool_loop.run_tool_rounds(
                settings=settings(
                    mcp_tool_loop_enabled=True,
                    mcp_tool_loop_max_rounds=3,
                    image_generation_enabled=True,
                ),
                model_alias="free-chat",
                messages=messages,
                usage={},
                on_status=on_status,
                user=pro_user,
            )

        # One completion that requested the tool — no second "final answer" round.
        assert complete.await_count == 1
        invoke.assert_awaited_once()
        assert statuses == [("image_gen", "watercolor fox")]
        assert verified is None
        assert terminal is not None
        assert terminal.final_content == marker
        assert terminal.message_id == "01900000-0000-7000-8000-000000000001"
    finally:
        mcp_registry.clear()


@pytest.mark.asyncio
async def test_tool_loop_search_image_is_terminal():
    """Successful search_image (reference-photo lookup) stops further rounds."""
    from app.gateways.mcp.base import ToolResult
    from app.modules.images.search_tool import ImageSearchAdapter

    mcp_registry.clear()
    mcp_registry.register(ImageSearchAdapter(settings(image_search_enabled=True)))
    try:
        messages = [{"role": "user", "content": "show me an ear"}]
        marker = "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]"
        complete = AsyncMock(
            return_value={
                "content": None,
                "tool_calls": [
                    {
                        "id": "img1",
                        "type": "function",
                        "function": {
                            "name": "search_image",
                            "arguments": '{"query": "human ear"}',
                        },
                    }
                ],
            }
        )
        invoke = AsyncMock(
            return_value=ToolResult(
                name="search_image",
                content="ok",
                data={
                    "terminal": True,
                    "image_marker": marker,
                    "assistant_message_id": "01900000-0000-7000-8000-000000000002",
                    "resolved_model": "image-search-model",
                },
            )
        )
        statuses: list[tuple[str, str | None]] = []

        async def on_status(phase: str, detail: str | None = None) -> None:
            statuses.append((phase, detail))

        free_user = MagicMock()
        with (
            patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
            patch("app.services.tool_loop.mcp_registry.invoke_validated", invoke),
            patch("app.services.tool_loop.plan_service.is_pro", return_value=False),
        ):
            _out, verified, terminal, _hits = await tool_loop.run_tool_rounds(
                settings=settings(
                    mcp_tool_loop_enabled=True,
                    mcp_tool_loop_max_rounds=3,
                    image_search_enabled=True,
                ),
                model_alias="free-chat",
                messages=messages,
                usage={},
                on_status=on_status,
                user=free_user,
            )

        # Free users get the lookup tool even though generate_image is Pro-only.
        assert complete.await_count == 1
        invoke.assert_awaited_once()
        assert statuses == [("image_gen", "human ear")]
        assert verified is None
        assert terminal is not None
        assert terminal.final_content == marker
        assert terminal.message_id == "01900000-0000-7000-8000-000000000002"
    finally:
        mcp_registry.clear()


@pytest.mark.asyncio
async def test_tools_for_user_omits_image_gen_for_free():
    from app.modules.images.gen_tool import ImageGenAdapter

    mcp_registry.clear()
    mcp_registry.register(ImageGenAdapter(settings(image_generation_enabled=True)))
    try:
        with patch("app.services.tool_loop.plan_service.is_pro", return_value=False):
            tools = tool_loop._tools_for_user(settings(image_generation_enabled=True), MagicMock())
        names = [(t.get("function") or {}).get("name") for t in tools]
        assert "generate_image" not in names
    finally:
        mcp_registry.clear()


@pytest.mark.asyncio
async def test_tools_for_user_keeps_search_image_for_free():
    """Unlike generate_image, search_image is not Pro-gated."""
    from app.modules.images.search_tool import ImageSearchAdapter

    mcp_registry.clear()
    mcp_registry.register(ImageSearchAdapter(settings(image_search_enabled=True)))
    try:
        with patch("app.services.tool_loop.plan_service.is_pro", return_value=False):
            tools = tool_loop._tools_for_user(settings(image_search_enabled=True), MagicMock())
        names = [(t.get("function") or {}).get("name") for t in tools]
        assert "search_image" in names
    finally:
        mcp_registry.clear()


@pytest.mark.asyncio
async def test_tools_for_user_omits_search_image_when_disabled():
    from app.modules.images.search_tool import ImageSearchAdapter

    mcp_registry.clear()
    mcp_registry.register(ImageSearchAdapter(settings(image_search_enabled=True)))
    try:
        tools = tool_loop._tools_for_user(settings(image_search_enabled=False), MagicMock())
        names = [(t.get("function") or {}).get("name") for t in tools]
        assert "search_image" not in names
    finally:
        mcp_registry.clear()
