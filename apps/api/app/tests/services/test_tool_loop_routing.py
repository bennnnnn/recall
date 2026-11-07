"""When the tool loop runs; whether a turn searches is the model's call, never the loop's."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateways.litellm_gateway import ModelUnavailableError
from app.gateways.mcp.base import ToolResult
from app.gateways.web_search_gateway import WebSearchHit
from app.modules.chat import tool_loop
from app.modules.chat.tool_loop import rounds, text_calls
from app.tests.modules.chat.chat_test_support import turn_deps

from .tool_loop_support import settings


@pytest.mark.parametrize(
    ("text", "kwargs", "expected"),
    [
        ("Explain photosynthesis in two sentences.", {}, False),
        ("hi", {"lightweight": True}, False),
        # A search is the reply's own call: news alone never runs the loop.
        ("What's the latest news on SpaceX?", {}, False),
        ("What is going on", {}, False),
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
    messages = [{"role": "user", "content": "tell me about Lisbon"}]
    complete = AsyncMock(return_value={"content": "Tokyo is the capital.", "tool_calls": []})
    with patch("app.modules.chat.tool_loop.rounds.litellm_gateway.complete_with_tools", complete):
        out, verified, terminal, _hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True),
            messages=messages,
            usage={},
        )
    assert verified is None
    assert terminal is None
    assert out == messages
    complete.assert_awaited_once()


def test_tool_selectors_are_tool_capable_catalog_aliases():
    from app.models import model_catalog

    selectors = model_catalog.tool_selector_aliases()
    assert selectors[:2] == ("gpt-6-luna", "free-chat")
    assert all(model_catalog.get(alias).supports_tools for alias in selectors)
    # Two companies, so one provider's outage leaves the other.
    assert len({model_catalog.get(alias).provider for alias in selectors}) == len(selectors)


@pytest.mark.asyncio
async def test_tool_loop_uses_dedicated_alias_for_smart_chat(web_search_registered):
    messages = [{"role": "user", "content": "tell me about Lisbon"}]
    complete = AsyncMock(return_value={"content": "ok", "tool_calls": []})
    with (
        patch("app.modules.chat.tool_loop.rounds.litellm_gateway.complete_with_tools", complete),
        patch(
            "app.modules.chat.tool_loop.forced_search.run_cached_search",
            AsyncMock(return_value=([], [])),
        ),
    ):
        await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True),
            messages=messages,
            usage={},
        )
    assert complete.await_args.kwargs["model_alias"] == "gpt-6-luna"


def test_recovers_provider_text_function_call_only_for_offered_tool() -> None:
    tools = [
        {
            "type": "function",
            "function": {"name": "web_search", "parameters": {}},
        }
    ]
    calls = text_calls._tool_calls_from_text(
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
        text_calls._tool_calls_from_text(
            '!function_call:{"call":"calendar","arguments":{}}',
            tools,
        )
        == []
    )


@pytest.mark.asyncio
async def test_tool_loop_model_unavailable_falls_through(web_search_registered):
    messages = [{"role": "user", "content": "tell me about Lisbon"}]
    complete = AsyncMock(
        side_effect=ModelUnavailableError("down", failed_alias="free-chat"),
    )
    with patch("app.modules.chat.tool_loop.rounds.litellm_gateway.complete_with_tools", complete):
        out, verified, terminal, _hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True),
            messages=messages,
            usage={},
        )
    assert out == [*messages, rounds._tool_selection_unavailable_message()]
    assert verified is None
    assert terminal is None


@pytest.mark.asyncio
async def test_tool_loop_never_searches_when_the_model_does_not(web_search_registered):
    """A round whose model calls no tool searches nothing: the server never searches
    for it, whatever the words look like."""
    messages = [{"role": "user", "content": "differentiate x^2, and what's the latest news?"}]
    complete = AsyncMock(return_value={"content": "I already know.", "tool_calls": []})
    invoke = AsyncMock(side_effect=AssertionError("no tool was called"))
    with (
        patch("app.modules.chat.tool_loop.rounds.litellm_gateway.complete_with_tools", complete),
        patch("app.modules.chat.tool_loop.calls.mcp_registry.invoke_validated", invoke),
    ):
        out, verified, terminal, hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            messages=messages,
            usage={},
        )
    complete.assert_awaited_once()
    invoke.assert_not_awaited()
    assert hits == []
    assert out == messages
    assert verified is None
    assert terminal is None


@pytest.mark.asyncio
async def test_a_search_that_finds_nothing_says_so_to_the_reply(web_search_registered):
    # A math turn asks the model which tool to call; it may choose web_search.
    messages = [{"role": "user", "content": "differentiate x^2"}]
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
    with (
        patch("app.modules.chat.tool_loop.rounds.litellm_gateway.complete_with_tools", complete),
        patch("app.modules.chat.tool_loop.calls.mcp_registry.invoke_validated", invoke),
    ):
        out, _verified, _terminal, hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            messages=messages,
            usage={},
        )
    assert hits == []
    assert any(m.get("role") == "tool" and "(no results)" in str(m.get("content")) for m in out)


@pytest.mark.asyncio
async def test_tool_loop_path_copies_tool_hits_onto_context():
    from uuid import uuid4

    from app.modules.chat.stream_paths import run_tool_loop_path

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
    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=False)})
    with (
        patch("app.modules.chat.tool_loop.turn_needs_tool_loop", return_value=True),
        patch(
            "app.modules.chat.tool_loop.run_tool_rounds",
            AsyncMock(return_value=(ctx.prompt_messages, None, None, [hit])),
        ),
    ):
        await run_tool_loop_path(
            deps,
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

    from app.modules.chat.stream_paths import run_tool_loop_path
    from app.modules.chemistry.block import build_verified_chemistry
    from app.modules.chemistry.extract import extract_chemistry_intent
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
    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=False)})
    with (
        patch("app.modules.chat.tool_loop.turn_needs_tool_loop", return_value=True),
        patch(
            "app.modules.chat.tool_loop.run_tool_rounds",
            AsyncMock(return_value=(ctx.prompt_messages, tool_math, None, [])),
        ),
    ):
        await run_tool_loop_path(
            deps,
            AsyncMock(),
            settings(mcp_tool_loop_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    assert ctx.verified_subject is chemistry


@pytest.mark.parametrize(
    "content",
    ["What's the latest news on SpaceX?", "How many employees does Anthropic have?", "hi there"],
)
@pytest.mark.asyncio
async def test_a_turn_that_does_not_loop_offers_its_reply_the_search(
    web_search_registered, content: str
):
    """No word rule runs: the reply's model call carries web_search and decides."""
    from uuid import uuid4

    from app.modules.chat.stream_paths import run_tool_loop_path
    from app.modules.chat.tool_loop.reply_calls import offers_search

    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_subject = None
    ctx.user_message_content = content
    ctx.search_sources = []
    ctx.user = None
    ctx.user_id = uuid4()
    ctx.chat_id = uuid4()
    ctx.prompt_messages = [{"role": "user", "content": content}]
    ctx.model = "free-chat"
    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=False)})
    with patch(
        "app.modules.chat.tool_loop.run_tool_rounds",
        AsyncMock(side_effect=AssertionError("no tool loop for a search")),
    ):
        await run_tool_loop_path(
            deps,
            AsyncMock(),
            settings(
                mcp_tool_loop_enabled=True, web_search_enabled=True, reply_search_tool_enabled=True
            ),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    assert offers_search(ctx.reply_tools)


@pytest.mark.asyncio
async def test_tool_loop_path_skips_the_loop_when_spend_capped():
    from uuid import uuid4

    from app.modules.chat.stream_paths import run_tool_loop_path

    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_subject = None
    ctx.user_message_content = "How many employees does Anthropic have?"
    ctx.search_sources = []
    ctx.user = None
    ctx.user_id = uuid4()
    ctx.chat_id = uuid4()
    ctx.prompt_messages = [{"role": "user", "content": ctx.user_message_content}]
    ctx.model = "free-chat"
    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=True)})
    with patch(
        "app.modules.chat.tool_loop.run_tool_rounds",
        AsyncMock(side_effect=AssertionError("spend cap must skip tool loop")),
    ) as run:
        await run_tool_loop_path(
            deps,
            AsyncMock(),
            settings(mcp_tool_loop_enabled=True, web_search_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    run.assert_not_awaited()
