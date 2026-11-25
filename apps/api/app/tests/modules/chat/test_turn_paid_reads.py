"""A turn's paid reads never outlive a turn that will not stream (audit, 2026-11-25).

The live read (two or three model calls) and the follow-up read started before the quota
reserve and outside the stream's ``finally``: a quota refusal, a prepare error or an
intercept's left them running, billed, for a turn that saved nothing. An at-cap send also
started them before it was refused.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.exceptions import QuotaExceededError
from app.modules.chat import stream_entry, turn_decision, turn_load
from app.modules.conversation import chats_repository, messages_repository
from app.services import quota as quota_service
from app.tests.fakes import make_user
from app.tests.modules.chat.chat_test_support import FakeSessionCM, turn_deps


@contextmanager
def _turn_load():
    chat = MagicMock()
    chat.summary = None
    with (
        patch.object(chats_repository, "get_by_id", AsyncMock(return_value=chat)),
        patch.object(messages_repository, "list_recent", AsyncMock(return_value=[])),
        patch.object(messages_repository, "count_for_chat", AsyncMock(return_value=0)),
        patch.object(turn_load, "wait_for_pending_finalize", AsyncMock()),
    ):
        yield


def _deps() -> Any:
    return turn_deps(
        session_factory=FakeSessionCM,
        model_choice={"resolve_user_model_override": MagicMock(return_value="free-chat")},
        locks={"acquire_lock": AsyncMock(return_value="tok"), "release_lock": AsyncMock()},
    )


class _Reads:
    """The turn's reads as started: a live read that runs until cancelled, and the posed
    read's start and stop."""

    def __init__(self) -> None:
        self.live: asyncio.Task[Any] | None = None
        self.start = MagicMock(side_effect=self._start)
        self.posed_started = MagicMock()
        self.posed_stopped = MagicMock()

    def _start(self, *_args: Any, **_kwargs: Any) -> asyncio.Task[Any]:
        self.live = asyncio.ensure_future(asyncio.sleep(30))
        return self.live


@contextmanager
def _watched_reads():
    reads = _Reads()
    with (
        patch.object(turn_decision, "start_turn_decision", reads.start),
        patch.object(stream_entry, "start_posed_read", reads.posed_started),
        patch.object(stream_entry, "stop_posed_read", reads.posed_stopped),
    ):
        yield reads


async def _send(deps: Any, fake_redis: Any, user: Any, content: str) -> list[str]:
    return [
        token
        async for token in stream_entry.stream_chat_response(
            deps,
            fake_redis,
            Settings(),
            user_id=user.id,
            chat_id=uuid4(),
            content=content,
            user=user,
            skip_usage_seed=True,
        )
    ]


async def _spend_the_day(fake_redis: Any, user: Any) -> None:
    for _ in range(quota_service.daily_message_limit(user, Settings())):
        assert await quota_service.reserve_message(fake_redis, user, Settings()) is not None


async def test_an_at_cap_send_is_refused_before_any_paid_read(fake_redis: Any) -> None:
    user = make_user(plan="free")
    await _spend_the_day(fake_redis, user)
    with _turn_load(), _watched_reads() as reads, pytest.raises(QuotaExceededError):
        await _send(_deps(), fake_redis, user, "what's a good name for a cat?")
    reads.start.assert_not_called()
    reads.posed_started.assert_not_called()


async def test_an_at_cap_picture_still_reaches_the_intercept(fake_redis: Any) -> None:
    """A painted picture takes no chat message: at the cap the read still decides it."""
    user = make_user(plan="free")
    await _spend_the_day(fake_redis, user)
    with (
        _turn_load(),
        _watched_reads() as reads,
        patch.object(stream_entry, "intercept_new_turn", AsyncMock(return_value=True)),
    ):
        assert await _send(_deps(), fake_redis, user, "draw a cat wearing a hat") == []
    reads.start.assert_called_once()


