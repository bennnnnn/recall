"""A reply cut off before its end owes no picture: the phone says it was cut off and offers
Continue, and the picture may come with the rest. A reply cut at the length limit is not a
cancelled one (``StreamAccum.mark_truncated``), so the owed-picture pass once saved "I
couldn't draw this graph." under the phone's cut-off note (finalize review, 2026-11-19)."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.modules.chat.owed_picture import not_drawn_line
from app.modules.chat.stream_pipeline import stream_and_finalize
from app.modules.chat.turn_outcome import TurnOutcome
from app.tests.modules.chat.chat_test_support import offline_deps
from app.tests.modules.chat.test_owed_picture import _ctx, _decision

pytest_plugins = ("app.tests.modules.chat.chat_test_support",)

_LINE = "Draw the v-t graph of a car speeding up from rest to 20 m/s in 5 s."
_REPLY = "Here is the motion step by step.\n\nThe car starts at rest and its velocity rises"


async def _saved(fake_redis: Any, finish_reason: str) -> tuple[str, TurnOutcome]:
    """The reply a graph turn saves when its model ended with ``finish_reason``."""

    async def fake_stream(**kwargs: Any) -> Any:
        meta = kwargs.get("stream_meta")
        if isinstance(meta, dict):
            meta["finish_reason"] = finish_reason
        yield _REPLY

    finalize = AsyncMock()
    outcome = TurnOutcome()
    ctx = _ctx(_LINE, _decision("physics", "graph"), skip_memory_jobs=True)
    with ExitStack() as stack:
        stack.enter_context(
            patch("app.gateways.litellm_gateway.stream_chat_completion", fake_stream)
        )
        stack.enter_context(
            patch("app.modules.chat.stream_pipeline.finalize_stream_turn_db", finalize)
        )
        stack.enter_context(patch("app.repositories.users.get_by_id", AsyncMock(return_value=None)))
        async for _ in stream_and_finalize(
            offline_deps(),
            fake_redis,
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            ctx,
            should_cancel=None,
            outcome=outcome,
        ):
            pass
        if outcome.finalize_db_task is not None:
            await outcome.finalize_db_task
    return finalize.await_args.kwargs["assistant_text"], outcome


@pytest.mark.asyncio
@pytest.mark.parametrize("finish_reason", ["length", "max_tokens", "content_filter"])
async def test_a_reply_cut_off_owes_no_picture(
    fake_redis: Any, stream_offline_io: None, finish_reason: str
) -> None:
    saved, outcome = await _saved(fake_redis, finish_reason)
    assert outcome.completion == "interrupted"
    assert not_drawn_line("graph", "en") not in saved
    assert saved.startswith("Here is the motion step by step.")


@pytest.mark.asyncio
async def test_a_whole_reply_still_says_its_picture_was_not_drawn(
    fake_redis: Any, stream_offline_io: None
) -> None:
    saved, outcome = await _saved(fake_redis, "stop")
    assert outcome.completion is None
    assert saved.endswith(not_drawn_line("graph", "en") + "\n")
