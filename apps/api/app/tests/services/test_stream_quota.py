"""Quota edge cases on the chat stream path (Kimi Mediums)."""

import asyncio
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


def _borrowed_resources(redis, user_id, chat_id, reserved: int) -> stream_module.TurnResources:
    """Resources already held by an outer turn (what stream_edit_response hands down)."""
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
