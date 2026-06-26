"""Tests for token-budget history compression."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.background import compaction
from app.core.config import Settings


class _SessionCM:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


def _msg(content="x"):
    m = MagicMock()
    m.role = "user"
    m.content = content
    return m


@pytest.mark.asyncio
async def test_compress_noop_when_tail_fits_budget():
    session = AsyncMock()
    chat = MagicMock()
    chat.summary_message_count = 0
    session.get = AsyncMock(return_value=chat)
    summarize = AsyncMock()
    with (
        patch("app.background.compaction.SessionLocal", lambda: _SessionCM(session)),
        patch("app.background.compaction.messages_repo.count_for_chat", AsyncMock(return_value=10)),
        patch(
            "app.background.compaction.messages_repo.list_recent",
            AsyncMock(return_value=[_msg() for _ in range(10)]),
        ),
        patch("app.background.compaction.litellm_gateway.summarize_conversation", summarize),
    ):
        # 10 short messages all fit the budget → keep=10, aged_out=0 → nothing to do
        await compaction.compress_chat_history(Settings(), uuid4())
    summarize.assert_not_awaited()


@pytest.mark.asyncio
async def test_compress_summarizes_when_over_window_cap():
    session = AsyncMock()
    chat = MagicMock()
    chat.summary = None
    chat.summary_message_count = 0
    session.get = AsyncMock(return_value=chat)
    recent = [_msg() for _ in range(40)]  # window cap → keep = 40
    with (
        patch("app.background.compaction.SessionLocal", lambda: _SessionCM(session)),
        patch("app.background.compaction.messages_repo.count_for_chat", AsyncMock(return_value=60)),
        patch(
            "app.background.compaction.messages_repo.list_recent",
            AsyncMock(return_value=recent),
        ),
        patch(
            "app.background.compaction.messages_repo.list_range",
            AsyncMock(return_value=[_msg("a"), _msg("b")]),
        ),
        patch(
            "app.background.compaction.litellm_gateway.summarize_conversation",
            AsyncMock(return_value="SUMMARY"),
        ),
    ):
        await compaction.compress_chat_history(
            Settings(recent_message_window=40, context_token_budget=6000, history_summary_batch=10),
            uuid4(),
        )
    assert chat.summary == "SUMMARY"
    assert chat.summary_message_count == 20  # total(60) - keep(40)
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_compress_missing_chat_is_noop():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    with (
        patch("app.background.compaction.SessionLocal", lambda: _SessionCM(session)),
        patch("app.background.compaction.messages_repo.count_for_chat", AsyncMock()) as count,
    ):
        await compaction.compress_chat_history(Settings(), uuid4())
    count.assert_not_awaited()
