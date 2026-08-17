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
async def test_tool_loop_path_skips_when_spend_capped():
    from app.services.chat.stream import _run_tool_loop_path

    ctx = MagicMock()
    ctx.instant_reply = None
    ctx.lightweight_turn = False
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
