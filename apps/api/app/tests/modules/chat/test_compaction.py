"""Tests for token-budget history compression."""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import Chat
from app.modules.chat import compaction
from app.tests.fakes import FakeSessionCM, fake_session, redis_mock


def _msg(content="x"):
    m = MagicMock()
    m.role = "user"
    m.content = content
    return m


def _fake_redis(*, acquired: bool = True) -> AsyncMock:
    """Matches the redis_lock (SET NX EX + Lua compare-and-delete) contract."""
    redis = redis_mock()
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
            "app.modules.conversation.messages_repository.count_for_chat",
            AsyncMock(return_value=10),
        ),
        patch(
            "app.modules.conversation.messages_repository.list_recent",
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
            "app.modules.conversation.messages_repository.count_for_chat",
            AsyncMock(return_value=60),
        ),
        patch(
            "app.modules.conversation.messages_repository.list_recent",
            AsyncMock(return_value=recent),
        ),
        patch(
            "app.modules.conversation.messages_repository.list_range",
            AsyncMock(return_value=[_msg("a"), _msg("b")]),
        ),
        patch(
            "app.modules.chat.compaction.summarize_conversation",
            AsyncMock(return_value="SUMMARY"),
        ),
    ):
        await compaction.compress_chat_history(_OVER_WINDOW, uuid4())
    assert chat.summary == "SUMMARY"
    # 60 unsummarized pass the 30-message trigger: the newest 40 (the target) stay.
    assert chat.summary_message_count == 20
    session.commit.assert_awaited()
    redis.eval.assert_awaited_once()  # lock released after a real run too


@pytest.mark.asyncio
async def test_compress_folds_past_the_token_trigger():
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
            "app.modules.conversation.messages_repository.count_for_chat",
            AsyncMock(return_value=11),
        ),
        patch(
            "app.modules.conversation.messages_repository.list_recent",
            AsyncMock(return_value=recent),
        ),
        patch(
            "app.modules.conversation.messages_repository.list_range",
            AsyncMock(return_value=[_msg("old")] * 5),
        ) as list_range,
        patch(
            "app.modules.chat.compaction.summarize_conversation",
            summarize,
        ),
    ):
        await compaction.compress_chat_history(
            # 11 rows of ~111 tokens pass 1000: the newest 2 fit the 250-token target.
            Settings(history_fold_trigger_tokens=1000, history_fold_target_tokens=250),
            uuid4(),
        )
    summarize.assert_awaited_once()
    list_range.assert_awaited_once()
    assert list_range.await_args.kwargs["limit"] == 9
    assert chat.summary == "PARTIAL"
    assert chat.summary_message_count == 9
    session.commit.assert_awaited()


def _over_window_patches(session, summarize, history=None):
    return (
        patch("app.modules.chat.compaction.get_redis_client", return_value=_fake_redis()),
        patch("app.modules.chat.compaction.SessionLocal", FakeSessionCM(session)),
        patch(
            "app.modules.conversation.messages_repository.count_for_chat",
            AsyncMock(return_value=60),
        ),
        patch(
            "app.modules.conversation.messages_repository.list_recent",
            AsyncMock(return_value=[_msg() for _ in range(40)]),
        ),
        patch(
            "app.modules.conversation.messages_repository.list_range",
            AsyncMock(return_value=history or [_msg("a"), _msg("b")]),
        ),
        patch("app.modules.chat.compaction.summarize_conversation", summarize),
    )


# A chat of 60 unsummarized messages (40 loaded) is past this rule's 30-message trigger.
_OVER_WINDOW = Settings(
    history_max_messages=40, history_fold_trigger_messages=30, history_fold_target_messages=40
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
async def test_the_summary_reads_a_reply_without_its_sources_fence():
    """A summary once kept "3.8% in June 2025" from a search result as if it were said."""
    chat = MagicMock(summary=None, summary_message_count=0)
    session = fake_session(get=AsyncMock(return_value=chat))
    reply = _msg(
        'Kenya held the rate at 8.75%.\n\n```sources\n[{"title": "CBK", "url": "https://x.test", '
        '"snippet": "Inflation 3.8% | June 2025"}]\n```'
    )
    reply.role = "assistant"
    seen: list[list[dict[str, str]]] = []

    async def summarize(_settings, _prior, transcript):
        seen.append(transcript)
        return "SUMMARY"

    with ExitStack() as stack:
        for each in _over_window_patches(session, summarize, [_msg("What is the rate?"), reply]):
            stack.enter_context(each)
        await compaction.compress_chat_history(_OVER_WINDOW, uuid4())
    assert [m["content"] for m in seen[0]] == ["What is the rate?", "Kenya held the rate at 8.75%."]


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
        patch("app.modules.conversation.messages_repository.count_for_chat", AsyncMock()) as count,
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
        patch("app.modules.conversation.messages_repository.count_for_chat", AsyncMock()) as count,
    ):
        await compaction.compress_chat_history(Settings(), uuid4())
    count.assert_not_awaited()
    session.get.assert_not_called()
    redis.eval.assert_not_awaited()  # never acquired, nothing to release


