"""Quota edge cases on the chat stream path (Kimi Mediums)."""

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat import stream as stream_module


class _FakeSessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return False


def _pro_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.default_model = "smart-chat"
    user.plan = "pro"
    return user


@contextmanager
def _turn_load():
    chat = MagicMock()
    chat.project_id = None
    chat.quiz_mode = None
    chat.summary = None
    with (
        patch("app.services.chat.stream.chats_repo.get_by_id", AsyncMock(return_value=chat)),
        patch("app.services.chat.stream.messages_repo.list_recent", AsyncMock(return_value=[])),
        patch("app.services.chat.stream.messages_repo.count_for_chat", AsyncMock(return_value=0)),
    ):
        yield


def _borrowed_resources(redis, user_id, chat_id, reserved: int) -> stream_module.TurnResources:
    """Resources already held by an outer turn (what regenerate hands down)."""
    return stream_module.TurnResources(
        redis=redis,
        user_id=user_id,
        chat_id=chat_id,
        lock_key=f"chatprep:{chat_id}",
        lock_token="test-token",
        reserved_tokens=reserved,
    )


@pytest.mark.asyncio
async def test_stream_chat_response_refunds_pre_reserved_on_image_gen():
    """Edit reserves before stream_chat_response; image-gen must refund that hold."""
    user = _pro_user()
    chat_id = uuid4()
    redis = AsyncMock()
    refund = AsyncMock()

    with (
        patch("app.services.chat.stream.SessionLocal", _FakeSessionCM),
        patch("app.services.chat.stream.wait_for_pending_finalize", AsyncMock()),
        _turn_load(),
        patch(
            "app.services.chat.stream.plan_service.resolve_user_model_override",
            return_value="smart-chat",
        ),
        patch(
            "app.services.chat.stream.quota_service.daily_limit_for_user",
            return_value=100_000,
        ),
        patch(
            "app.services.chat.stream._try_image_gen_for_turn",
            AsyncMock(return_value=True),
        ),
        patch("app.services.chat.stream.quota_service.refund_usage", refund),
    ):
        tokens = [
            t
            async for t in stream_module.stream_chat_response(
                redis,
                Settings(),
                user_id=user.id,
                chat_id=chat_id,
                content="draw a cat",
                resources=_borrowed_resources(redis, user.id, chat_id, 500),
                user=user,
                skip_usage_seed=True,
            )
        ]

    assert tokens == []
    refund.assert_awaited_once_with(redis, str(user.id), 500)


