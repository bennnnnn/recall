from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.post_turn import enqueue_post_turn_jobs
from app.services.chat.turn_prep.context import StreamContext


def _ctx(*, prior_count: int, run_title: bool = True) -> StreamContext:
    user = MagicMock()
    user.memory_enabled = True
    return StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[],
        run_title=run_title,
        user_message_content="hello",
        reserved_tokens=10,
        max_output_tokens=100,
        assistant_message_id=uuid4(),
        skip_memory_jobs=False,
        prior_count=prior_count,
        user=user,
    )


@pytest.mark.asyncio
async def test_default_memory_interval_skips_turn_two():
    ctx = _ctx(prior_count=2)  # turn_number = 2
    with patch("app.core.jobs.enqueue", AsyncMock()) as enqueue:
        await enqueue_post_turn_jobs(
            AsyncMock(),
            Settings(history_compression_enabled=False, chat_history_rag_enabled=False),
            ctx,
            "ok",
        )
    assert [c.args[1] for c in enqueue.call_args_list] == ["topic"]


@pytest.mark.asyncio
async def test_default_memory_interval_runs_turn_three():
    ctx = _ctx(prior_count=4)  # turn_number = 3
    with patch("app.core.jobs.enqueue", AsyncMock()) as enqueue:
        await enqueue_post_turn_jobs(
            AsyncMock(),
            Settings(history_compression_enabled=False, chat_history_rag_enabled=False),
            ctx,
            "ok",
        )
    job_types = [c.args[1] for c in enqueue.call_args_list]
    assert "memory" in job_types
    memory_call = next(c for c in enqueue.call_args_list if c.args[1] == "memory")
    assert memory_call.kwargs["dedupe_key"] == f"memory:{ctx.assistant_message_id}"


@pytest.mark.asyncio
async def test_spend_cap_keeps_topic_drops_llm_jobs():
    ctx = _ctx(prior_count=0, run_title=True)  # turn 1 would enqueue memory
    with (
        patch("app.core.jobs.enqueue", AsyncMock()) as enqueue,
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=True)),
    ):
        await enqueue_post_turn_jobs(
            AsyncMock(),
            Settings(
                history_compression_enabled=True,
                chat_history_rag_enabled=True,
            ),
            ctx,
            "ok",
        )
    assert [c.args[1] for c in enqueue.call_args_list] == ["topic"]


@pytest.mark.asyncio
async def test_suggestions_job_has_user_dedupe_key():
    """The suggestions job must dedupe by user — the handler reads recent
    activity at run time, so a coalesced run covers the latest state and rapid
    turns at the % 10 boundary don't stack duplicate suggestion jobs."""
    ctx = _ctx(prior_count=10, run_title=False)  # turn 11; 11 % 3 != 0 (no memory)
    with patch("app.core.jobs.enqueue", AsyncMock()) as enqueue:
        await enqueue_post_turn_jobs(
            AsyncMock(),
            Settings(history_compression_enabled=False, chat_history_rag_enabled=False),
            ctx,
            "ok",
        )
    job_types = [c.args[1] for c in enqueue.call_args_list]
    assert "suggestions" in job_types
    suggestions_call = next(c for c in enqueue.call_args_list if c.args[1] == "suggestions")
    assert suggestions_call.kwargs["dedupe_key"] == f"suggestions:{ctx.user_id}"


@pytest.mark.asyncio
async def test_tool_loop_path_skips_when_spend_capped():
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
    ctx.prompt_messages = []
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=True)),
        patch("app.services.tool_loop.run_tool_rounds", AsyncMock()) as run,
    ):
        await _run_tool_loop_path(
            AsyncMock(),
            Settings(mcp_tool_loop_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    run.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_loop_path_skips_when_heuristic_math_already_verified():
    """Regression: PR #690 enabled the owned tool loop by default, which added
    up to 3 non-streaming OpenRouter round-trips (~24s) before the first token
    even when turn_prep's heuristic math already produced a verified fence.
    The loop's sympy/graph adapter is redundant in that case — skip it so math
    turns stay on the fast 1-call path. Ordinary non-tool turns skip the loop
    too (see turn_needs_tool_loop)."""
    from app.services.chat.stream import _run_tool_loop_path

    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_math = MagicMock()  # heuristic already produced a verified block
    ctx.user_id = uuid4()
    ctx.chat_id = uuid4()
    ctx.prompt_messages = []
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
        patch("app.services.tool_loop.run_tool_rounds", AsyncMock()) as run,
    ):
        await _run_tool_loop_path(
            AsyncMock(),
            Settings(mcp_tool_loop_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    run.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_loop_path_skips_ordinary_explain_turn():
    from app.services.chat.stream import _run_tool_loop_path

    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
    ctx.verified_math = None
    ctx.user_message_content = "Explain photosynthesis in two sentences."
    ctx.search_sources = []
    ctx.user = None
    ctx.user_id = uuid4()
    ctx.chat_id = uuid4()
    ctx.prompt_messages = []
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
        patch("app.services.tool_loop.run_tool_rounds", AsyncMock()) as run,
    ):
        await _run_tool_loop_path(
            AsyncMock(),
            Settings(mcp_tool_loop_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    run.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_loop_path_does_not_dump_leftover_as_instant_reply():
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
    ctx.prompt_messages = [{"role": "user", "content": "What's the latest news on SpaceX?"}]
    tool_messages = [
        *ctx.prompt_messages,
        {"role": "assistant", "tool_calls": [{"id": "c1"}]},
        {"role": "tool", "tool_call_id": "c1", "content": "hits"},
    ]
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
        patch(
            "app.services.tool_loop.run_tool_rounds",
            AsyncMock(return_value=(tool_messages, None, None, [])),
        ) as run,
    ):
        await _run_tool_loop_path(
            AsyncMock(),
            Settings(mcp_tool_loop_enabled=True),
            ctx,
            usage={},
            on_status=None,
            should_cancel=None,
        )
    run.assert_awaited_once()
    assert ctx.instant_reply is None
    assert ctx.prompt_messages == tool_messages
