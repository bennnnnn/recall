from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways.litellm_gateway import ModelUnavailableError
from app.gateways.mcp import registry as mcp_registry
from app.gateways.mcp.base import ToolResult
from app.gateways.web_search_gateway import WebSearchHit
from app.services import tool_loop
from app.services.mcp.web_search_adapter import WebSearchAdapter


def test_status_for_tool_omits_generic_thinking():
    assert tool_loop._status_for_tool("web_search") == "searching"
    assert tool_loop._status_for_tool("sympy") == "calculating"
    assert tool_loop._status_for_tool("generate_image") == "image_gen"
    assert tool_loop._status_for_tool("calendar") is None
    assert tool_loop._status_for_tool("") is None


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
    out, verified, terminal, _hits = await tool_loop.run_tool_rounds(
        settings=_settings(mcp_tool_loop_enabled=False),
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
            settings=_settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=3),
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
            settings=_settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=2),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )

    assert complete.await_count == 1
    assert invoke.await_count == 1


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
            settings=_settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=3),
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
            settings=_settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=3),
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
    from app.services.mcp.image_gen_adapter import ImageGenAdapter

    mcp_registry.clear()
    mcp_registry.register(ImageGenAdapter(_settings(image_generation_enabled=True)))
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
                settings=_settings(
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
async def test_tools_for_user_omits_image_gen_for_free():
    from app.services.mcp.image_gen_adapter import ImageGenAdapter

    mcp_registry.clear()
    mcp_registry.register(ImageGenAdapter(_settings(image_generation_enabled=True)))
    try:
        with patch("app.services.tool_loop.plan_service.is_pro", return_value=False):
            tools = tool_loop._tools_for_user(_settings(image_generation_enabled=True), MagicMock())
        names = [(t.get("function") or {}).get("name") for t in tools]
        assert "generate_image" not in names
    finally:
        mcp_registry.clear()


@pytest.mark.parametrize(
    ("text", "kwargs", "expected"),
    [
        ("Explain photosynthesis in two sentences.", {}, False),
        ("hi", {"lightweight": True}, False),
        ("What's the latest news on SpaceX?", {}, True),
        ("What's the latest news on SpaceX?", {"has_search_sources": True}, False),
        ("What's the latest news on SpaceX?", {"web_search": False}, False),
        ("Explain photosynthesis in two sentences.", {"web_search": True}, True),
        ("differentiate x^2", {}, True),
        ("differentiate x^2", {"has_verified_math": True}, False),
        ("schedule a meeting with Sam tomorrow at 3", {}, True),
    ],
)
def test_turn_needs_tool_loop_gates_ordinary_chat(text: str, kwargs: dict, expected: bool):
    assert (
        tool_loop.turn_needs_tool_loop(
            text,
            settings=_settings(mcp_tool_loop_enabled=True, math_tools_enabled=True),
            **kwargs,
        )
        is expected
    )


@pytest.mark.asyncio
async def test_tool_loop_no_tools_first_round_does_not_complete_twice(web_search_registered):
    """Probe found no tools — stream the answer; never complete_with_tools twice."""
    messages = [{"role": "user", "content": "search the latest news"}]
    complete = AsyncMock(return_value={"content": "Tokyo is the capital.", "tool_calls": []})
    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch(
            "app.services.web_search.search_cache.run_cached_search",
            AsyncMock(return_value=([], [])),
        ),
    ):
        out, verified, terminal, _hits = await tool_loop.run_tool_rounds(
            settings=_settings(mcp_tool_loop_enabled=True),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )
    assert verified is None
    assert terminal is None
    assert out == messages
    complete.assert_awaited_once()


def test_tool_loop_completion_alias_avoids_reasoning_models():
    assert tool_loop._tool_loop_completion_alias("smart-chat") == "free-chat"
    assert tool_loop._tool_loop_completion_alias("free-chat") == "free-chat"


@pytest.mark.asyncio
async def test_tool_loop_uses_fast_alias_for_smart_chat(web_search_registered):
    messages = [{"role": "user", "content": "search the latest news"}]
    complete = AsyncMock(return_value={"content": "ok", "tool_calls": []})
    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch(
            "app.services.web_search.search_cache.run_cached_search",
            AsyncMock(return_value=([], [])),
        ),
    ):
        await tool_loop.run_tool_rounds(
            settings=_settings(mcp_tool_loop_enabled=True),
            model_alias="smart-chat",
            messages=messages,
            usage={},
        )
    assert complete.await_args.kwargs["model_alias"] == "free-chat"