def test_summary_system_prompt_preserves_uncertainty():
    from app.modules.chat.context_window import SUMMARY_SYSTEM_PROMPT

    assert "considering" in SUMMARY_SYSTEM_PROMPT
    assert "uses Postgres" in SUMMARY_SYSTEM_PROMPT


def test_summary_system_prompt_keeps_topics_in_order_and_short():
    from app.modules.chat.context_window import (
        NEWEST_FIGURE_RULE,
        NO_INVENTED_PLAN,
        SUMMARY_SYSTEM_PROMPT,
    )

    # A 36-message chat once saved a summary cut off mid-sentence, with the middle topics
    # gone: the model was never asked to stay short, so it ran out of tokens.
    # The model writes only the new messages' topics; earlier lines are kept by code.
    assert "NEW messages only" in SUMMARY_SYSTEM_PROMPT
    assert "under 200 words" in SUMMARY_SYSTEM_PROMPT
    assert NEWEST_FIGURE_RULE in SUMMARY_SYSTEM_PROMPT
    # An invented "Open: user considering sleeping 6-7 hours" later came back as something
    # the assistant had asked.
    assert NO_INVENTED_PLAN in SUMMARY_SYSTEM_PROMPT


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


@pytest.mark.asyncio
async def test_compress_folds_nothing_between_folds():
    """Under the trigger the summary's edge holds still, though messages wait outside
    it: that edge is where every turn's history starts, the prefix a cache serves."""
    session = AsyncMock()
    chat = MagicMock()
    chat.summary = "Facts: …"
    chat.summary_message_count = 30
    session.get = AsyncMock(return_value=chat)
    summarize = AsyncMock()
    with ExitStack() as stack:
        for p in _over_window_patches(session, summarize):
            stack.enter_context(p)
        # 60 - 30 = 30 unsummarized: not past the 30-message trigger.
        await compaction.compress_chat_history(_OVER_WINDOW, uuid4())
    summarize.assert_not_awaited()
    assert chat.summary_message_count == 30


@pytest.mark.asyncio
async def test_a_backlog_folds_a_window_at_a_time():
    """A chat with hundreds of unsummarized messages (written before the rule, or after a
    failed job) folds its oldest ``history_max_messages`` a run, never all at once."""
    session = AsyncMock()
    chat = MagicMock()
    chat.summary = None
    chat.summary_message_count = 0
    session.get = AsyncMock(return_value=chat)
    with (
        patch("app.modules.chat.compaction.get_redis_client", return_value=_fake_redis()),
        patch("app.modules.chat.compaction.SessionLocal", FakeSessionCM(session)),
        patch(
            "app.modules.conversation.messages_repository.count_for_chat",
            AsyncMock(return_value=500),
        ),
        patch(
            "app.modules.conversation.messages_repository.list_recent",
            AsyncMock(return_value=[_msg() for _ in range(40)]),
        ),
        patch(
            "app.modules.conversation.messages_repository.list_range",
            AsyncMock(return_value=[_msg("a")] * 40),
        ) as list_range,
        patch(
            "app.modules.chat.compaction.summarize_conversation",
            AsyncMock(return_value="SUMMARY"),
        ),
    ):
        await compaction.compress_chat_history(_OVER_WINDOW, uuid4())
    assert list_range.await_args.kwargs["limit"] == 40
    assert chat.summary_message_count == 40


def _rows(count: int) -> list[SimpleNamespace]:
    """A chat whose replies are long: the user's short lines, each answered at length."""
    return [
        SimpleNamespace(
            id=uuid4(),
            role="user" if index % 2 == 0 else "assistant",
            content=f"question {index}" if index % 2 == 0 else "word " * 1000,
        )
        for index in range(count)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(("summarized", "gap"), [(0, [2, 3]), (2, [2, 3]), (4, [])])
async def test_the_prompt_gap_never_repeats_what_the_summary_folded(summarized, gap):
    """Long replies keep the verbatim tail short, so the summary folds the rows just
    before it. Rows the summary holds must not come back as the gap between them."""
    from app.modules.chat.prompt_window import load_prompt_window

    rows = _rows(12)
    current = SimpleNamespace(id=uuid4(), role="user", content="what did we cover?")
    chat = Chat(id=uuid4(), user_id=uuid4(), summary="Facts: …", summary_message_count=summarized)

    window = await load_prompt_window(
        chat.id,
        chat,
        [*rows, current],
        # A budget eight such replies overflow, whatever the default is.
        Settings(context_token_budget=6000),
        query_text=current.content,
        omit_message_ids=None,
        current_user_message_id=current.id,
        prior_count=len(rows),
    )

    assert [m.id for m in window.recent] == [m.id for m in rows[4:]] + [current.id]
    assert [rows.index(m) for m in window.gap] == gap


def _short_rows(count: int) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            id=uuid4(),
            role="user" if index % 2 == 0 else "assistant",
            content=f"line {index}",
            created_at=index,
        )
        for index in range(count)
    ]


