import asyncio
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat.stream_entry import stream_chat_response
from app.tests.fakes import redis_mock
from app.tests.modules.chat.chat_test_support import FakeSessionCM, turn_deps


def _deps(*, load_user, load_chat, list_recent):
    return turn_deps(
        session_factory=FakeSessionCM,
        quota={
            "has_daily_usage_key": AsyncMock(return_value=True),
            "daily_limit_for_user": lambda _user, _settings: 100_000,
        },
        users={"get_by_id": load_user},
        chats={"get_by_id": load_chat},
        messages={"list_recent": list_recent, "count_for_chat": AsyncMock(return_value=0)},
        model_choice={"resolve_user_model_override": lambda *_args, **_kwargs: "free-chat"},
    )


def _held_resources() -> SimpleNamespace:
    return SimpleNamespace(
        reserved_tokens=0,
        refund=AsyncMock(),
        turn_left=AsyncMock(return_value=True),
        lock_key="lock",
        lock_token="token",
    )


@contextmanager
def _photo_turn(resources: SimpleNamespace, *, answered: bool = True) -> Iterator[None]:
    """The lock is held, the previous turn is saved, and a photo answers the turn (or,
    ``answered=False``, nothing intercepts it)."""

    @asynccontextmanager
    async def turn_resources(*_args, **_kwargs):
        yield resources

    with (
        patch("app.modules.chat.stream_entry.turn_resources", turn_resources),
        patch("app.modules.chat.turn_load.seed_usage_from_db", AsyncMock()),
        patch("app.modules.chat.turn_load.wait_for_pending_finalize", AsyncMock()),
        patch("app.modules.chat.stream_entry.intercept_new_turn", AsyncMock(return_value=answered)),
    ):
        yield


@pytest.mark.asyncio
async def test_history_load_overlaps_account_and_chat_load() -> None:
    """A remote history read must not sit behind the account/chat DB lane.

    The user lookup waits until list_recent has started. The old serial path
    deadlocks here; the parallel path reaches both lanes and completes.
    """
    history_started = asyncio.Event()

    async def load_user(_session, _user_id):
        await asyncio.wait_for(history_started.wait(), timeout=0.5)
        user = MagicMock()
        user.id = uuid4()
        user.plan = "pro"
        user.timezone = "UTC"
        user.default_model = "free-chat"
        user.memory_enabled = True
        return user

    chat = MagicMock()
    chat.id = uuid4()

    async def load_recent(_session, _chat_id, *, limit):
        _ = limit
        history_started.set()
        await asyncio.sleep(0)
        return []

    resources = _held_resources()
    deps = _deps(
        load_user=load_user, load_chat=AsyncMock(return_value=chat), list_recent=load_recent
    )
    with _photo_turn(resources):
        tokens = [
            token
            async for token in stream_chat_response(
                deps,
                redis_mock(),
                Settings(),
                user_id=uuid4(),
                chat_id=chat.id,
                content="What is the capital of France?",
            )
        ]

    assert tokens == []
    assert history_started.is_set()
    resources.refund.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_and_chat_ownership_loads_overlap() -> None:
    """User and chat DB lookups run concurrently on separate sessions."""
    user_started = asyncio.Event()
    chat_started = asyncio.Event()
    user_id = uuid4()
    chat_id = uuid4()

    user = MagicMock()
    user.id = user_id
    user.plan = "pro"
    user.timezone = "UTC"
    user.default_model = "free-chat"
    user.memory_enabled = True

    chat = MagicMock()
    chat.id = chat_id

    async def load_user(_session, _user_id):
        user_started.set()
        await asyncio.wait_for(chat_started.wait(), timeout=0.5)
        return user

    async def load_chat(_session, _chat_id, _user_id):
        chat_started.set()
        await asyncio.wait_for(user_started.wait(), timeout=0.5)
        return chat

    resources = _held_resources()
    deps = _deps(load_user=load_user, load_chat=load_chat, list_recent=AsyncMock(return_value=[]))
    with _photo_turn(resources):
        tokens = [
            token
            async for token in stream_chat_response(
                deps,
                redis_mock(),
                Settings(),
                user_id=user_id,
                chat_id=chat_id,
                content="hi",
            )
        ]

    assert tokens == []
    assert user_started.is_set()
    assert chat_started.is_set()
    resources.refund.assert_awaited_once()


