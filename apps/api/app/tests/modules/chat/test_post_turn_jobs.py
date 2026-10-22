"""The post-turn jobs: which ones a finished turn enqueues, in ``POST_TURN_JOBS`` order."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.core import jobs
from app.core.config import Settings
from app.core.jobs import worker
from app.modules.chat import post_turn
from app.modules.chat.turn_prep import StreamContext

_USER = UUID(int=1)
_CHAT = UUID(int=2)
_ASSISTANT = UUID(int=3)
# A lesson that also confirms a reminder: every job has a reason to run.
_REPLY = "I'll set a reminder for Call mom.\n\n### Lesson 2: Fractions\n\n```quiz\n{}\n```"


def _turn(**overrides: Any) -> StreamContext:
    fields: dict[str, Any] = {
        "user_id": _USER,
        "chat_id": _CHAT,
        "model": "free-chat",
        "prompt_messages": [],
        "run_title": True,
        "user_message_content": "remind me to call mom tomorrow",
        "reserved_tokens": 10,
        "max_output_tokens": 100,
        "user": SimpleNamespace(id=_USER, memory_enabled=True),
        "assistant_message_id": _ASSISTANT,
    }
    fields.update(overrides)
    return StreamContext(**fields)


async def _enqueued(ctx: StreamContext, *, spend_capped: bool = False) -> list[tuple[str, Any]]:
    calls: list[tuple[str, Any]] = []

    async def enqueue(_redis: object, name: str, payload: dict[str, str], dedupe_key=None):
        calls.append((name, dedupe_key))

    settings = Settings(history_compression_enabled=True, chat_history_rag_enabled=True)
    with (
        patch("app.core.jobs.enqueue", enqueue),
        patch(
            "app.modules.chat.post_turn.quota_service.global_spend_exceeded",
            AsyncMock(return_value=spend_capped),
        ),
    ):
        await post_turn.enqueue_post_turn_jobs(AsyncMock(), settings, ctx, _REPLY)
    return calls


@pytest.mark.asyncio
async def test_post_turn_jobs_enqueue_in_declared_order() -> None:
    enqueued = await _enqueued(_turn())
    compress = enqueued[3][1]
    assert compress.startswith(f"compress:{_CHAT}:")
    assert enqueued == [
        ("memory", f"memory:{_ASSISTANT}"),
        ("lesson_progress", f"lesson_progress:{_ASSISTANT}"),
        ("topic", f"topic:{_CHAT}"),
        ("compress", compress),
        # A turn's documents are not here: persist_user_turn queues them when the
        # user's message commits (test_turn_prep_persist.py).
        ("message_index", f"message_index:{_ASSISTANT}"),
    ]


@pytest.mark.asyncio
async def test_a_chat_is_compressed_again_after_its_first_run(fake_redis) -> None:
    # Turn 1's run folds nothing. A fixed key then marked compress done for 24 h, so the
    # later run with messages to fold was acknowledged without running.
    keys = [dict(await _enqueued(_turn()))["compress"] for _ in range(2)]
    runs: list[str] = []

    async def compress(_settings: Settings, _payload: dict[str, Any]) -> None:
        runs.append("ran")

    jobs.register("compress-each-turn", compress)
    await worker._ensure_group(fake_redis)
    for key in keys:
        fields = {"type": "compress-each-turn", "payload": "{}", "dedupe_key": key}
        entry = await fake_redis.xadd(jobs.JOBS_STREAM, fields)
        await worker._process_entries(fake_redis, Settings(), [(entry, fields)])
    assert runs == ["ran", "ran"]


@pytest.mark.asyncio
async def test_post_turn_jobs_under_the_spend_cap_keep_lesson_progress_and_the_title() -> None:
    assert [name for name, _key in await _enqueued(_turn(), spend_capped=True)] == [
        "lesson_progress",
        "topic",
    ]


@pytest.mark.asyncio
async def test_post_turn_jobs_key_a_turn_without_an_id_by_its_place() -> None:
    names = dict(await _enqueued(_turn(assistant_message_id=None, prior_count=4)))
    assert names["memory"] == "memory:prior4"
    assert "message_index" not in names
