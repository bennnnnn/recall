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


@pytest.mark.asyncio
async def test_stream_chat_response_refunds_pre_reserved_on_image_gen():
    """Edit reserves before stream_chat_response; image-gen must refund that hold."""
    user = _pro_user()
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
                chat_id=uuid4(),
                content="draw a cat",
                pre_reserved=500,
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
    ):
        with pytest.raises(asyncio.CancelledError):
            async for _ in stream_module.stream_chat_response(
                redis,
                Settings(),
                user_id=user.id,
                chat_id=uuid4(),
                content="hi",
                pre_reserved=250,
                user=user,
                skip_usage_seed=True,
            ):
                pass

    refund.assert_awaited_once_with(redis, str(user.id), 250)
