"""One reminder instant for push, email and the phone (``due_reminders.reminder_instant``).

The phone scheduled its own alerts from a copy of the lead rule and knew nothing of quiet
hours: quiet hours 22:00-07:00 and a to-do due at 23:30 alerted on the device at 23:20 while
push waited until 07:00. The to-do list now carries ``notify_at``, the instant the push
scheduler sends at; these tests hold the two together.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import PushToken, TodoItem
from app.modules.notifications import push as push_service
from app.modules.todos import api as todos_router
from app.modules.todos.due_reminders import (
    is_due_now,
    mark_reminder_emailed,
    mark_reminder_pushed,
    reminder_instant,
)
from app.modules.todos.occurrences import TodoEmailSnapshot
from app.repositories import users as users_repo
from app.services.reminder_timing import OVERDUE_MAX_HOURS
from app.tests.fakes import make_user

NEW_YORK = ZoneInfo("America/New_York")


def _todo(due: datetime, *, set_at: datetime | None = None) -> TodoItem:
    return TodoItem(
        id=uuid4(),
        user_id=uuid4(),
        content="Call the dentist",
        checked=False,
        due_at=due,
        due_set_at=set_at or due - timedelta(days=1),
    )


def _first_push_minute(todo: TodoItem, user: object, *, start: datetime) -> datetime | None:
    """The first minute a scheduler that runs every minute would send this reminder."""
    moment = start
    end = start + timedelta(hours=OVERDUE_MAX_HOURS + 26)
    while moment <= end:
        if is_due_now(todo, user, now=moment):  # type: ignore[arg-type]
            return moment
        moment += timedelta(minutes=1)
    return None


def _ceil_minute(instant: datetime) -> datetime:
    floor = instant.replace(second=0, microsecond=0)
    return floor if floor == instant else floor + timedelta(minutes=1)


_SCENARIOS = [
    # tz, quiet window (or None), lead, due on the user's clock, set this long before due
    ("UTC", None, 10, (2026, 1, 2, 23, 30), timedelta(days=1)),
    ("UTC", (1320, 420), 10, (2026, 1, 2, 23, 30), timedelta(days=1)),
    ("UTC", (1320, 420), 60, (2026, 1, 3, 7, 30), timedelta(days=1)),
    ("Asia/Tokyo", (1320, 420), 15, (2026, 1, 3, 0, 10), timedelta(days=1)),
    ("America/New_York", (1320, 420), 10, (2026, 3, 7, 23, 30), timedelta(days=1)),
    ("America/New_York", (1320, 420), 10, (2026, 10, 31, 23, 30), timedelta(days=1)),
    ("America/New_York", (1320, 150), 10, (2026, 3, 7, 23, 30), timedelta(days=1)),
    ("Europe/London", (780, 900), 30, (2026, 6, 1, 14, 0), timedelta(days=1)),
    # Set 3 minutes before it is due: when due, and then after quiet hours.
    ("UTC", None, 10, (2026, 1, 2, 12, 0), timedelta(minutes=3)),
    ("UTC", (1320, 420), 10, (2026, 1, 2, 23, 0), timedelta(minutes=3)),
    # Set an hour after its time, during quiet hours: the next morning.
    ("UTC", (1320, 420), 10, (2026, 1, 2, 22, 0), -timedelta(hours=1)),
]


@pytest.mark.parametrize("tz, window, lead, due, set_before", _SCENARIOS)
def test_the_push_scheduler_sends_at_the_instant_the_phone_schedules(
    tz: str,
    window: tuple[int, int] | None,
    lead: int,
    due: tuple[int, int, int, int, int],
    set_before: timedelta,
) -> None:
    user = make_user(
        timezone=tz,
        reminder_lead_minutes=lead,
        quiet_hours_enabled=window is not None,
        quiet_hours_start_minute=window[0] if window else 1320,
        quiet_hours_end_minute=window[1] if window else 420,
    )
    year, month, day, hour, minute = due
    due_at = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz)).astimezone(UTC)
    todo = _todo(due_at, set_at=due_at - set_before)
    notify_at = reminder_instant(todo, user)
    assert notify_at is not None
    start = min(due_at, todo.due_set_at) - timedelta(hours=2)
    assert _first_push_minute(todo, user, start=start) == _ceil_minute(notify_at)


def test_the_measured_case_reminds_at_seven_not_twenty_past_eleven() -> None:
    user = make_user(timezone="America/New_York", reminder_lead_minutes=10)
    user.quiet_hours_enabled = True
    due = datetime(2026, 1, 2, 23, 30, tzinfo=NEW_YORK)
    notify_at = reminder_instant(_todo(due), user)
    assert notify_at == datetime(2026, 1, 3, 7, 0, tzinfo=NEW_YORK)


@pytest.mark.parametrize(
    "change", [{"checked": True}, {"due_at": None}], ids=["completed", "undated"]
)
def test_no_instant_for_a_completed_or_undated_todo(change: dict[str, object]) -> None:
    todo = _todo(datetime(2026, 1, 2, 12, tzinfo=UTC))
    for key, value in change.items():
        setattr(todo, key, value)
    assert reminder_instant(todo, make_user()) is None


def test_no_push_inside_quiet_hours_even_for_an_instant_already_past() -> None:
    """A cycle that runs late (a worker that was down) still waits out the night."""
    user = make_user(quiet_hours_enabled=True)
    todo = _todo(datetime(2026, 1, 2, 20, 0, tzinfo=UTC))
    assert reminder_instant(todo, user) == datetime(2026, 1, 2, 19, 50, tzinfo=UTC)
    assert is_due_now(todo, user, now=datetime(2026, 1, 2, 21, 0, tzinfo=UTC))
    assert not is_due_now(todo, user, now=datetime(2026, 1, 2, 23, 0, tzinfo=UTC))
    assert is_due_now(todo, user, now=datetime(2026, 1, 3, 7, 0, tzinfo=UTC))


# ── Against Postgres: the page the phone reads and the push the scheduler sends ──


async def _push_user(session, **columns: object):
    user = await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Push User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )
    for key, value in columns.items():
        setattr(user, key, value)
    session.add(
        PushToken(user_id=user.id, expo_push_token=f"ExponentPushToken[{uuid4()}]", platform="ios")
    )
    await session.flush()
    return user


async def _page_notify_at(session, user) -> dict[str, str | None]:
    app = FastAPI()
    app.include_router(todos_router.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/todos/page")
    assert response.status_code == 200
    return {item["content"]: item["notify_at"] for item in response.json()["items"]}


async def _pushed_now(session, now: datetime) -> list[str]:
    page = await push_service.collect_push_page(session, now=now)
    return [m.message["body"] for m in page.messages]


async def test_the_page_notify_at_is_the_minute_push_sends(db_session) -> None:
    user = await _push_user(
        db_session,
        timezone="America/New_York",
        reminder_lead_minutes=10,
        quiet_hours_enabled=True,
        quiet_hours_start_minute=1320,
        quiet_hours_end_minute=420,
        push_notifications_enabled=True,
    )
    # Far from rows other tests leave: the push scan names no user.
    due = datetime(2032, 1, 2, 23, 30, tzinfo=NEW_YORK)
    db_session.add(
        TodoItem(
            user_id=user.id,
            content="Night dentist call",
            due_at=due,
            due_set_at=due - timedelta(days=3),
        )
    )
    await db_session.flush()

    notify_at = datetime.fromisoformat(
        str((await _page_notify_at(db_session, user))["Night dentist call"])
    )
    assert notify_at == datetime(2032, 1, 3, 7, 0, tzinfo=NEW_YORK)
    # The phone alerted at 23:20 before; push never did.
    assert await _pushed_now(db_session, due - timedelta(minutes=10)) == []
    assert await _pushed_now(db_session, notify_at - timedelta(minutes=1)) == []
    assert await _pushed_now(db_session, notify_at) == ["Night dentist call"]


async def test_a_delivery_leaves_the_instant_where_it_was(db_session) -> None:
    """A sent stamp is not an edit: updated_at and the instant stay where they were (a moved
    instant meant a second alert on a device without a token)."""
    user = await _push_user(db_session, reminder_lead_minutes=10)
    now = datetime.now(UTC)
    set_at = now - timedelta(days=1)
    pushed = TodoItem(user_id=user.id, content="Pushed", due_at=now + timedelta(minutes=5))
    emailed = TodoItem(user_id=user.id, content="Emailed", due_at=now + timedelta(minutes=6))
    db_session.add_all([pushed, emailed])
    await db_session.flush()
    for todo in (pushed, emailed):
        todo.updated_at = set_at
        todo.due_set_at = set_at
    await db_session.flush()
    before = {todo.content: reminder_instant(todo, user) for todo in (pushed, emailed)}

    assert await mark_reminder_pushed(db_session, pushed, now=now)
    assert await mark_reminder_emailed(
        db_session, TodoEmailSnapshot.from_todo(emailed), sent_at=now
    )
    for todo in (pushed, emailed):
        await db_session.refresh(todo)
        assert todo.updated_at == set_at
        assert reminder_instant(todo, user) == before[todo.content]
    assert pushed.notification_sent_at == now
    assert emailed.email_sent_at == now


async def _patch(session, user, todo_id, body: dict[str, object]) -> dict[str, object]:
    app = FastAPI()
    app.include_router(todos_router.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(f"/todos/{todo_id}", json=body)
    assert response.status_code == 200
    return response.json()


async def _set_yesterday(session, *, due: datetime, user) -> TodoItem:
    """A to-do due at ``due`` whose time was set the day before."""
    todo = TodoItem(user_id=user.id, content="Call the dentist", due_at=due)
    session.add(todo)
    await session.flush()
    yesterday = due - timedelta(days=1)
    todo.updated_at = yesterday
    todo.due_set_at = yesterday
    await session.flush()
    return todo


@pytest.mark.parametrize(
    "edits",
    [
        [{"content": "Call the dentist back"}],
        [{"sort_order": 3}],
        [{"topic": "Health"}],
        [{"checked": True}, {"checked": False}],
    ],
    ids=["title", "reorder", "category", "uncheck"],
)
async def test_an_edit_that_keeps_the_due_time_keeps_the_reminder(
    db_session, edits: list[dict[str, object]]
) -> None:
    """The instant read when the to-do last changed, so an edit inside the lead window, after
    the reminder went out at due - lead, moved it to the due time: a phone without push,
    which schedules its own alert at notify_at, alerted a second time."""
    user = await _push_user(db_session, reminder_lead_minutes=10)
    due = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=5)
    todo = await _set_yesterday(db_session, due=due, user=user)
    went_out = reminder_instant(todo, user)
    assert went_out == due - timedelta(minutes=10)

    for body in edits:
        saved = await _patch(db_session, user, todo.id, body)
    assert datetime.fromisoformat(str(saved["notify_at"])) == went_out


async def test_a_due_time_set_inside_its_lead_window_still_goes_out_when_due(db_session) -> None:
    user = await _push_user(db_session, reminder_lead_minutes=10)
    now = datetime.now(UTC).replace(microsecond=0)
    todo = await _set_yesterday(db_session, due=now + timedelta(days=1), user=user)

    saved = await _patch(
        db_session, user, todo.id, {"due_at": (now + timedelta(minutes=5)).isoformat()}
    )
    assert datetime.fromisoformat(str(saved["notify_at"])) == now + timedelta(minutes=5)