@pytest.mark.parametrize("failure", ["quota", "prepare", "intercept"])
async def test_a_turn_that_fails_before_its_reply_stops_its_reads(
    fake_redis: Any, failure: str
) -> None:
    user = make_user(plan="free")
    errors = {
        "quota": QuotaExceededError("Daily limit reached."),
        "prepare": RuntimeError("prepare failed"),
        "intercept": RuntimeError("intercept failed"),
    }
    raising = AsyncMock(side_effect=errors[failure])
    # The quota refuses as the deps' own reserve does: no message left to take.
    deps = turn_deps(
        session_factory=FakeSessionCM,
        model_choice={"resolve_user_model_override": MagicMock(return_value="free-chat")},
        locks={"acquire_lock": AsyncMock(return_value="tok"), "release_lock": AsyncMock()},
        quota={"reserve_message": AsyncMock(return_value=None)} if failure == "quota" else {},
    )
    with (
        _turn_load(),
        _watched_reads() as reads,
        patch.object(
            stream_entry,
            "intercept_new_turn",
            raising if failure == "intercept" else AsyncMock(return_value=False),
        ),
        patch.object(
            stream_entry,
            "prepare_chat_turn",
            raising if failure == "prepare" else AsyncMock(return_value=MagicMock()),
        ),
        pytest.raises(type(errors[failure])),
    ):
        await _send(deps, fake_redis, user, "what's a good name for a cat?")
    assert reads.live is not None
    await asyncio.sleep(0)
    assert reads.live.cancelled()
    reads.posed_stopped.assert_called()


async def test_an_intercepted_turn_stops_its_follow_up_read(fake_redis: Any) -> None:
    user = make_user(plan="free")
    with (
        _turn_load(),
        _watched_reads() as reads,
        patch.object(stream_entry, "intercept_new_turn", AsyncMock(return_value=True)),
    ):
        await _send(_deps(), fake_redis, user, "show me a red panda")
    reads.posed_stopped.assert_called_once()


async def test_a_refused_top_up_stops_the_reads_and_the_figure(fake_redis: Any) -> None:
    """The prompt's top-up is a quota check too: refused there, the reads and the figure,
    chart and formal reads begun beside the reply all stop."""
    user = make_user(plan="free")
    stopped = MagicMock()
    with (
        _turn_load(),
        _watched_reads() as reads,
        patch.object(stream_entry, "intercept_new_turn", AsyncMock(return_value=False)),
        patch.object(stream_entry, "prepare_chat_turn", AsyncMock(return_value=MagicMock())),
        patch.object(stream_entry, "start_figure", MagicMock(return_value=None)),
        patch.object(stream_entry, "start_chart", MagicMock(return_value=None)),
        patch.object(stream_entry, "start_formal", MagicMock(return_value=None)),
        patch.object(stream_entry, "start_reply_picture", MagicMock(return_value=None)),
        patch.object(stream_entry, "stop_figure", stopped),
        patch.object(
            stream_entry,
            "top_up_reserve_for_prompt",
            AsyncMock(side_effect=QuotaExceededError("Daily limit reached.")),
        ),
        pytest.raises(QuotaExceededError),
    ):
        await _send(_deps(), fake_redis, user, "what's a good name for a cat?")
    assert reads.live is not None
    await asyncio.sleep(0)
    assert reads.live.cancelled()
    stopped.assert_called_once()


