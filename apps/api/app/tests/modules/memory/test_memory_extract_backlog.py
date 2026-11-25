from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.memory.extract_backlog import (
    FAILED_PASS_LIMIT,
    clear_failed_extract_passes,
    expand_memory_extract_transcript,
    format_extract_cursor,
    format_user_memory_transcript,
    history_chat_transcript,
    note_failed_extract_pass,
    parse_extract_cursor,
)
from app.tests.fakes import redis_mock


def test_parse_extract_cursor_round_trip():
    created = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    msg_id = uuid4()
    raw = format_extract_cursor(created, msg_id)
    parsed_at, parsed_id = parse_extract_cursor(raw)
    assert parsed_at == created
    assert parsed_id == msg_id
    assert parse_extract_cursor(None) == (None, None)
    assert parse_extract_cursor("nope") == (None, None)


def test_format_user_memory_transcript_strips_attachments():
    built = format_user_memory_transcript(
        [
            "Help me eat healthier.",
            "I'm allergic to peanuts.\n[Image: plate.jpg]",
        ]
    )
    assert built == ("User: Help me eat healthier.\nUser: I'm allergic to peanuts.")
    assert "Image" not in built


def test_a_line_that_only_says_when_teaches_memory_nothing():
    # Live 2026-11-06: "6pm", the answer to a reminder's question, became "User works or
    # starts their day at 18:00 (6pm)".
    built = format_user_memory_transcript(
        ["remind me to call mom tomorrow at 6", "6pm", "tomorrow at 6", "pm"]
    )
    assert built == "User: remind me to call mom tomorrow at 6"
    assert format_user_memory_transcript(["I start work at 6pm"]) == "User: I start work at 6pm"


@pytest.mark.asyncio
async def test_expand_includes_unprocessed_user_lines():
    session = AsyncMock()
    older = _message("user", "I'm allergic to peanuts.", 10, 0)
    newer = SimpleNamespace(
        id=uuid4(),
        created_at=datetime(2026, 9, 3, 10, 1, tzinfo=UTC),
        content="Keep the meals simple.",
    )
    redis = redis_mock()
    redis.get = AsyncMock(return_value=None)
    with (
        patch(
            "app.modules.memory.extract_backlog.chat_history.user_lines_since",
            AsyncMock(return_value=[older, newer]),
        ),
        patch(
            "app.modules.memory.extract_backlog.get_redis_client",
            MagicMock(return_value=redis),
        ),
        patch(
            "app.modules.memory.extract_backlog.chat_history.messages_before",
            # The messages before the last unread line: the reply before the first, and it.
            AsyncMock(return_value=[_message("assistant", "What can I make?", 9, 59), older]),
        ),
    ):
        read = await expand_memory_extract_transcript(
            session,
            user_id=uuid4(),
            chat_id=uuid4(),
            fallback_transcript="User: Keep the meals simple.",
        )
    assert "I'm allergic to peanuts." in read.transcript
    assert "Keep the meals simple." in read.transcript
    assert read.cursor == format_extract_cursor(newer.created_at, newer.id)
    # Each line keeps its message: a fact's "From" link opens the chat there.
    assert [(line.text, line.message_id) for line in read.sources] == [
        ("I'm allergic to peanuts.", older.id),
        ("Keep the meals simple.", newer.id),
    ]
    # The chat before the first unread line is read as context.
    assert read.context == (("assistant", "What can I make?"),)


