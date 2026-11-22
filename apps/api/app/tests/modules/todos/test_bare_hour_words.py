"""The word rules on the shapes the live QA round (2026-11-22) missed: an hour said with no
am or pm, "did it actually save?", and a reminder set a while before an event."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.todos import repository as todos_repo
from app.modules.todos.reminder_fences import materialize_reminder_fences
from app.modules.todos.spoken_add import parse_spoken_add
from app.modules.todos.spoken_change import parse_spoken_reminder_change
from app.tests.fakes import fake_session

ZONE = "America/Los_Angeles"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("line", "reply", "hour"),
    [
        # The model asked which half; the rule settles it and saves.
        ("hey can u remind me to move my car tmrw at 5", "Do you mean 5 am or 5 pm?", 17),
        # The model's fence took the other half: the user's words, by the rule, decide.
        (
            "remind me to call the plumber about the sink tmrw at 5",
            '```reminder\n{"title": "Call the plumber", "due_at": "2030-01-02T05:00:00"}\n```',
            17,
        ),
        ("remind me to grab coffee w jess tomorrow at 11", "When should I remind you?", 11),
    ],
)
async def test_an_hour_with_no_half_is_saved_by_the_rule(line: str, reply: str, hour: int) -> None:
    session = fake_session()
    with (
        patch.object(todos_repo, "list_for_user", AsyncMock(return_value=[])),
        patch.object(todos_repo, "get_open_dated_duplicate", AsyncMock(return_value=None)),
        patch.object(todos_repo, "create", AsyncMock()) as create,
    ):
        _text, created = await materialize_reminder_fences(
            session,
            user_id=uuid4(),
            chat_id=uuid4(),
            assistant_text=reply,
            user_timezone=ZONE,
            user_text=line,
        )
    assert created == 1
    assert create.await_args is not None
    due: datetime = create.await_args.kwargs["due_at"]
    assert due.tzinfo is not None
    from zoneinfo import ZoneInfo

    assert due.astimezone(ZoneInfo(ZONE)).hour == hour
    assert due > datetime.now(UTC)


def test_a_quoted_request_is_not_settled_by_the_rule() -> None:
    """ "translate to amharic: remind me to call you tomorrow at 6" asks for a translation."""
    from app.modules.todos.spoken_clauses import parse_spoken_adds

    adds = parse_spoken_adds(
        "translate to amharic: remind me to call you tomorrow at 6", user_timezone=ZONE
    )
    assert all(add.hour is None for add in adds)


@pytest.mark.parametrize(
    "line",
    ["Did it actually save somewhere?", "did it actually save tho?", "did it work?"],
)
def test_asking_whether_it_saved_is_not_marking_it_done(line: str) -> None:
    assert parse_spoken_reminder_change(line, user_timezone=ZONE) is None


@pytest.mark.parametrize("line", ["did it", "done ✅ just talked to her", "did it!"])
def test_saying_it_is_done_still_marks_it(line: str) -> None:
    change = parse_spoken_reminder_change(line, user_timezone=ZONE)
    assert change is not None and change.action == "complete"


@pytest.mark.parametrize(
    "line",
    [
        "remind me an hour before my dinner at 7 tonight",
        "remind me 15 minutes before my 3pm meeting today",
        "remind me to leave for the airport 2 hours before my 6pm flight tomorrow",
    ],
)
def test_a_lead_time_is_not_read_as_the_title_and_the_events_clock(line: str) -> None:
    """The dinner's 7 is not the reminder's: the turn's read works the lead time out."""
    assert parse_spoken_add(line) is None


def test_abt_reads_as_about() -> None:
    add = parse_spoken_add("remind me abt my bio test tmrw at 5?")
    assert add is not None and add.title == "my bio test" and add.day == "tomorrow"