@pytest.mark.parametrize("refused_at", ["reserve", "top_up"])
async def test_a_refused_regenerate_stops_its_reads(fake_redis: Any, refused_at: str) -> None:
    """A regenerate started its figure, chart and formal reads before its ``try``: a
    refused top-up left them running, as the reserve's refusal left the live read."""
    from types import SimpleNamespace

    from app.models.orm import Chat, User

    owner, chat_id = uuid4(), uuid4()
    window = [
        SimpleNamespace(id=uuid4(), role="user", content="name a cat", model=None),
        SimpleNamespace(id=uuid4(), role="assistant", content="Miso.", model="free-chat"),
    ]
    refusal = QuotaExceededError("Daily limit reached.")
    deps = turn_deps(
        session_factory=FakeSessionCM,
        users={"get_by_id": AsyncMock(return_value=User(id=owner, email="a@b.c", name="A"))},
        chats={"get_by_id": AsyncMock(return_value=Chat(id=chat_id, user_id=owner))},
        messages={
            "list_recent": AsyncMock(return_value=window),
            "count_for_chat": AsyncMock(return_value=len(window)),
        },
        model_choice={"resolve_regenerate_model": lambda *_args, **_kwargs: "free-chat"},
        locks={"acquire_lock": AsyncMock(return_value="tok"), "release_lock": AsyncMock()},
        quota={"reserve_message": AsyncMock(return_value=None)} if refused_at == "reserve" else {},
    )
    stopped = MagicMock()
    with (
        _watched_reads() as reads,
        patch.object(turn_load, "wait_for_pending_finalize", AsyncMock()),
        patch.object(stream_entry, "intercept_regenerate", AsyncMock(return_value=False)),
        patch.object(
            stream_entry, "build_stream_prompt_context", AsyncMock(return_value=MagicMock())
        ),
        patch.object(
            stream_entry, "stream_context_from_bundle", MagicMock(return_value=MagicMock())
        ),
        patch.object(stream_entry, "start_figure", MagicMock(return_value=None)),
        patch.object(stream_entry, "start_chart", MagicMock(return_value=None)),
        patch.object(stream_entry, "start_formal", MagicMock(return_value=None)),
        patch.object(stream_entry, "stop_figure", stopped),
        patch.object(stream_entry, "top_up_reserve_for_prompt", AsyncMock(side_effect=refusal)),
        pytest.raises(QuotaExceededError),
    ):
        async for _ in stream_entry.stream_regenerate_response(
            deps, fake_redis, Settings(), user_id=owner, chat_id=chat_id
        ):
            pass
    assert reads.live is not None
    await asyncio.sleep(0)
    assert reads.live.cancelled()
    assert stopped.called is (refused_at == "top_up")


@pytest.mark.parametrize(
    ("redone", "reads_start"), [("free-chat", False), ("image-gen-model", True)]
)
async def test_an_at_cap_regenerate_starts_no_paid_read(
    fake_redis: Any, redone: str, reads_start: bool
) -> None:
    """Review of #2590: a regenerate at 10/10 started its reads before ``reserve`` refused
    it. Now it is refused first, as a new turn is; a painted reply redone (it takes no chat
    message) still goes to the intercept, whose read decides."""
    from types import SimpleNamespace

    from app.models.orm import Chat

    user = make_user(plan="free")
    chat_id = uuid4()
    await _spend_the_day(fake_redis, user)
    window = [
        SimpleNamespace(id=uuid4(), role="user", content="a cat", model=None),
        SimpleNamespace(id=uuid4(), role="assistant", content="Miso.", model=redone),
    ]
    deps = turn_deps(
        session_factory=FakeSessionCM,
        users={"get_by_id": AsyncMock(return_value=user)},
        chats={"get_by_id": AsyncMock(return_value=Chat(id=chat_id, user_id=user.id))},
        messages={
            "list_recent": AsyncMock(return_value=window),
            "count_for_chat": AsyncMock(return_value=len(window)),
        },
        model_choice={"resolve_regenerate_model": lambda *_args, **_kwargs: "free-chat"},
        locks={"acquire_lock": AsyncMock(return_value="tok"), "release_lock": AsyncMock()},
    )
    with (
        _watched_reads() as reads,
        patch.object(turn_load, "wait_for_pending_finalize", AsyncMock()),
        patch.object(stream_entry, "intercept_regenerate", AsyncMock(return_value=True)),
    ):
        try:
            async for _ in stream_entry.stream_regenerate_response(
                deps, fake_redis, Settings(), user_id=user.id, chat_id=chat_id
            ):
                pass
            refused = False
        except QuotaExceededError:
            refused = True
    assert refused is not reads_start
    assert reads.start.called is reads_start