@pytest.mark.asyncio
# A greeting sees what came before it, so a "hi" after a "hi" is noticed; a short
# reply answers the last turn: "no" to "Understood?" must see it.
@pytest.mark.parametrize("content", ["hi", "thanks", "No", "got it", "yes"])
async def test_every_turn_loads_the_recent_window(
    monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    user = MagicMock()
    user.id = uuid4()
    user.plan = "pro"
    user.timezone = "UTC"
    user.default_model = "free-chat"
    user.memory_enabled = True

    chat = MagicMock()
    chat.id = uuid4()

    prior = MagicMock(role="assistant", content="It's good to act even after a delay. Understood?")
    list_recent = AsyncMock(return_value=[prior])

    deps = _deps(
        load_user=AsyncMock(return_value=user),
        load_chat=AsyncMock(return_value=chat),
        list_recent=list_recent,
    )
    with _photo_turn(_held_resources()):
        tokens = [
            token
            async for token in stream_chat_response(
                deps,
                redis_mock(),
                Settings(),
                user_id=user.id,
                chat_id=chat.id,
                content=content,
            )
        ]

    assert tokens == []
    assert list_recent.await_count == 1


class _Prepared(Exception):
    """Raised by the stub prepare: the turn got as far as its prompt."""


@pytest.mark.asyncio
@pytest.mark.parametrize(("plan", "kept"), [("free", None), ("pro", "smart-chat")])
async def test_a_model_the_plan_dropped_reaches_the_prep_as_auto(
    monkeypatch: pytest.MonkeyPatch, plan: str, kept: str | None
) -> None:
    """A lapsed Pro's phone still names a Pro model: the whole turn runs as Auto (its
    routing, ``auto_routed`` and the photo lane), not only the model pick (review of #2596)."""
    from app.modules.chat import stream_entry

    user = MagicMock(id=uuid4(), plan=plan, timezone="UTC", memory_enabled=True)
    user.enabled_models = None
    chat = MagicMock(id=uuid4())
    seen: dict[str, object] = {}

    async def prepare(**kwargs: object) -> None:
        seen.update(kwargs)
        raise _Prepared

    monkeypatch.setattr(stream_entry, "prepare_chat_turn", prepare)
    monkeypatch.setattr(stream_entry, "_reserve_new_turn", AsyncMock(return_value=None))
    deps = _deps(
        load_user=AsyncMock(return_value=user),
        load_chat=AsyncMock(return_value=chat),
        list_recent=AsyncMock(return_value=[]),
    )
    resources = _held_resources()
    resources.search_budget = lambda *_args: None
    with _photo_turn(resources, answered=False), pytest.raises(_Prepared):
        async for _token in stream_chat_response(
            deps,
            redis_mock(),
            Settings(),
            user_id=user.id,
            chat_id=chat.id,
            content="hello",
            model_alias="smart-chat",
        ):
            pass

    assert seen["model_alias"] == kept


@pytest.mark.parametrize(("plan", "explicit"), [("free", False), ("pro", True)])
def test_a_regenerated_photo_with_a_dropped_model_takes_autos_photo_lane(
    monkeypatch: pytest.MonkeyPatch, plan: str, explicit: bool
) -> None:
    from app.modules.billing import plan as plan_service
    from app.modules.chat import stream_entry

    seen: dict[str, object] = {}

    def image_turn_model(_user: object, _settings: object, routed: str, **kwargs: object) -> str:
        seen.update(kwargs)
        return routed

    monkeypatch.setattr(plan_service, "image_turn_model", image_turn_model)
    turn = SimpleNamespace(
        content=f"What is this?\n[Image: /attachments/{uuid4()}/file]",
        model="free-chat",
        user=SimpleNamespace(plan=plan, enabled_models=None),
    )

    stream_entry._regenerate_images(turn, Settings(attachments_enabled=True), "smart-chat")  # type: ignore[arg-type]

    assert seen["explicit"] is explicit