def _message(role: str, content: str, hour: int, minute: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        role=role,
        content=content,
        created_at=datetime(2026, 9, 3, hour, minute, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_a_lagging_pass_reads_each_line_with_the_reply_it_answers():
    """Two unread lines: the second keeps the question asked between them, so a bare "34"
    answers "How old are you?" (review, #2539). The chat before them and the replies
    between them are one read, so the job makes no more round trips."""
    before = _message("assistant", "Hey! What's up?", 9, 59)
    hi = _message("user", "Hi", 10, 0)
    asked = _message("assistant", "Hi! How old are you?", 10, 1)
    answer = _message("user", "34", 10, 2)
    redis = redis_mock()
    redis.get = AsyncMock(return_value=None)
    window = AsyncMock(return_value=[before, hi, asked])
    with (
        patch(
            "app.modules.memory.extract_backlog.chat_history.user_lines_since",
            AsyncMock(return_value=[hi, answer]),
        ),
        patch(
            "app.modules.memory.extract_backlog.get_redis_client",
            MagicMock(return_value=redis),
        ),
        patch("app.modules.memory.extract_backlog.chat_history.messages_before", window),
    ):
        read = await expand_memory_extract_transcript(
            AsyncMock(), user_id=uuid4(), chat_id=uuid4(), fallback_transcript="User: 34"
        )
    assert [(line.text, line.asked) for line in read.sources] == [
        ("Hi", "Hey! What's up?"),
        ("34", "Hi! How old are you?"),
    ]
    assert read.context == (("assistant", "Hey! What's up?"),)
    window.assert_awaited_once()
    assert window.await_args.args[2] is answer


@pytest.mark.asyncio
async def test_a_failed_window_read_keeps_the_lines():
    rows = [_message("user", "Hi", 10, 0), _message("user", "I live in Denver", 10, 2)]
    with (
        patch(
            "app.modules.memory.extract_backlog.chat_history.user_lines_since",
            AsyncMock(return_value=rows),
        ),
        patch(
            "app.modules.memory.extract_backlog.chat_history.messages_before",
            AsyncMock(side_effect=RuntimeError("db down")),
        ),
    ):
        read = await history_chat_transcript(AsyncMock(), uuid4(), newer_than=None)
    assert [(line.text, line.asked) for line in read.sources] == [
        ("Hi", ""),
        ("I live in Denver", ""),
    ]


@pytest.mark.asyncio
async def test_note_failed_extract_pass_gives_up_after_the_limit(fake_redis):
    user_id, chat_id = uuid4(), uuid4()
    with patch(
        "app.modules.memory.extract_backlog.get_redis_client",
        MagicMock(return_value=fake_redis),
    ):
        results = [
            await note_failed_extract_pass(user_id, chat_id) for _ in range(FAILED_PASS_LIMIT)
        ]
        # The count starts again after giving up, so a later failure is retried.
        after_reset = await note_failed_extract_pass(user_id, chat_id)

    assert results == [False] * (FAILED_PASS_LIMIT - 1) + [True]
    assert after_reset is False


@pytest.mark.asyncio
async def test_clear_failed_extract_passes_restarts_the_count(fake_redis):
    user_id, chat_id = uuid4(), uuid4()
    with patch(
        "app.modules.memory.extract_backlog.get_redis_client",
        MagicMock(return_value=fake_redis),
    ):
        for _ in range(FAILED_PASS_LIMIT - 1):
            await note_failed_extract_pass(user_id, chat_id)
        await clear_failed_extract_passes(user_id, chat_id)
        gave_up = await note_failed_extract_pass(user_id, chat_id)

    assert gave_up is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cursor_at, expected",
    [
        # Past a cursor, no rows means every line was read: the payload is not read again.
        (datetime(2026, 9, 3, 10, 0, tzinfo=UTC), ""),
        # No cursor yet (or Redis down): the payload's lines are all there is.
        (None, "User: Forget that I live in Denver."),
    ],
)
async def test_nothing_past_the_cursor_reads_nothing(cursor_at, expected):
    redis = redis_mock()
    redis.get = AsyncMock(
        return_value=format_extract_cursor(cursor_at, uuid4()) if cursor_at else None
    )
    with (
        patch(
            "app.modules.memory.extract_backlog.chat_history.user_lines_since",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.modules.memory.extract_backlog.get_redis_client",
            MagicMock(return_value=redis),
        ),
    ):
        read = await expand_memory_extract_transcript(
            AsyncMock(),
            user_id=uuid4(),
            chat_id=uuid4(),
            fallback_transcript="User: Forget that I live in Denver.",
        )
    assert read.transcript == expected
    assert read.cursor is None
