"""Finalize must not refund after a successful DB commit."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.post_turn import finalize_stream_turn_db
from app.services.chat.turn_prep import StreamContext


class _FakeSessionCM:
    def __init__(self, session: AsyncMock):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_adjust_usage_failure_after_commit_does_not_refund():
    user_id = uuid4()
    chat_id = uuid4()
    redis = AsyncMock()
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    assistant = MagicMock()
    assistant.id = uuid4()

    ctx = StreamContext(
        user_id=user_id,
        chat_id=chat_id,
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "hi"}],
        run_title=False,
        user_message_content="hi",
        reserved_tokens=200,
        max_output_tokens=50,
        skip_memory_jobs=True,
        user=MagicMock(plan="free"),
    )

    refund = AsyncMock()
    adjust = AsyncMock(side_effect=RuntimeError("redis blip"))

    with (
        patch("app.services.chat.post_turn.SessionLocal", lambda: _FakeSessionCM(session)),
        patch(
            "app.services.chat.post_turn.messages_repo.create",
            AsyncMock(return_value=assistant),
        ),
        patch("app.services.chat.post_turn.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.post_turn.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.post_turn.quota_service.adjust_usage", adjust),
        patch("app.services.chat.post_turn.quota_service.refund_usage", refund),
        patch(
            "app.services.chat.post_turn.quota_service.daily_limit_for_user",
            return_value=100_000,
        ),
        patch("app.services.chat.post_turn.get_settings", return_value=Settings()),
    ):
        await finalize_stream_turn_db(
            redis,
            ctx,
            "hello",
            {"input": 10, "output": 5},
            result={},
        )

    session.commit.assert_awaited()
    adjust.assert_awaited_once()
    refund.assert_not_awaited()
