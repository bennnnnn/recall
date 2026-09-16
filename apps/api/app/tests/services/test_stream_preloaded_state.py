from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.preload import PreloadedChatTurnState
from app.services.chat.stream_entry import stream_chat_response


class _SessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *_args):
        return False


def _user() -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.plan = "pro"
    user.default_model = "gpt-5.5"
    user.timezone = "UTC"
    return user


def _chat() -> MagicMock:
    chat = MagicMock()
    chat.id = uuid4()
    chat.project_id = None
    chat.quiz_mode = None
    chat.summary = None
    return chat


def _seams(user, chat, *, db_user, db_chat, db_history):
    resources = SimpleNamespace(
        reserved_tokens=0,
        refund=AsyncMock(),
        lock_key="lock",
        lock_token="token",
    )

    @asynccontextmanager
    async def turn_resources(*_args, **_kwargs):
        yield resources

    return (
        SimpleNamespace(
            wrap_stream_status=lambda _timing, status: status,
            turn_resources=turn_resources,
            wait_for_pending_finalize=AsyncMock(),
            SessionLocal=_SessionCM,
            users_repo=SimpleNamespace(get_by_id=db_user),
            chats_repo=SimpleNamespace(get_by_id=db_chat),
            messages_repo=SimpleNamespace(
                list_recent=db_history,
                count_for_chat=AsyncMock(return_value=0),
            ),
            quota_service=SimpleNamespace(
                has_daily_usage_key=AsyncMock(return_value=True),
                daily_limit_for_user=lambda *_args: 100_000,
            ),
            seed_usage_from_db=AsyncMock(),
            plan_service=SimpleNamespace(
                resolve_user_model_override=lambda *_args, **_kwargs: "gpt-5.5"
            ),
            _try_image_lookup_for_turn=AsyncMock(return_value=True),
            _try_image_gen_for_turn=AsyncMock(return_value=False),
        ),
        resources,
    )


@pytest.mark.asyncio
async def test_valid_preload_skips_user_chat_and_history_db_reads() -> None:
    user = _user()
    chat = _chat()
    db_user = AsyncMock(return_value=user)
    db_chat = AsyncMock(return_value=chat)
    db_history = AsyncMock(return_value=[])
    seams, resources = _seams(
        user,
        chat,
        db_user=db_user,
        db_chat=db_chat,
        db_history=db_history,
    )
    state = PreloadedChatTurnState(
        user=user,
        chat=chat,
        recent_messages=[],
        prior_count=0,
        generation=7,
    )

    with patch(
        "app.services.chat.stream_entry.get_chat_generation",
        AsyncMock(return_value=7),
    ):
        tokens = [
            token
            async for token in stream_chat_response(
                seams,
                AsyncMock(),
                Settings(),
                user_id=user.id,
                chat_id=chat.id,
                content="hi",
                preloaded_state=state,
            )
        ]

    assert tokens == []
    db_user.assert_not_awaited()
    db_chat.assert_not_awaited()
    db_history.assert_not_awaited()
    resources.refund.assert_awaited_once()


@pytest.mark.asyncio
async def test_stale_preload_falls_back_to_fresh_db_reads() -> None:
    user = _user()
    chat = _chat()
    db_user = AsyncMock(return_value=user)
    db_chat = AsyncMock(return_value=chat)
    db_history = AsyncMock(return_value=[])
    seams, _resources = _seams(
        user,
        chat,
        db_user=db_user,
        db_chat=db_chat,
        db_history=db_history,
    )
    state = PreloadedChatTurnState(
        user=user,
        chat=chat,
        recent_messages=[],
        prior_count=0,
        generation=7,
    )

    with patch(
        "app.services.chat.stream_entry.get_chat_generation",
        AsyncMock(return_value=8),
    ):
        tokens = [
            token
            async for token in stream_chat_response(
                seams,
                AsyncMock(),
                Settings(),
                user_id=user.id,
                chat_id=chat.id,
                content="hi",
                preloaded_state=state,
            )
        ]

    assert tokens == []
    db_user.assert_awaited_once()
    db_chat.assert_awaited_once()
    db_history.assert_awaited_once()
