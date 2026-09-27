import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.stream_entry import stream_chat_response


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
        user.response_style = "balanced"
        user.memory_enabled = True
        return user

    chat = MagicMock()
    chat.id = uuid4()
    chat.project_id = None
    chat.quiz_mode = None

    async def load_recent(_session, _chat_id, *, limit):
        _ = limit
        history_started.set()
        await asyncio.sleep(0)
        return []

    class SessionCM:
        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, *_args):
            return False

    resources = SimpleNamespace(
        reserved_tokens=0,
        refund=AsyncMock(),
        lock_key="lock",
        lock_token="token",
    )

    @asynccontextmanager
    async def turn_resources(*_args, **_kwargs):
        yield resources

    seams = SimpleNamespace(
        wrap_stream_status=lambda _timing, status: status,
        turn_resources=turn_resources,
        quota_service=SimpleNamespace(
            has_daily_usage_key=AsyncMock(return_value=True),
            daily_limit_for_user=lambda _user, _settings: 100_000,
        ),
        SessionLocal=SessionCM,
        users_repo=SimpleNamespace(get_by_id=load_user),
        chats_repo=SimpleNamespace(get_by_id=AsyncMock(return_value=chat)),
        messages_repo=SimpleNamespace(
            list_recent=load_recent,
            count_for_chat=AsyncMock(return_value=0),
        ),
        seed_usage_from_db=AsyncMock(),
        wait_for_pending_finalize=AsyncMock(),
        plan_service=SimpleNamespace(
            resolve_user_model_override=lambda *_args, **_kwargs: "free-chat"
        ),
        _try_image_lookup_for_turn=AsyncMock(return_value=True),
        _try_image_gen_for_turn=AsyncMock(return_value=False),
    )

    tokens = [
        token
        async for token in stream_chat_response(
            seams,
            AsyncMock(),
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
    user.response_style = "balanced"
    user.memory_enabled = True

    chat = MagicMock()
    chat.id = chat_id
    chat.project_id = None
    chat.quiz_mode = None

    async def load_user(_session, _user_id):
        user_started.set()
        await asyncio.wait_for(chat_started.wait(), timeout=0.5)
        return user

    async def load_chat(_session, _chat_id, _user_id):
        chat_started.set()
        await asyncio.wait_for(user_started.wait(), timeout=0.5)
        return chat

    class SessionCM:
        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, *_args):
            return False

    resources = SimpleNamespace(
        reserved_tokens=0,
        refund=AsyncMock(),
        lock_key="lock",
        lock_token="token",
    )

    @asynccontextmanager
    async def turn_resources(*_args, **_kwargs):
        yield resources

    seams = SimpleNamespace(
        wrap_stream_status=lambda _timing, status: status,
        turn_resources=turn_resources,
        quota_service=SimpleNamespace(
            has_daily_usage_key=AsyncMock(return_value=True),
            daily_limit_for_user=lambda _user, _settings: 100_000,
        ),
        SessionLocal=SessionCM,
        users_repo=SimpleNamespace(get_by_id=load_user),
        chats_repo=SimpleNamespace(get_by_id=load_chat),
        messages_repo=SimpleNamespace(
            list_recent=AsyncMock(return_value=[]),
            count_for_chat=AsyncMock(return_value=0),
        ),
        seed_usage_from_db=AsyncMock(),
        wait_for_pending_finalize=AsyncMock(),
        plan_service=SimpleNamespace(
            resolve_user_model_override=lambda *_args, **_kwargs: "free-chat"
        ),
        _try_image_lookup_for_turn=AsyncMock(return_value=True),
        _try_image_gen_for_turn=AsyncMock(return_value=False),
    )

    tokens = [
        token
        async for token in stream_chat_response(
            seams,
            AsyncMock(),
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
@pytest.mark.parametrize(
    ("content", "loads_history"),
    [
        ("hi", False),
        ("thanks", False),
        # A short reply answers the last turn: "no" to "Understood?" must see it.
        ("No", True),
        ("got it", True),
        ("yes", True),
    ],
)
async def test_short_reply_loads_the_recent_window(
    monkeypatch: pytest.MonkeyPatch, content: str, loads_history: bool
) -> None:
    user = MagicMock()
    user.id = uuid4()
    user.plan = "pro"
    user.timezone = "UTC"
    user.default_model = "free-chat"
    user.response_style = "balanced"
    user.memory_enabled = True

    chat = MagicMock()
    chat.id = uuid4()
    chat.project_id = None
    chat.quiz_mode = None

    prior = MagicMock()
    prior.content = "It's good to act even after a delay. Understood?"
    monkeypatch.setattr(
        "app.services.chat.turn_prep.mode.messages_repo.get_last_assistant",
        AsyncMock(return_value=prior),
    )
    list_recent = AsyncMock(return_value=[])

    class SessionCM:
        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, *_args):
            return False

    resources = SimpleNamespace(
        reserved_tokens=0,
        refund=AsyncMock(),
        lock_key="lock",
        lock_token="token",
    )

    @asynccontextmanager
    async def turn_resources(*_args, **_kwargs):
        yield resources

    seams = SimpleNamespace(
        wrap_stream_status=lambda _timing, status: status,
        turn_resources=turn_resources,
        quota_service=SimpleNamespace(
            has_daily_usage_key=AsyncMock(return_value=True),
            daily_limit_for_user=lambda _user, _settings: 100_000,
        ),
        SessionLocal=SessionCM,
        users_repo=SimpleNamespace(get_by_id=AsyncMock(return_value=user)),
        chats_repo=SimpleNamespace(get_by_id=AsyncMock(return_value=chat)),
        messages_repo=SimpleNamespace(
            list_recent=list_recent,
            count_for_chat=AsyncMock(return_value=0),
        ),
        seed_usage_from_db=AsyncMock(),
        wait_for_pending_finalize=AsyncMock(),
        plan_service=SimpleNamespace(
            resolve_user_model_override=lambda *_args, **_kwargs: "free-chat"
        ),
        _try_image_lookup_for_turn=AsyncMock(return_value=True),
        _try_image_gen_for_turn=AsyncMock(return_value=False),
    )

    tokens = [
        token
        async for token in stream_chat_response(
            seams,
            AsyncMock(),
            Settings(),
            user_id=user.id,
            chat_id=chat.id,
            content=content,
        )
    ]

    assert tokens == []
    assert list_recent.await_count == (1 if loads_history else 0)