@pytest.mark.asyncio
async def test_stream_chat_response_refunds_on_cancelled_error():
    """Hard cancel (CancelledError) must refund — except Exception would miss it."""
    user = _pro_user()
    redis = AsyncMock()
    refund = AsyncMock()

    async def boom_stream(*_a, **_k):
        raise asyncio.CancelledError()
        yield  # pragma: no cover — make this an async generator

    with (
        patch("app.services.chat.stream.SessionLocal", _FakeSessionCM),
        patch("app.services.chat.stream.wait_for_pending_finalize", AsyncMock()),
        _turn_load(),
        patch(
            "app.services.chat.stream.plan_service.resolve_user_model_override",
            return_value="smart-chat",
        ),
        patch(
            "app.services.chat.stream.quota_service.daily_limit_for_user",
            return_value=100_000,
        ),
        patch(
            "app.services.chat.stream._try_image_gen_for_turn",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.services.chat.stream.prepare_chat_turn",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("app.services.chat.stream.stream_and_finalize", boom_stream),
        patch("app.services.chat.stream.quota_service.refund_usage", refund),
        # This turn owns its own lock + reservation (the plain message path).
        patch("app.services.chat.stream.acquire_lock", AsyncMock(return_value="tok")),
        patch("app.services.chat.stream.release_lock", AsyncMock()),
        patch("app.services.chat.stream.reserve_turn_quota", AsyncMock(return_value=250)),
    ):
        with pytest.raises(asyncio.CancelledError):
            async for _ in stream_module.stream_chat_response(
                redis,
                Settings(),
                user_id=user.id,
                chat_id=uuid4(),
                content="hi",
                user=user,
                skip_usage_seed=True,
            ):
                pass

    refund.assert_awaited_once_with(redis, str(user.id), 250)


@pytest.mark.asyncio
async def test_stream_chat_response_reserves_max_output_ceiling():
    user = _pro_user()
    user.response_style = "detailed"
    redis = AsyncMock()
    reserve = AsyncMock(return_value=3400)

    async def empty_stream(*_a, **_k):
        if False:
            yield ""

    with (
        patch("app.services.chat.stream.SessionLocal", _FakeSessionCM),
        patch("app.services.chat.stream.wait_for_pending_finalize", AsyncMock()),
        _turn_load(),
        patch(
            "app.services.chat.stream.plan_service.resolve_user_model_override",
            return_value="smart-chat",
        ),
        patch(
            "app.services.chat.stream.quota_service.daily_limit_for_user",
            return_value=100_000,
        ),
        patch(
            "app.services.chat.stream._try_image_gen_for_turn",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.services.chat.stream.prepare_chat_turn",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("app.services.chat.stream.stream_and_finalize", empty_stream),
        patch("app.services.chat.stream.acquire_lock", AsyncMock(return_value="tok")),
        patch("app.services.chat.stream.release_lock", AsyncMock()),
        patch("app.services.chat.stream.reserve_turn_quota", reserve),
    ):
        async for _ in stream_module.stream_chat_response(
            redis,
            Settings(max_output_tokens=1200),
            user_id=user.id,
            chat_id=uuid4(),
            content="hi",
            user=user,
            skip_usage_seed=True,
        ):
            pass

    # No style-based cap anymore — reserve against the single ceiling
    # (settings.max_output_tokens), regardless of response_style.
    assert reserve.await_args.kwargs["max_output"] == 1200


@pytest.mark.asyncio
async def test_prior_count_uses_recent_length_when_window_has_room():
    from app.services.chat.stream_entry import _prior_count_for_window

    count = AsyncMock(return_value=99)
    recent = [MagicMock(), MagicMock()]
    n = await _prior_count_for_window(
        recent,
        window=20,
        count_for_chat=count,
        session=AsyncMock(),
        chat_id=uuid4(),
    )
    assert n == 2
    count.assert_not_awaited()


@pytest.mark.asyncio
async def test_prior_count_queries_when_recent_window_is_full():
    from app.services.chat.stream_entry import _prior_count_for_window

    count = AsyncMock(return_value=40)
    recent = [MagicMock(), MagicMock()]
    n = await _prior_count_for_window(
        recent,
        window=2,
        count_for_chat=count,
        session=AsyncMock(),
        chat_id=uuid4(),
    )
    assert n == 40
    count.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_skips_count_when_recent_window_has_room():
    user = _pro_user()
    redis = AsyncMock()
    count = AsyncMock(return_value=99)

    async def fake_stream(*_a, **_k):
        yield "ok"

    chat = MagicMock()
    chat.project_id = None
    chat.quiz_mode = None
    chat.summary = None
    with (
        patch("app.services.chat.stream.acquire_lock", AsyncMock(return_value="tok")),
        patch("app.services.chat.stream.release_lock", AsyncMock()),
        patch("app.services.chat.stream.wait_for_pending_finalize", AsyncMock()),
        patch("app.services.chat.stream.SessionLocal", _FakeSessionCM),
        patch("app.services.chat.stream.chats_repo.get_by_id", AsyncMock(return_value=chat)),
        patch(
            "app.services.chat.stream.messages_repo.list_recent",
            AsyncMock(return_value=[MagicMock()]),
        ),
        patch("app.services.chat.stream.messages_repo.count_for_chat", count),
        patch(
            "app.services.chat.stream.plan_service.resolve_user_model_override",
            return_value="smart-chat",
        ),
        patch(
            "app.services.chat.stream.quota_service.daily_limit_for_user",
            return_value=100_000,
        ),
        patch("app.services.chat.stream._try_image_gen_for_turn", AsyncMock(return_value=False)),
        patch("app.services.chat.stream.prepare_chat_turn", AsyncMock(return_value=MagicMock())),
        patch("app.services.chat.stream.stream_and_finalize", fake_stream),
        patch("app.services.chat.stream.reserve_turn_quota", AsyncMock(return_value=100)),
    ):
        async for _ in stream_module.stream_chat_response(
            redis,
            Settings(),
            user_id=user.id,
            chat_id=uuid4(),
            content="hi",
            user=user,
            skip_usage_seed=True,
        ):
            pass

    count.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_counts_when_recent_window_is_full():
    user = _pro_user()
    redis = AsyncMock()
    count = AsyncMock(return_value=40)

    async def fake_stream(*_a, **_k):
        yield "ok"

    chat = MagicMock()
    chat.project_id = None
    chat.quiz_mode = None
    chat.summary = None
    with (
        patch("app.services.chat.stream.acquire_lock", AsyncMock(return_value="tok")),
        patch("app.services.chat.stream.release_lock", AsyncMock()),
        patch("app.services.chat.stream.wait_for_pending_finalize", AsyncMock()),
        patch("app.services.chat.stream.SessionLocal", _FakeSessionCM),
        patch("app.services.chat.stream.chats_repo.get_by_id", AsyncMock(return_value=chat)),
        patch(
            "app.services.chat.stream.messages_repo.list_recent",
            AsyncMock(return_value=[MagicMock(), MagicMock()]),
        ),
        patch("app.services.chat.stream.messages_repo.count_for_chat", count),
        patch(
            "app.services.chat.stream.plan_service.resolve_user_model_override",
            return_value="smart-chat",
        ),
        patch(
            "app.services.chat.stream.quota_service.daily_limit_for_user",
            return_value=100_000,
        ),
        patch("app.services.chat.stream._try_image_gen_for_turn", AsyncMock(return_value=False)),
        patch("app.services.chat.stream.prepare_chat_turn", AsyncMock(return_value=MagicMock())),
        patch("app.services.chat.stream.stream_and_finalize", fake_stream),
        patch("app.services.chat.stream.reserve_turn_quota", AsyncMock(return_value=100)),
    ):
        async for _ in stream_module.stream_chat_response(
            redis,
            Settings(recent_message_window=2),
            user_id=user.id,
            chat_id=uuid4(),
            content="hi",
            user=user,
            skip_usage_seed=True,
        ):
            pass

    count.assert_awaited_once()