async def _window(rows, current, chat, settings=None, *, prior_count=None, omit=None):
    from app.modules.chat.prompt_window import load_prompt_window

    return await load_prompt_window(
        chat.id,
        chat,
        [*rows, current],
        settings or Settings(),
        query_text=current.content,
        omit_message_ids=omit,
        current_user_message_id=current.id,
        prior_count=len(rows) if prior_count is None else prior_count,
    )


@pytest.mark.asyncio
async def test_the_history_starts_at_the_summarys_edge_while_it_fits():
    """Every message after the edge goes whole, and none the summary holds: the history
    then starts where the last turn's did, the prefix a provider caches."""
    rows = _short_rows(12)
    current = SimpleNamespace(id=uuid4(), role="user", content="and then?", created_at=99)
    chat = Chat(id=uuid4(), user_id=uuid4(), summary="Facts: …", summary_message_count=4)

    window = await _window(rows, current, chat)

    assert [m.id for m in window.recent] == [m.id for m in rows[4:]] + [current.id]
    assert window.gap == []
    assert window.anchored
    from app.modules.chat.context_window import total_tokens

    assert window.history_size == (9, total_tokens(window.recent))


@pytest.mark.asyncio
async def test_the_history_reads_the_unsummarized_rows_older_than_the_loaded_window():
    """The turn loads the readers' 20 rows; the prompt reads the ones before them, back to
    the summary's edge, in its own short session."""
    chat_rows = _short_rows(50)
    loaded = chat_rows[-20:]
    current = SimpleNamespace(id=uuid4(), role="user", content="and then?", created_at=99)
    chat = Chat(id=uuid4(), user_id=uuid4(), summary="Facts: …", summary_message_count=10)
    before = AsyncMock(return_value=chat_rows[10:30])

    with (
        patch("app.modules.chat.prompt_context.SessionLocal", FakeSessionCM(AsyncMock())),
        patch("app.modules.conversation.history.messages_before", before),
    ):
        window = await _window(loaded, current, chat, prior_count=50)

    assert before.await_args.kwargs == {"limit": 20}
    assert before.await_args.args[2] is loaded[0]
    assert [m.id for m in window.recent] == [m.id for m in chat_rows[10:]] + [current.id]
    assert window.anchored


@pytest.mark.asyncio
async def test_past_the_message_cap_the_history_slides():
    chat_rows = _short_rows(50)
    current = SimpleNamespace(id=uuid4(), role="user", content="and then?", created_at=99)
    chat = Chat(id=uuid4(), user_id=uuid4(), summary=None, summary_message_count=0)
    # Only the gap loader reads older rows: its newest ten before the window.
    before = AsyncMock(return_value=chat_rows[20:30])

    with (
        patch("app.modules.chat.prompt_context.SessionLocal", FakeSessionCM(AsyncMock())),
        patch("app.modules.conversation.history.messages_before", before),
    ):
        window = await _window(
            chat_rows[-20:], current, chat, Settings(history_max_messages=30), prior_count=50
        )

    assert before.await_args.kwargs == {"limit": 10}
    assert not window.anchored
    assert window.history_size is None
    assert [m.id for m in window.recent] == [m.id for m in chat_rows[-19:]] + [current.id]
    # The row the current line pushed out of the loaded twenty, and nine before it.
    assert [m.id for m in window.gap] == [m.id for m in chat_rows[21:31]]


@pytest.mark.asyncio
async def test_a_regenerated_reply_stays_out_of_the_anchored_history():
    rows = _short_rows(6)
    current = rows[-2]
    chat = Chat(id=uuid4(), user_id=uuid4(), summary=None, summary_message_count=0)
    from app.modules.chat.prompt_window import load_prompt_window

    window = await load_prompt_window(
        chat.id,
        chat,
        rows,
        Settings(),
        query_text=current.content,
        omit_message_ids={rows[-1].id},
        current_user_message_id=None,
        prior_count=len(rows),
    )

    assert [m.id for m in window.recent] == [m.id for m in rows[:-1]]
    assert window.anchored
