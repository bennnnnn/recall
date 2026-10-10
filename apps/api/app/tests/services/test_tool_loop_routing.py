"""When the tool loop runs, and how forced search and classifiers behave."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateways.litellm_gateway import ModelUnavailableError
from app.gateways.mcp.base import ToolResult
from app.gateways.web_search_gateway import WebSearchHit
from app.services import tool_loop

from .tool_loop_support import settings


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
        (
            "graph y=x**2 and also solve 3x=9",
            {"has_verified_math": True},
            True,
        ),
        ("schedule a meeting with Sam tomorrow at 3", {}, False),
    ],
)
def test_turn_needs_tool_loop_gates_ordinary_chat(text: str, kwargs: dict, expected: bool):
    assert (
        tool_loop.turn_needs_tool_loop(
            text,
            settings=settings(mcp_tool_loop_enabled=True, math_tools_enabled=True),
            **kwargs,
        )
        is expected
    )


def test_turn_needs_tool_loop_image_lookup_needs_no_pro_user():
    """Reference-photo lookup is free-tier — unlike generate_image it needs no user/plan check."""
    assert (
        tool_loop.turn_needs_tool_loop(
            "show me an ear",
            settings=settings(
                mcp_tool_loop_enabled=True, math_tools_enabled=True, image_search_enabled=True
            ),
            user=None,
        )
        is True
    )


def test_turn_needs_tool_loop_image_lookup_respects_disabled_flag():
    assert (
        tool_loop.turn_needs_tool_loop(
            "show me an ear",
            settings=settings(
                mcp_tool_loop_enabled=True, math_tools_enabled=True, image_search_enabled=False
            ),
            user=None,
        )
        is False
    )


def test_turn_needs_tool_loop_draw_request_does_not_trigger_lookup_path():
    """'draw me a fox' is generation phrasing; only Pro users get the tool-loop nod for it."""
    assert (
        tool_loop.turn_needs_tool_loop(
            "draw me a fox",
            settings=settings(
                mcp_tool_loop_enabled=True,
                math_tools_enabled=True,
                image_search_enabled=True,
                image_generation_enabled=True,
            ),
            user=None,
        )
        is False
    )


@pytest.mark.asyncio
async def test_tool_loop_no_tools_first_round_does_not_complete_twice(web_search_registered):
    """Probe found no tools — stream the answer; never complete_with_tools twice."""
    messages = [{"role": "user", "content": "search the latest news"}]
    complete = AsyncMock(return_value={"content": "Tokyo is the capital.", "tool_calls": []})
    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch(
            "app.modules.web_search.search_cache.run_cached_search",
            AsyncMock(return_value=([], [])),
        ),
    ):
        out, verified, terminal, _hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )
    assert verified is None
    assert terminal is None
    assert out == messages
    complete.assert_awaited_once()


def test_tool_loop_completion_alias_uses_dedicated_tool_model():
    assert tool_loop._tool_loop_completion_alias("smart-chat") == "gemini-flash"
    assert tool_loop._tool_loop_completion_alias("free-chat") == "gemini-flash"


@pytest.mark.asyncio
async def test_tool_loop_uses_dedicated_alias_for_smart_chat(web_search_registered):
    messages = [{"role": "user", "content": "search the latest news"}]
    complete = AsyncMock(return_value={"content": "ok", "tool_calls": []})
    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch(
            "app.modules.web_search.search_cache.run_cached_search",
            AsyncMock(return_value=([], [])),
        ),
    ):
        await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True),
            model_alias="smart-chat",
            messages=messages,
            usage={},
        )
    assert complete.await_args.kwargs["model_alias"] == "gemini-flash"


def test_recovers_provider_text_function_call_only_for_offered_tool() -> None:
    tools = [
        {
            "type": "function",
            "function": {"name": "web_search", "parameters": {}},
        }
    ]
    calls = tool_loop._tool_calls_from_text(
        "Let me correct that.\n"
        '!function_call:{"call":"web_search","arguments":{"query":"latest news"}}',
        tools,
    )
    assert calls == [
        {
            "id": "text_web_search",
            "type": "function",
            "function": {
                "name": "web_search",
                "arguments": '{"query": "latest news"}',
            },
        }
    ]
    assert (
        tool_loop._tool_calls_from_text(
            '!function_call:{"call":"calendar","arguments":{}}',
            tools,
        )
        == []
    )


@pytest.mark.asyncio
async def test_tool_loop_model_unavailable_falls_through(web_search_registered):
    messages = [{"role": "user", "content": "search the latest news"}]
    complete = AsyncMock(
        side_effect=ModelUnavailableError("down", failed_alias="free-chat"),
    )
    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch(
            "app.modules.web_search.search_cache.run_cached_search",
            AsyncMock(return_value=([], [])),
        ),
    ):
        out, verified, terminal, _hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True),
            model_alias="smart-chat",
            messages=messages,
            usage={},
        )
    assert out == [*messages, tool_loop._tool_selection_unavailable_message()]
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
        patch("app.modules.web_search.search_cache.run_cached_search", forced),
    ):
        out, verified, terminal, hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
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
async def test_tool_loop_forces_search_when_classifier_required_and_heuristic_no(
    web_search_registered,
):
    from app.modules.web_search.detection import needs_web_search

    query = "Who is the CEO of Anthropic?"
    assert needs_web_search(query) is False
    messages = [{"role": "user", "content": query}]
    hit = WebSearchHit(title="CEO", url="https://example.com/ceo", snippet="Dario Amodei")
    complete = AsyncMock(return_value={"content": "I already know.", "tool_calls": []})
    forced = AsyncMock(return_value=([hit], [query]))
    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.modules.web_search.search_cache.run_cached_search", forced),
    ):
        out, verified, terminal, hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            model_alias="free-chat",
            messages=messages,
            usage={},
            web_search=True,
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
async def test_tool_loop_skips_force_search_when_not_required_and_heuristic_no(
    web_search_registered,
):
    from app.modules.web_search.detection import needs_web_search

    query = "Who is the CEO of Anthropic?"
    assert needs_web_search(query) is False
    messages = [{"role": "user", "content": query}]
    complete = AsyncMock(return_value={"content": "ok", "tool_calls": []})
    forced = AsyncMock(return_value=([], [query]))
    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.modules.web_search.search_cache.run_cached_search", forced),
    ):
        out, _verified, _terminal, hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )
    forced.assert_not_awaited()
    assert hits == []
    assert all("returned no usable results" not in str(m.get("content")) for m in out)


@pytest.mark.asyncio
async def test_tool_loop_injects_empty_search_when_force_finds_nothing(web_search_registered):
    messages = [{"role": "user", "content": "What's the latest news on SpaceX?"}]
    complete = AsyncMock(return_value={"content": "I already know.", "tool_calls": []})
    forced = AsyncMock(return_value=([], ["What's the latest news on SpaceX?"]))
    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.modules.web_search.search_cache.run_cached_search", forced),
    ):
        out, _verified, _terminal, hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )
    forced.assert_awaited_once()
    assert hits == []
    assert any(
        m.get("role") == "system" and "could not verify that live" in str(m.get("content"))
        for m in out
    )


@pytest.mark.asyncio
async def test_tool_loop_injects_empty_when_tool_returns_no_hits(web_search_registered):
    messages = [{"role": "user", "content": "What's the latest news on SpaceX?"}]
    complete = AsyncMock(
        return_value={
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": '{"query": "SpaceX"}'},
                }
            ],
        }
    )
    invoke = AsyncMock(
        return_value=ToolResult(name="web_search", content="(no results)", data={"hits": []})
    )
    forced = AsyncMock(return_value=([], ["What's the latest news on SpaceX?"]))
    with (
        patch("app.services.tool_loop.litellm_gateway.complete_with_tools", complete),
        patch("app.services.tool_loop.mcp_registry.invoke_validated", invoke),
        patch("app.modules.web_search.search_cache.run_cached_search", forced),
    ):
        out, _verified, _terminal, hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            model_alias="free-chat",
            messages=messages,
            usage={},
        )
    forced.assert_not_awaited()
    assert hits == []
    assert any(
        m.get("role") == "system" and "could not verify that live" in str(m.get("content"))
        for m in out
    )


@pytest.mark.asyncio
async def test_tool_loop_path_copies_tool_hits_onto_context():
    from uuid import uuid4

    from app.services.chat.stream import _run_tool_loop_path

    hit = WebSearchHit(title="T", url="https://example.com", snippet="s")
    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_subject = None
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
            settings(mcp_tool_loop_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    assert ctx.search_sources == [hit]


@pytest.mark.asyncio
async def test_tool_loop_keeps_a_chemistry_verified_block():
    from uuid import uuid4

    from app.modules.chemistry.block import build_verified_chemistry
    from app.modules.chemistry.extract import extract_chemistry_intent
    from app.services.chat.stream import _run_tool_loop_path
    from app.services.solving import VerifiedMathBlock

    intent = extract_chemistry_intent("Find the molar mass of H2O")
    assert intent is not None
    chemistry = build_verified_chemistry(intent)
    assert chemistry is not None
    tool_math = VerifiedMathBlock(
        text="verified",
        canonical_fence={"type": "answer", "content": "x = 2"},
        canonical_answer="x = 2",
    )
    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_subject = chemistry
    ctx.user_message_content = "Find the molar mass of H2O"
    ctx.search_sources = []
    ctx.user = None
    ctx.user_id = uuid4()
    ctx.chat_id = uuid4()
    ctx.prompt_messages = [{"role": "user", "content": ctx.user_message_content}]
    ctx.model = "free-chat"
    ctx.web_search_classified = None
    ctx.user_timezone = None
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
        patch("app.services.tool_loop.turn_needs_tool_loop", return_value=True),
        patch(
            "app.services.tool_loop.run_tool_rounds",
            AsyncMock(return_value=(ctx.prompt_messages, tool_math, None, [])),
        ),
    ):
        await _run_tool_loop_path(
            AsyncMock(),
            settings(mcp_tool_loop_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    assert ctx.verified_subject is chemistry


@pytest.mark.asyncio
async def test_tool_loop_path_classifier_yes_when_heuristic_is_weak():
    from uuid import uuid4

    from app.services.chat.stream import _run_tool_loop_path

    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_subject = None
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
            "app.modules.web_search.detection.should_web_search",
            AsyncMock(return_value=True),
        ) as classify,
    ):
        await _run_tool_loop_path(
            AsyncMock(),
            settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    classify.assert_awaited_once()
    run.assert_awaited_once()
    assert run.await_args.kwargs["web_search"] is True


@pytest.mark.asyncio
async def test_tool_loop_path_skips_classifier_when_heuristic_already_yes():
    from uuid import uuid4

    from app.services.chat.stream import _run_tool_loop_path

    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_subject = None
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
            "app.modules.web_search.detection.should_web_search",
            AsyncMock(side_effect=AssertionError("heuristic already yes")),
        ) as classify,
    ):
        await _run_tool_loop_path(
            AsyncMock(),
            settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_loop_path_skips_classifier_when_spend_capped():
    from uuid import uuid4

    from app.services.chat.stream import _run_tool_loop_path

    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_subject = None
    ctx.user_message_content = "Who is the CEO of Anthropic?"
    ctx.search_sources = []
    ctx.user = None
    ctx.user_id = uuid4()
    ctx.chat_id = uuid4()
    ctx.prompt_messages = [{"role": "user", "content": ctx.user_message_content}]
    ctx.model = "free-chat"
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=True)),
        patch(
            "app.modules.web_search.detection.should_web_search",
            AsyncMock(side_effect=AssertionError("spend cap must skip classifier")),
        ) as classify,
        patch(
            "app.services.tool_loop.run_tool_rounds",
            AsyncMock(side_effect=AssertionError("spend cap must skip tool loop")),
        ) as run,
    ):
        await _run_tool_loop_path(
            AsyncMock(),
            settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    classify.assert_not_awaited()
    run.assert_not_awaited()
