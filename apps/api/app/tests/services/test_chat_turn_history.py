"""A next turn must build its context from the committed previous reply."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.exceptions import ChatBusyError
from app.services.chat import finalize_registry, stream
from app.tests.services.chat_test_support import FakeSessionCM


@pytest.mark.asyncio
async def test_next_turn_history_includes_pending_assistant_after_finalize():
    user = MagicMock(id=uuid4(), plan="free")
    chat_id = uuid4()
    chat = MagicMock(project_id=None, quiz_mode=None)
    committed = False
    recent = [
        SimpleNamespace(id=uuid4(), role="user", content="Name a city", model="free-chat"),
        SimpleNamespace(id=uuid4(), role="assistant", content="Paris", model="free-chat"),
    ]

    async def finish_previous_turn(*_args, **_kwargs):
        nonlocal committed
        await asyncio.sleep(0)
        committed = True

    async def read_recent(*_args, **_kwargs):
        return list(recent if committed else recent[:1])

    async def fake_stream(*_args, **_kwargs):
        yield "France"

    prepare = AsyncMock(return_value=MagicMock())
    with (
        patch("app.services.chat.stream.acquire_lock", AsyncMock(return_value="lock")),
        patch("app.services.chat.stream.refresh_lock", AsyncMock(return_value=True)),
        patch("app.services.chat.stream.release_lock", AsyncMock()),
        patch("app.services.chat.stream.wait_for_pending_finalize", finish_previous_turn),
        patch("app.services.chat.stream.SessionLocal", FakeSessionCM),
        patch("app.services.chat.stream.chats_repo.get_by_id", AsyncMock(return_value=chat)),
        patch("app.services.chat.stream.messages_repo.list_recent", read_recent),
        patch("app.services.chat.stream._try_image_gen_for_turn", AsyncMock(return_value=False)),
        patch("app.services.chat.stream.reserve_turn_quota", AsyncMock(return_value=100)),
        patch("app.services.chat.stream._top_up_reserve_for_prompt", AsyncMock()),
        patch("app.services.chat.stream.quota_service.daily_limit_for_user", return_value=100_000),
        patch(
            "app.services.chat.stream.plan_service.resolve_user_model_override",
            return_value="free-chat",
        ),
        patch("app.services.chat.stream.prepare_chat_turn", prepare),
        patch("app.services.chat.stream.await_user_message_persist", AsyncMock()),
        patch("app.services.chat.stream.stream_and_finalize", fake_stream),
    ):
        tokens = [
            token
            async for token in stream.stream_chat_response(
                AsyncMock(),
                Settings(_env_file=None),
                user_id=user.id,
                chat_id=chat_id,
                content="Which country is it in?",
                user=user,
                skip_usage_seed=True,
            )
        ]
    assert tokens == ["France"]
    assert prepare.await_args.kwargs["recent_messages"] == recent
    assert prepare.await_args.kwargs["prior_count"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["send", "regenerate"])
@pytest.mark.parametrize("finalize_owner", ["local", "remote"])
async def test_next_turn_rejects_busy_before_reading_uncommitted_history(
    fake_redis, action, finalize_owner
):
    user = MagicMock(id=uuid4(), plan="free")
    chat_id = uuid4()
    gate = asyncio.Event()
    finalize = asyncio.create_task(gate.wait())
    if finalize_owner == "local":
        finalize_registry.register_pending_finalize(chat_id, finalize)
    else:
        await finalize_registry.mark_pending_finalize(fake_redis, chat_id)
    premature_read = AsyncMock(side_effect=AssertionError("read history while finalize is pending"))
    reserve = AsyncMock()
    release = AsyncMock()
    try:
        with (
            patch("app.services.chat.finalize_registry._FINALIZE_WAIT_TIMEOUT_SECONDS", 0.01),
            patch("app.services.chat.finalize_registry._FINALIZE_POLL_INTERVAL_SECONDS", 0.001),
            patch("app.services.chat.stream.acquire_lock", AsyncMock(return_value="lock")),
            patch("app.services.chat.stream.release_lock", release),
            patch("app.services.chat.stream.SessionLocal", FakeSessionCM),
            patch("app.services.chat.stream.users_repo.get_by_id", AsyncMock(return_value=user)),
            patch(
                "app.services.chat.stream.chats_repo.get_by_id", AsyncMock(return_value=MagicMock())
            ),
            patch("app.services.chat.stream.messages_repo.list_recent", premature_read),
            patch("app.services.chat.stream.messages_repo.get_last", premature_read),
            patch("app.services.chat.stream.reserve_turn_quota", reserve),
        ):
            kwargs = {"user_id": user.id, "chat_id": chat_id}
            if action == "send":
                token_stream = stream.stream_chat_response(
                    fake_redis,
                    Settings(_env_file=None),
                    content="next",
                    user=user,
                    skip_usage_seed=True,
                    **kwargs,
                )
            else:
                token_stream = stream.stream_regenerate_response(
                    fake_redis,
                    Settings(_env_file=None),
                    **kwargs,
                )
            with pytest.raises(ChatBusyError):
                _ = [token async for token in token_stream]
            assert not finalize.done()
            premature_read.assert_not_awaited()
            reserve.assert_not_awaited()
            release.assert_awaited_once()
    finally:
        gate.set()
        await finalize
        await finalize_registry.clear_pending_finalize(fake_redis, chat_id)
