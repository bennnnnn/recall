"""The post-turn jobs: which ones a finished turn enqueues, in ``POST_TURN_JOBS`` order."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.core.config import Settings
from app.modules.chat import post_turn
from app.modules.chat.turn_prep import StreamContext
from app.tests.modules.chat.chat_test_support import FakeSessionCM

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
        "indexable_attachment_ids": ["a1", "a2"],
    }
    fields.update(overrides)
    return StreamContext(**fields)


async def _enqueued(ctx: StreamContext, *, spend_capped: bool = False) -> list[tuple[str, Any]]:
    calls: list[tuple[str, Any]] = []

    async def enqueue(_redis: object, name: str, payload: dict[str, str], dedupe_key=None):
        calls.append((name, dedupe_key))

    settings = Settings(
        reminder_proposals_enabled=False,
        history_compression_enabled=True,
        chat_history_rag_enabled=True,
    )
    with (
        patch("app.core.jobs.enqueue", enqueue),
        patch(
            "app.modules.chat.post_turn.quota_service.global_spend_exceeded",
            AsyncMock(return_value=spend_capped),
        ),
        patch("app.modules.chat.post_turn.SessionLocal", FakeSessionCM),
        patch(
            "app.modules.todos.build_todo_sync_transcript",
            AsyncMock(return_value="User: earlier\nAssistant: earlier"),
        ),
    ):
        await post_turn.enqueue_post_turn_jobs(AsyncMock(), settings, ctx, _REPLY)
    return calls


@pytest.mark.asyncio
async def test_post_turn_jobs_enqueue_in_declared_order() -> None:
    assert await _enqueued(_turn()) == [
        ("memory", f"memory:{_ASSISTANT}"),
        ("lesson_progress", f"lesson_progress:{_ASSISTANT}"),
        ("todos", f"todosync:{_CHAT}:{_ASSISTANT}"),
        ("topic", f"topic:{_CHAT}"),
        ("compress", f"compress:{_CHAT}"),
        ("attachment_index", f"attachment_index:a1:{_CHAT}"),
        ("attachment_index", f"attachment_index:a2:{_CHAT}"),
        ("message_index", f"message_index:{_ASSISTANT}"),
    ]


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