@pytest.mark.asyncio
async def test_tool_loop_model_unavailable_falls_through(web_search_registered):
    messages = [{"role": "user", "content": "search the latest news"}]
    complete = AsyncMock(
        side_effect=ModelUnavailableError("down", failed_alias="free-chat"),
    )
    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch(
            "app.services.web_search.search_cache.run_cached_search",
            AsyncMock(return_value=([], [])),
        ),
    ):
        out, verified, terminal, _hits = await tool_loop.run_tool_rounds(
            settings=_settings(mcp_tool_loop_enabled=True),
            model_alias="smart-chat",
            messages=messages,
            usage={},
        )
    assert out == messages
    assert verified is None
    assert terminal is None


@pytest.mark.asyncio
async def test_tool_loop_forces_search_when_model_skips_web_search(web_search_registered):
    messages = [{"role": "user", "content": "What's the latest news on SpaceX?"}]
    hit = WebSearchHit(title="SpaceX", url="https://example.com/sx", snippet="landed")
    complete = AsyncMock(return_value={"content": "I already know.", "tool_calls": []})
    forced = AsyncMock(return_value=([hit], ["What's the latest news on SpaceX?"]))
    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.services.web_search.search_cache.run_cached_search", forced),
    ):
        out, verified, terminal, hits = await tool_loop.run_tool_rounds(
            settings=_settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )
    complete.assert_awaited_once()
    forced.assert_awaited_once()
    assert hits == [hit]
    assert any(
        m.get("role") == "system"
        and "BEGIN UNTRUSTED CONTENT — web search" in str(m.get("content"))
        for m in out
    )
    assert verified is None
    assert terminal is None


@pytest.mark.asyncio
async def test_tool_loop_path_copies_tool_hits_onto_context():
    from uuid import uuid4

    from app.services.chat.stream import _run_tool_loop_path

    hit = WebSearchHit(title="T", url="https://example.com", snippet="s")
    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_math = None
    ctx.user_message_content = "What's the latest news on SpaceX?"
    ctx.search_sources = []
    ctx.user = None
    ctx.user_id = uuid4()
    ctx.chat_id = uuid4()
    ctx.prompt_messages = [{"role": "user", "content": ctx.user_message_content}]
    ctx.model = "free-chat"
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
        patch(
            "app.services.tool_loop.run_tool_rounds",
            AsyncMock(return_value=(ctx.prompt_messages, None, None, [hit])),
        ),
    ):
        await _run_tool_loop_path(
            AsyncMock(),
            _settings(mcp_tool_loop_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    assert ctx.search_sources == [hit]


@pytest.mark.asyncio
async def test_tool_loop_path_classifier_yes_when_heuristic_is_weak():
    from uuid import uuid4

    from app.services.chat.stream import _run_tool_loop_path

    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_math = None
    ctx.user_message_content = "Who is the CEO of Anthropic?"
    ctx.search_sources = []
    ctx.user = None
    ctx.user_id = uuid4()
    ctx.chat_id = uuid4()
    ctx.prompt_messages = [{"role": "user", "content": ctx.user_message_content}]
    ctx.model = "free-chat"
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
        patch(
            "app.services.tool_loop.run_tool_rounds",
            AsyncMock(return_value=(ctx.prompt_messages, None, None, [])),
        ) as run,
        patch(
            "app.services.web_search.detection.should_web_search",
            AsyncMock(return_value=True),
        ) as classify,
    ):
        await _run_tool_loop_path(
            AsyncMock(),
            _settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    classify.assert_awaited_once()
    run.assert_awaited_once()


@pytest.mark.asyncio
async def test_tool_loop_path_skips_classifier_when_heuristic_already_yes():
    from uuid import uuid4

    from app.services.chat.stream import _run_tool_loop_path

    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_math = None
    ctx.user_message_content = "What's the latest news on SpaceX?"
    ctx.search_sources = []
    ctx.user = None
    ctx.user_id = uuid4()
    ctx.chat_id = uuid4()
    ctx.prompt_messages = [{"role": "user", "content": ctx.user_message_content}]
    ctx.model = "free-chat"
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
        patch(
            "app.services.tool_loop.run_tool_rounds",
            AsyncMock(return_value=(ctx.prompt_messages, None, None, [])),
        ),
        patch(
            "app.services.web_search.detection.should_web_search",
            AsyncMock(side_effect=AssertionError("heuristic already yes")),
        ) as classify,
    ):
        await _run_tool_loop_path(
            AsyncMock(),
            _settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    classify.assert_not_awaited()
