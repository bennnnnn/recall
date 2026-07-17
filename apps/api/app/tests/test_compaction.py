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


def _fake_redis(*, acquired: bool = True) -> AsyncMock:
    """Matches the redis_lock (SET NX EX + Lua compare-and-delete) contract."""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=acquired)
    redis.eval = AsyncMock(return_value=1)
    return redis


@pytest.mark.asyncio
async def test_compress_noop_when_tail_fits_budget():
    session = AsyncMock()
    chat = MagicMock()
    chat.summary_message_count = 0
    session.get = AsyncMock(return_value=chat)
    summarize = AsyncMock()
    redis = _fake_redis()
    with (
        patch("app.background.compaction.get_redis_client", return_value=redis),
        patch("app.background.compaction.SessionLocal", lambda: _SessionCM(session)),
        patch("app.background.compaction.messages_repo.count_for_chat", AsyncMock(return_value=10)),
        patch(
            "app.background.compaction.messages_repo.list_recent",
            AsyncMock(return_value=[_msg() for _ in range(10)]),
        ),
        patch("app.background.compaction.summarize_conversation", summarize),
    ):
        # 10 short messages all fit the budget → keep=10, aged_out=0 → nothing to do
        await compaction.compress_chat_history(Settings(), uuid4())
    summarize.assert_not_awaited()
    # Lock acquired then released even on the no-op path.
    redis.set.assert_awaited_once()
    redis.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_compress_summarizes_when_over_window_cap():
    session = AsyncMock()
    chat = MagicMock()
    chat.summary = None
    chat.summary_message_count = 0
    session.get = AsyncMock(return_value=chat)
    recent = [_msg() for _ in range(40)]  # window cap → keep = 40
    redis = _fake_redis()
    with (
        patch("app.background.compaction.get_redis_client", return_value=redis),
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
            "app.background.compaction.summarize_conversation",
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
    redis.eval.assert_awaited_once()  # lock released after a real run too


@pytest.mark.asyncio
async def test_compress_runs_under_token_pressure_before_full_batch():
    session = AsyncMock()
    chat = MagicMock()
    chat.summary = None
    chat.summary_message_count = 0
    session.get = AsyncMock(return_value=chat)
    recent = [_msg("a" * 400) for _ in range(11)]
    summarize = AsyncMock(return_value="PARTIAL")
    redis = _fake_redis()
    with (
        patch("app.background.compaction.get_redis_client", return_value=redis),
        patch("app.background.compaction.SessionLocal", lambda: _SessionCM(session)),
        patch("app.background.compaction.messages_repo.count_for_chat", AsyncMock(return_value=11)),
        patch(
            "app.background.compaction.messages_repo.list_recent",
            AsyncMock(return_value=recent),
        ),
        patch(
            "app.background.compaction.messages_repo.list_range",
            AsyncMock(return_value=[_msg("old")] * 5),
        ) as list_range,
        patch(
            "app.background.compaction.summarize_conversation",
            summarize,
        ),
    ):
        await compaction.compress_chat_history(
            Settings(
                recent_message_window=40,
                context_token_budget=250,
                history_summary_batch=10,
                history_summary_urgent_pending=3,
            ),
            uuid4(),
        )
    summarize.assert_awaited_once()
    list_range.assert_awaited_once()
    assert chat.summary == "PARTIAL"
    assert chat.summary_message_count > 0
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_compress_missing_chat_is_noop():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    redis = _fake_redis()
    with (
        patch("app.background.compaction.get_redis_client", return_value=redis),
        patch("app.background.compaction.SessionLocal", lambda: _SessionCM(session)),
        patch("app.background.compaction.messages_repo.count_for_chat", AsyncMock()) as count,
    ):
        await compaction.compress_chat_history(Settings(), uuid4())
    count.assert_not_awaited()
    redis.eval.assert_awaited_once()  # still releases the lock it acquired


@pytest.mark.asyncio
async def test_compress_skips_when_another_worker_holds_the_lock():
    """Concurrent workers processing the same chat_id: the loser no-ops instead
    of racing the winner on chat.summary/summary_message_count."""
    session = AsyncMock()
    redis = _fake_redis(acquired=False)
    with (
        patch("app.background.compaction.get_redis_client", return_value=redis),
        patch("app.background.compaction.SessionLocal", lambda: _SessionCM(session)),
        patch("app.background.compaction.messages_repo.count_for_chat", AsyncMock()) as count,
    ):
        await compaction.compress_chat_history(Settings(), uuid4())
    count.assert_not_awaited()
    session.get.assert_not_called()
    redis.eval.assert_not_awaited()  # never acquired, nothing to release
