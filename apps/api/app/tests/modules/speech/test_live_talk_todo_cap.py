"""A reminder spoken at the open to-do cap is an expected refusal (review of #2597): the
saved reply says the list is full, never "I've set a reminder", and no error is logged."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.speech import live_talk
from app.modules.todos.limits import TODO_LIST_FULL_REPLY, TodoLimitError


@asynccontextmanager
async def _savepoint():
    yield


@pytest.mark.asyncio
async def test_a_reminder_spoken_at_the_cap_says_the_list_is_full(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = MagicMock(begin_nested=lambda: _savepoint())
    user = MagicMock(id=uuid4(), locale="en", timezone="UTC")
    refused = AsyncMock(side_effect=TodoLimitError("full"))
    with patch.object(live_talk.todos_service, "materialize_reminder_fences", refused):
        reply = await live_talk._save_spoken_reminders(
            session, user, uuid4(), "I've set a reminder to call mom.", "remind me to call mom"
        )
    assert reply == TODO_LIST_FULL_REPLY
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
