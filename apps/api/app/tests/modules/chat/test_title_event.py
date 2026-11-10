"""A new chat's title reaches the phone with its turn, or in one request: never by polling.

2026-11-08 feature test: the phone read ``GET /chats/{id}`` every two seconds after a new
chat's first reply until the topic job's title landed (47 reads in one run, two for one
chat). The job now announces the title; the turn's stream sends it after ``done``, and a
phone with no such stream asks once, with ``wait_for_title``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.modules.chat import title_event
from app.modules.chat.stream_events import DoneEvent, after_done_events
from app.modules.chat.turn_outcome import TurnOutcome
from app.tests.api_support import api_user, app_with_user
from app.tests.fakes import FakeSessionCM


def _redis() -> Any:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


# ── the announcement ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_await_title_returns_the_title_the_topic_job_announced() -> None:
    redis, chat_id = _redis(), uuid4()

    async def announce_later() -> None:
        await asyncio.sleep(0.05)
        await title_event.announce_title(redis, chat_id, "Sourdough starter basics")

    later = asyncio.create_task(announce_later())
    assert await title_event.await_title(redis, chat_id, within=2.0) == "Sourdough starter basics"
    await later


@pytest.mark.asyncio
async def test_await_title_gives_up_when_no_title_comes() -> None:
    assert await title_event.await_title(_redis(), uuid4(), within=0.05) is None


@pytest.mark.asyncio
async def test_a_redis_failure_reads_as_no_title_yet() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(side_effect=ConnectionError("redis down"))
    redis.set = AsyncMock(side_effect=ConnectionError("redis down"))
    await title_event.announce_title(redis, uuid4(), "Ignored")
    assert await title_event.await_title(redis, uuid4(), within=0.05) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("applied", [True, False])
async def test_the_topic_job_announces_only_a_title_it_applied(applied: bool) -> None:
    from app.modules.chat import titles

    redis, chat_id = _redis(), uuid4()
    with (
        patch.object(titles, "SessionLocal", side_effect=[FakeSessionCM(AsyncMock())]),
        patch.object(titles, "generate_title", AsyncMock(return_value="Bike chain fix")),
        patch(
            "app.modules.conversation.chats_repository.set_title_if_empty",
            AsyncMock(return_value=applied),
        ),
    ):
        await titles.generate_chat_title(
            Settings(),
            chat_id,
            "my bike chain keeps falling off",
            "Here is how",
            user_id=uuid4(),
            redis=redis,
        )
    expected = "Bike chain fix" if applied else None
    assert await title_event.await_title(redis, chat_id, within=0) == expected


# ── after done, on the turn's socket (one over a socket: test_client_message.py) ──


def test_done_says_a_title_follows_only_on_a_socket_after_a_saved_first_reply() -> None:
    first = TurnOutcome(message_id="reply", title_wait=lambda _wanted: _landed("Bike chain"))
    assert DoneEvent.from_outcome(first, title_follows=True).model_dump()["title_pending"] == "1"
    later = DoneEvent.from_outcome(TurnOutcome(message_id="reply"), title_follows=True)
    assert "title_pending" not in later.model_dump()
    # SSE ends with its done: the phone reads the title once.
    assert "title_pending" not in DoneEvent.from_outcome(first).model_dump()
    # A reply still saving: the phone reloads the chat, which brings the title.
    saving = DoneEvent.from_outcome(first, persisting=True, title_follows=True)
    assert "title_pending" not in saving.model_dump()


async def _landed(title: str | None) -> dict[str, Any]:
    return title_event.build_title_event(title)


@pytest.mark.asyncio
async def test_after_done_waits_for_the_title_only_on_a_socket() -> None:
    redis, chat_id = _redis(), uuid4()
    started: list[UUID] = []

    async def wait(wanted: Callable[[], bool]) -> dict[str, Any]:
        started.append(chat_id)
        return await title_event.title_event(redis, chat_id, wanted)

    await title_event.announce_title(redis, chat_id, "Lighthouse at sunset")
    first = TurnOutcome(message_id="reply", title_wait=wait)
    # SSE: no wait, and nothing was polled for it.
    assert [event async for event in after_done_events(first)] == []
    assert started == []
    events = [event async for event in after_done_events(first, title_wanted=lambda: True)]
    assert events == [{"type": "title", "title": "Lighthouse at sunset"}]


@pytest.mark.asyncio
async def test_after_done_says_when_no_title_came() -> None:
    with patch.object(title_event, "TITLE_WAIT_SECONDS", 0.05):
        first = TurnOutcome(
            message_id="reply", title_wait=partial(title_event.title_event, _redis(), uuid4())
        )
        events = [event async for event in after_done_events(first, title_wanted=lambda: True)]
    assert events == [{"type": "title", "title": None}]


@pytest.mark.asyncio
async def test_the_title_wait_ends_with_its_socket() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    # The phone closed the socket: the wait stops after its look, not 8 s later.
    assert await title_event.await_title(redis, uuid4(), wanted=lambda: False) is None
    assert redis.get.await_count == 1


# ── once, over HTTP ───────────────────────────────────────────────────────────


def _untitled_chat(chat_id: UUID) -> Any:
    from app.models.orm import Chat

    chat = MagicMock(spec=Chat)
    chat.id = chat_id
    chat.title = None
    chat.model = "free-chat"
    chat.pinned = False
    chat.archived = False
    chat.created_at = datetime(2026, 11, 8)
    chat.updated_at = datetime(2026, 11, 8)
    return chat


@pytest.mark.parametrize("wait", [True, False])
def test_get_chat_waits_for_a_new_chats_title_only_when_asked(wait: bool) -> None:
    from app.core.deps import get_redis

    chat_id, redis = uuid4(), _redis()
    app = app_with_user(api_user())
    app.dependency_overrides[get_redis] = lambda: redis

    async def announce_soon() -> None:
        await asyncio.sleep(0.1)
        await title_event.announce_title(redis, chat_id, "Picture of a red panda")

    async def read_chat(*_args: Any, **_kwargs: Any) -> Any:
        asyncio.get_running_loop().create_task(announce_soon())
        return _untitled_chat(chat_id)

    with patch("app.modules.conversation.chats_repository.get_by_id", read_chat):
        query = "?wait_for_title=true" if wait else ""
        response = TestClient(app).get(
            f"/chats/{chat_id}{query}", headers={"Authorization": "Bearer tok"}
        )
    assert response.status_code == 200
    assert response.json()["title"] == ("Picture of a red panda" if wait else None)


def test_get_chat_reads_the_row_again_when_no_title_was_announced() -> None:
    """The topic job wrote the title, but its announcement failed (Redis): the row has it."""
    from app.core.deps import get_redis

    chat_id = uuid4()
    titled = _untitled_chat(chat_id)
    titled.title = "Written, not announced"
    app = app_with_user(api_user())
    app.dependency_overrides[get_redis] = _redis
    reads = AsyncMock(side_effect=[_untitled_chat(chat_id), titled])
    with (
        patch("app.modules.conversation.chats_repository.get_by_id", reads),
        patch.object(title_event, "TITLE_WAIT_SECONDS", 0.05),
    ):
        response = TestClient(app).get(
            f"/chats/{chat_id}?wait_for_title=true", headers={"Authorization": "Bearer tok"}
        )
    assert response.status_code == 200
    assert response.json()["title"] == "Written, not announced"
    assert reads.await_count == 2
