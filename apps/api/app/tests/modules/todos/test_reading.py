"""The saved to-dos as chat reads them: a read-back, and which one a message names."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.todos import reading
from app.tests.fakes import fake_session

_ROWS = [
    SimpleNamespace(content="Gym", checked=False, due_at=None, topic="General"),
    SimpleNamespace(content="Call mom", checked=False, due_at=None, topic="Reminders"),
    SimpleNamespace(content="Go", checked=False, due_at=None, topic="General"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "named"),
    [
        ("move gym to 7pm", "gym"),
        ("I called Mom already, tick it off", None),
        ("call mom is done", "call mom"),
        ("let's go for a walk", None),
        ("what's the best gymnastics app?", None),
    ],
)
async def test_saved_todo_named(
    monkeypatch: pytest.MonkeyPatch, text: str, named: str | None
) -> None:
    monkeypatch.setattr(reading.todos_repo, "list_for_user", AsyncMock(return_value=_ROWS))
    assert await reading.saved_todo_named(fake_session(), uuid4(), text) == named


def test_a_read_back_lists_open_rows_by_time_then_the_done_ones() -> None:
    rows = [
        SimpleNamespace(
            content="Dentist",
            checked=False,
            due_at=datetime(2026, 10, 20, 12, 0, tzinfo=UTC),
            due_has_time=True,
            recurrence_rule=None,
            topic="Health",
        ),
        SimpleNamespace(content="Milk", checked=True, due_at=None, topic="General"),
    ]
    assert reading.format_reminder_reading(rows, "Africa/Nairobi") == (
        "Dentist — Tuesday, Oct 20, 3:00 PM · Health.\nDone: Milk."
    )
    assert reading.format_reminder_reading([], "UTC") == "Nothing scheduled."
