"""Tests for token-budget history compression."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat import compaction
from app.tests.fakes import FakeSessionCM


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
        patch("app.modules.chat.compaction.get_redis_client", return_value=redis),
        patch("app.modules.chat.compaction.SessionLocal", FakeSessionCM(session)),
        patch(
            "app.modules.chat.compaction.messages_repo.count_for_chat", AsyncMock(return_value=10)
        ),
        patch(
            "app.modules.chat.compaction.messages_repo.list_recent",
            AsyncMock(return_value=[_msg() for _ in range(10)]),
        ),
        patch("app.modules.chat.compaction.summarize_conversation", summarize),
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
        patch("app.modules.chat.compaction.get_redis_client", return_value=redis),
        patch("app.modules.chat.compaction.SessionLocal", FakeSessionCM(session)),
        patch(
            "app.modules.chat.compaction.messages_repo.count_for_chat", AsyncMock(return_value=60)
        ),
        patch(
            "app.modules.chat.compaction.messages_repo.list_recent",
            AsyncMock(return_value=recent),
        ),
        patch(
            "app.modules.chat.compaction.messages_repo.list_range",
            AsyncMock(return_value=[_msg("a"), _msg("b")]),
        ),
        patch(
            "app.modules.chat.compaction.summarize_conversation",
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
        patch("app.modules.chat.compaction.get_redis_client", return_value=redis),
        patch("app.modules.chat.compaction.SessionLocal", FakeSessionCM(session)),
        patch(
            "app.modules.chat.compaction.messages_repo.count_for_chat", AsyncMock(return_value=11)
        ),
        patch(
            "app.modules.chat.compaction.messages_repo.list_recent",
            AsyncMock(return_value=recent),
        ),
        patch(
            "app.modules.chat.compaction.messages_repo.list_range",
            AsyncMock(return_value=[_msg("old")] * 5),
        ) as list_range,
        patch(
            "app.modules.chat.compaction.summarize_conversation",
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


def _over_window_patches(session, summarize):
    return (
        patch("app.modules.chat.compaction.get_redis_client", return_value=_fake_redis()),
        patch("app.modules.chat.compaction.SessionLocal", FakeSessionCM(session)),
        patch(
            "app.modules.chat.compaction.messages_repo.count_for_chat", AsyncMock(return_value=60)
        ),
        patch(
            "app.modules.chat.compaction.messages_repo.list_recent",
            AsyncMock(return_value=[_msg() for _ in range(40)]),
        ),
        patch(
            "app.modules.chat.compaction.messages_repo.list_range",
            AsyncMock(return_value=[_msg("a"), _msg("b")]),
        ),
        patch("app.modules.chat.compaction.summarize_conversation", summarize),
    )


_OVER_WINDOW = Settings(
    recent_message_window=40, context_token_budget=6000, history_summary_batch=10
)


class _TrackedSessionCM(FakeSessionCM):
    open = 0

    async def __aenter__(self):
        type(self).open += 1
        return await super().__aenter__()

    async def __aexit__(self, *args):
        type(self).open -= 1
        return False


@pytest.mark.asyncio
async def test_the_summary_model_runs_with_no_session_open():
    session = AsyncMock()
    chat = MagicMock(summary=None, summary_message_count=0)
    session.get = AsyncMock(return_value=chat)
    open_during_model: list[int] = []

    async def summarize(*_args):
        open_during_model.append(_TrackedSessionCM.open)
        return "SUMMARY"

    with ExitStack() as stack:
        for each in _over_window_patches(session, summarize):
            stack.enter_context(each)
        stack.enter_context(
            patch("app.modules.chat.compaction.SessionLocal", lambda: _TrackedSessionCM(session))
        )
        await compaction.compress_chat_history(_OVER_WINDOW, uuid4())
    assert open_during_model == [0]
    assert chat.summary == "SUMMARY"


@pytest.mark.asyncio
async def test_a_summary_folded_elsewhere_meanwhile_is_not_overwritten():
    session = AsyncMock()
    chat = MagicMock(summary=None, summary_message_count=0)
    session.get = AsyncMock(return_value=chat)

    async def summarize(*_args):
        chat.summary, chat.summary_message_count = "NEWER", 20  # another run saved first
        return "STALE"

    with ExitStack() as stack:
        for each in _over_window_patches(session, summarize):
            stack.enter_context(each)
        await compaction.compress_chat_history(_OVER_WINDOW, uuid4())
    assert chat.summary == "NEWER"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_compress_missing_chat_is_noop():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    redis = _fake_redis()
    with (
        patch("app.modules.chat.compaction.get_redis_client", return_value=redis),
        patch("app.modules.chat.compaction.SessionLocal", FakeSessionCM(session)),
        patch("app.modules.chat.compaction.messages_repo.count_for_chat", AsyncMock()) as count,
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
        patch("app.modules.chat.compaction.get_redis_client", return_value=redis),
        patch("app.modules.chat.compaction.SessionLocal", FakeSessionCM(session)),
        patch("app.modules.chat.compaction.messages_repo.count_for_chat", AsyncMock()) as count,
    ):
        await compaction.compress_chat_history(Settings(), uuid4())
    count.assert_not_awaited()
    session.get.assert_not_called()
    redis.eval.assert_not_awaited()  # never acquired, nothing to release


def test_summary_system_prompt_preserves_uncertainty():
    from app.services.context_window import SUMMARY_SYSTEM_PROMPT

    assert "considering" in SUMMARY_SYSTEM_PROMPT
    assert "uses Postgres" in SUMMARY_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_summary_generations_keep_undecided_redis():
    from app.modules.chat.summarize import summarize_conversation

    generations = [
        "Facts: considering Redis\nOpen: cache choice",
        "Facts: considering Redis\nTopics: API\nOpen: cache choice",
        "Facts: considering Redis\nTopics: API, deploy\nOpen: cache choice",
    ]

    async def fake_complete(**kwargs):
        system = kwargs["messages"][0]["content"]
        assert "considering" in system
        return generations.pop(0)

    prior = None
    with patch("app.modules.chat.summarize.litellm_gateway.complete_text", fake_complete):
        for round_messages in (
            [{"role": "user", "content": "Maybe Redis?"}],
            [{"role": "user", "content": "Still thinking about Redis."}],
            [{"role": "user", "content": "We talked about deploy too."}],
        ):
            prior = await summarize_conversation(
                Settings(mock_llm_enabled=False, openrouter_api_key="test-key"),
                prior,
                round_messages,
            )
            assert prior is not None
            assert "considering Redis" in prior
            assert "uses Redis" not in prior
    assert generations == []
