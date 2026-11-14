"""An instant reply makes no model call: the turn's read stops there (MODEL-06), unless the
picture the question asks to see still waits for it."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.stream_paths import run_instant_reply_path
from app.modules.chat.turn_prep import StreamContext


def _ctx(**fields: Any) -> StreamContext:
    return StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "2 + 2"}],
        run_title=False,
        user_message_content="2 + 2",
        reserved_tokens=100,
        max_output_tokens=50,
        instant_reply="4",
        **fields,
    )


async def _reply(ctx: StreamContext) -> list[str]:
    return [
        token
        async for token in run_instant_reply_path(ctx, should_cancel=None, accum=StreamAccum())
    ]


@pytest.mark.asyncio
async def test_an_instant_reply_stops_the_read() -> None:
    read = asyncio.ensure_future(asyncio.sleep(30))
    ctx = _ctx()
    ctx.live_read = read
    assert await _reply(ctx) == ["4"]
    await asyncio.sleep(0)
    assert read.cancelled()


@pytest.mark.parametrize("waiting", ["figure", "reply_picture"])
@pytest.mark.asyncio
async def test_a_picture_waiting_for_the_read_keeps_it(waiting: str) -> None:
    read = asyncio.ensure_future(asyncio.sleep(30))
    ctx = _ctx()
    ctx.live_read = read
    setattr(ctx, waiting, object())
    try:
        assert await _reply(ctx) == ["4"]
        await asyncio.sleep(0)
        assert not read.done()
    finally:
        read.cancel()
