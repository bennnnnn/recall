from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.memory.extract_backlog import (
    expand_memory_extract_transcript,
    format_extract_cursor,
    format_user_memory_transcript,
    parse_extract_cursor,
)


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


@pytest.mark.asyncio
async def test_expand_includes_unprocessed_user_lines():
    session = AsyncMock()
    older = SimpleNamespace(
        id=uuid4(),
        created_at=datetime(2026, 9, 3, 10, 0, tzinfo=UTC),
        content="I'm allergic to peanuts.",
    )
    newer = SimpleNamespace(
        id=uuid4(),
        created_at=datetime(2026, 9, 3, 10, 1, tzinfo=UTC),
        content="Keep the meals simple.",
    )
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    with (
        patch(
            "app.services.memory.extract_backlog.messages_repo.list_user_contents_since",
            AsyncMock(return_value=[older, newer]),
        ),
        patch(
            "app.services.memory.extract_backlog.get_redis_client",
            MagicMock(return_value=redis),
        ),
    ):
        transcript, cursor = await expand_memory_extract_transcript(
            session,
            user_id=uuid4(),
            chat_id=uuid4(),
            fallback_transcript="User: Keep the meals simple.",
        )
    assert "I'm allergic to peanuts." in transcript
    assert "Keep the meals simple." in transcript
    assert cursor == format_extract_cursor(newer.created_at, newer.id)
