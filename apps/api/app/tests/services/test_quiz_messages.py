"""Tests for quiz_messages helpers (LANG-STATE-001 re-emitted fence fix)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.chat.quiz_messages import find_original_quiz_fence_created_at


def _quiz_content(word: str = "serendipity", question: str = "What word?") -> str:
    return (
        "```vocab_quiz\n"
        + '{"quiz_type":"vocab","word":"'
        + word
        + '","question":"'
        + question
        + '","correct":"A","choices":['
        + '{"letter":"A","text":"serendipity"},'
        + '{"letter":"B","text":"ephemeral"},'
        + '{"letter":"C","text":"ubiquitous"},'
        + '{"letter":"D","text":"candid"}'
        + "]}\n```"
    )


def _msg(
    *,
    msg_id: object,
    content: str,
    created_at: datetime,
    role: str = "assistant",
) -> MagicMock:
    m = MagicMock()
    m.id = msg_id
    m.content = content
    m.created_at = created_at
    m.role = role
    return m


@pytest.mark.asyncio
async def test_find_original_returns_prior_when_no_earlier_fence():
    """If no earlier fence with the same word exists, return prior_assistant.created_at."""
    chat_id = uuid4()
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    prior = _msg(msg_id="h1", content=_quiz_content(), created_at=now)

    session = AsyncMock()
    # No earlier messages
    session_messages_repo = MagicMock()
    session_messages_repo.list_recent_assistants = AsyncMock(return_value=[])

    from app.repositories import messages as messages_repo

    original_list_recent = messages_repo.list_recent_assistants
    messages_repo.list_recent_assistants = session_messages_repo.list_recent_assistants
    try:
        result = await find_original_quiz_fence_created_at(session, chat_id, prior_assistant=prior)
        assert result == now
    finally:
        messages_repo.list_recent_assistants = original_list_recent


@pytest.mark.asyncio
async def test_find_original_finds_earlier_fence_same_word():
    """When the model re-emits a fence, find the original fence's created_at."""
    chat_id = uuid4()
    t1 = datetime(2026, 1, 1, 10, tzinfo=UTC)
    t3 = datetime(2026, 1, 1, 12, tzinfo=UTC)

    original = _msg(msg_id="q1", content=_quiz_content(), created_at=t1)
    reemitted = _msg(msg_id="h1", content=_quiz_content(), created_at=t3)

    session = AsyncMock()
    from app.repositories import messages as messages_repo

    mock_list_recent = AsyncMock(return_value=[reemitted, original])
    original_list_recent = messages_repo.list_recent_assistants
    messages_repo.list_recent_assistants = mock_list_recent
    try:
        result = await find_original_quiz_fence_created_at(
            session, chat_id, prior_assistant=reemitted
        )
        assert result == t1
    finally:
        messages_repo.list_recent_assistants = original_list_recent


@pytest.mark.asyncio
async def test_find_original_ignores_different_word_fence():
    """An earlier fence with a different word should not be used."""
    chat_id = uuid4()
    t1 = datetime(2026, 1, 1, 10, tzinfo=UTC)
    t3 = datetime(2026, 1, 1, 12, tzinfo=UTC)

    other = _msg(msg_id="q0", content=_quiz_content(word="ephemeral"), created_at=t1)
    reemitted = _msg(msg_id="h1", content=_quiz_content(word="serendipity"), created_at=t3)

    session = AsyncMock()
    from app.repositories import messages as messages_repo

    mock_list_recent = AsyncMock(return_value=[reemitted, other])
    original_list_recent = messages_repo.list_recent_assistants
    messages_repo.list_recent_assistants = mock_list_recent
    try:
        result = await find_original_quiz_fence_created_at(
            session, chat_id, prior_assistant=reemitted
        )
        assert result == t3  # no match, returns prior
    finally:
        messages_repo.list_recent_assistants = original_list_recent


@pytest.mark.asyncio
async def test_find_original_returns_prior_when_not_a_quiz():
    """If prior_assistant has no quiz fence, return its created_at immediately."""
    chat_id = uuid4()
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    prior = _msg(msg_id="h1", content="Just a hint, no fence.", created_at=now)

    session = AsyncMock()
    result = await find_original_quiz_fence_created_at(session, chat_id, prior_assistant=prior)
    assert result == now
