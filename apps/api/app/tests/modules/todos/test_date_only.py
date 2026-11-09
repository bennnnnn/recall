"""A to-do with a date and no time (``due_has_time`` false, ``modules/todos/due_day.py``).

Picking a date on the phone wrote a time with it (9:00, or the next hour), so a date alone
came with a time, a "Remind at" and a reminder. A date alone is held at the start of its
day on the user's clock, nothing reminds of it, it is overdue only once that day has
ended, a repeat moves its day, and it stays on its day when the user's zone changes.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import PushToken, TodoItem
from app.modules.notifications import push as push_service
from app.modules.todos import api as todos_router
from app.modules.todos import crud as todos_crud
from app.modules.todos import due_day, prompt_context, proposals, service
from app.modules.todos import repository as todos_repo
from app.modules.todos.due_reminders import (
    PUSH_REMINDERS,
    aged_out_unsent,
    due_reminder_page,
    is_due_now,
    reminder_instant,
)
from app.modules.todos.recurrence import next_open_due
from app.modules.todos.reminder_writes import (
    ReminderWrites,
    _existing_open_match,
    format_schedule_when,
)
from app.modules.todos.schedule_repository import move_due_day_if_current
from app.modules.todos.schemas import TodoUpdate
from app.modules.todos.spoken_apply import _apply_saved_fields, format_reminder_reading
from app.modules.todos.write_log import PlannedWrite
from app.repositories import users as users_repo
from app.tests.fakes import fake_session, isolated_settings, make_user

NEW_YORK = ZoneInfo("America/New_York")
# 10 November 2026 begins at 05:00 UTC in New York (EST).
NOV_10_NY = datetime(2026, 11, 10, 5, tzinfo=UTC)


def _date_alone(**columns: Any) -> TodoItem:
    fields: dict[str, Any] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "content": "Pay rent",
        "topic": "General",
        "checked": False,
        "due_at": NOV_10_NY,
        "due_has_time": False,
        "recurrence_rule": None,
        "due_set_at": NOV_10_NY - timedelta(days=3),
    }
    return TodoItem(**(fields | columns))


def _call(mock: Any) -> Any:
    """The last await of ``mock``, which must have been awaited."""
    assert mock.await_args is not None
    return mock.await_args


def _sql(statement: Any) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


# ── the day ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "picked",
    [
        datetime(2026, 11, 10),  # the phone's naive local midnight
        datetime(2026, 11, 10, 17, 45),  # any time that day
        datetime(2026, 11, 10, 0, 0, tzinfo=NEW_YORK),
        datetime(2026, 11, 11, 4, 59, tzinfo=UTC),  # 23:59 in New York
    ],
)
def test_a_date_alone_is_held_at_the_start_of_its_day(picked: datetime) -> None:
    assert due_day.stored_due(picked, "America/New_York", has_time=False) == NOV_10_NY


def test_a_time_is_stored_as_its_instant() -> None:
    naive = datetime(2026, 11, 10, 9, 0)
    stored = due_day.stored_due(naive, "America/New_York", has_time=True)
    assert stored == datetime(2026, 11, 10, 14, tzinfo=UTC)


def test_a_date_alone_is_overdue_when_its_day_ends_not_at_its_start() -> None:
    end = due_day.overdue_from(NOV_10_NY, "America/New_York", has_time=False)
    assert end == datetime(2026, 11, 11, 5, tzinfo=UTC)
    assert due_day.overdue_from(NOV_10_NY, "America/New_York", has_time=True) == NOV_10_NY


def test_a_flight_keeps_the_day() -> None:
    # New York's midnight is 21:00 the day before in Los Angeles.
    moved = due_day.same_day_in(NOV_10_NY, "America/New_York", "America/Los_Angeles")
    assert moved == datetime(2026, 11, 10, 8, tzinfo=UTC)


def test_the_model_reads_a_date_alone_by_its_day() -> None:
    zone = ZoneInfo("Asia/Tokyo")
    today = due_day.start_of_day(datetime.now(zone), "Asia/Tokyo")
    assert due_day.describe_due(today, "Asia/Tokyo", has_time=False) == "due today"
    yesterday = due_day.start_of_day(datetime.now(zone) - timedelta(days=1), "Asia/Tokyo")
    assert due_day.describe_due(yesterday, "Asia/Tokyo", has_time=False) == "overdue by 1 day"
    # Read as a time, the start of today has passed.
    assert due_day.describe_due(today, "Asia/Tokyo", has_time=True).startswith("overdue")


# ── no reminder ────────────────────────────────────────────────────────────


def test_nothing_reminds_of_a_date_alone() -> None:
    user = make_user(timezone="America/New_York", reminder_lead_minutes=10)
    rent = _date_alone()
    assert reminder_instant(rent, user) is None
    assert not is_due_now(rent, user, now=NOV_10_NY + timedelta(hours=9))
    timed = _date_alone(due_has_time=True)
    assert reminder_instant(timed, user) == NOV_10_NY - timedelta(minutes=10)


@pytest.mark.asyncio
async def test_push_and_email_never_read_a_date_alone() -> None:
    session = fake_session()
    session.execute.return_value = MagicMock(all=lambda: [])
    await due_reminder_page(session, PUSH_REMINDERS, now=NOV_10_NY)
    assert "todo_items.due_has_time = true" in _sql(_call(session.execute).args[0])
    session.scalar.return_value = 0
    await aged_out_unsent(session, PUSH_REMINDERS, now=NOV_10_NY, window=timedelta(hours=1))
    # One that aged out was never a delivery failure.
    assert "todo_items.due_has_time = true" in _sql(_call(session.scalar).args[0])


@pytest.mark.asyncio
async def test_todays_date_alone_does_not_crowd_the_overdue_probe() -> None:
    session = fake_session()
    await todos_repo.list_due_soon(session, uuid4(), before_utc=NOV_10_NY)
    sql = _sql(_call(session.execute).args[0])
    assert "todo_items.due_has_time IS true OR todo_items.due_at <=" in sql


# ── saving ─────────────────────────────────────────────────────────────────


def test_a_patch_names_the_flag_or_leaves_it_out() -> None:
    assert TodoUpdate.model_validate({"due_has_time": False}).due_has_time is False
    assert "due_has_time" not in TodoUpdate.model_validate({"content": "x"}).model_fields_set
    with pytest.raises(ValueError):
        TodoUpdate.model_validate({"due_has_time": None})


@pytest.mark.asyncio
async def test_create_holds_a_date_alone_at_its_day() -> None:
    user: Any = SimpleNamespace(id=uuid4(), timezone="America/New_York")
    create = AsyncMock(return_value=MagicMock())
    with patch.object(todos_repo, "create", create):
        await todos_crud.create_todo(
            fake_session(),
            user,
            content="Pay rent",
            topic=None,
            chat_id=None,
            due_at=datetime(2026, 11, 10),
            due_has_time=False,
        )
    assert _call(create).kwargs["due_at"] == NOV_10_NY
    assert _call(create).kwargs["due_has_time"] is False


async def _patched(item: Any, fields: dict[str, Any], *, now: datetime | None = None) -> Any:
    user: Any = SimpleNamespace(id=uuid4(), timezone="America/New_York")
    update = AsyncMock(return_value=MagicMock())
    clock = MagicMock(now=lambda tz: now or datetime(2026, 11, 1, tzinfo=UTC))
    with (
        patch.object(todos_repo, "get_by_id", AsyncMock(return_value=item)),
        patch.object(todos_repo, "update", update),
        patch.object(todos_crud, "datetime", clock),
    ):
        await todos_crud.update_todo(fake_session(), user, uuid4(), fields)
    return _call(update).kwargs


@pytest.mark.asyncio
async def test_taking_the_time_off_keeps_the_day() -> None:
    nine = datetime(2026, 11, 10, 14, tzinfo=UTC)
    written = await _patched(_date_alone(due_at=nine, due_has_time=True), {"due_has_time": False})
    assert written == {"due_at": NOV_10_NY, "due_has_time": False}


@pytest.mark.asyncio
async def test_a_time_given_to_a_date_alone_makes_it_timed() -> None:
    nine = datetime(2026, 11, 10, 9, 0)
    written = await _patched(_date_alone(), {"due_at": nine})
    assert written == {"due_at": datetime(2026, 11, 10, 14, tzinfo=UTC), "due_has_time": True}


@pytest.mark.asyncio
async def test_a_title_edit_that_sends_the_date_back_keeps_it_alone() -> None:
    # An app that never heard of the flag sends due_at back unchanged with the new title.
    written = await _patched(_date_alone(), {"content": "Rent", "due_at": NOV_10_NY})
    assert written["due_at"] == NOV_10_NY and written["due_has_time"] is False


@pytest.mark.asyncio
async def test_ticking_a_repeating_date_alone_moves_its_day_without_a_time() -> None:
    daily = _date_alone(recurrence_rule="daily")
    written = await _patched(daily, {"checked": True}, now=NOV_10_NY + timedelta(hours=15))
    assert written == {"due_at": NOV_10_NY + timedelta(days=1), "due_has_time": False}


@pytest.mark.asyncio
async def test_a_write_that_names_no_flag_gives_a_new_due_at_a_time() -> None:
    # Chat and live talk always give a time, and never pass the flag.
    retimed = _date_alone()
    await todos_repo.update(
        fake_session(), retimed, commit=False, due_at=NOV_10_NY + timedelta(hours=9)
    )
    assert retimed.due_has_time is True
    kept = _date_alone()
    await todos_repo.update(fake_session(), kept, commit=False, content="Rent", due_at=NOV_10_NY)
    assert kept.due_has_time is False


# ── repeats ────────────────────────────────────────────────────────────────


def test_a_repeating_date_alone_stays_on_today_until_today_ends() -> None:
    yesterday = NOV_10_NY - timedelta(days=1)
    now = NOV_10_NY + timedelta(hours=20)
    nxt = next_open_due(yesterday, "daily", has_time=False, now=now, timezone="America/New_York")
    assert nxt == NOV_10_NY
    timed = next_open_due(yesterday, "daily", has_time=True, now=now, timezone="America/New_York")
    assert timed == NOV_10_NY + timedelta(days=1)


@pytest.mark.asyncio
async def test_the_list_moves_a_past_repeating_date_alone_on_even_with_push_on() -> None:
    user: Any = SimpleNamespace(
        id=uuid4(),
        timezone="America/New_York",
        push_notifications_enabled=True,
        push_reminders_enabled=True,
    )
    passed = _date_alone(due_at=NOV_10_NY - timedelta(days=2), recurrence_rule="daily")
    timed = _date_alone(due_at=NOV_10_NY - timedelta(days=2), recurrence_rule="daily")
    timed.due_has_time = True
    advance = AsyncMock(return_value=False)
    with (
        patch.object(todos_repo, "list_after_id", AsyncMock(return_value=[passed, timed])),
        patch.object(todos_crud, "advance_past_recurring", advance),
    ):
        await todos_crud.list_todos_page(fake_session(), user)
    # Push moves the timed one as it goes out; nothing goes out for the date alone.
    assert _call(advance).args[1] == [passed]


# ── what chat and live talk read ───────────────────────────────────────────


def test_the_prompt_says_a_date_alone_has_no_time() -> None:
    today = due_day.start_of_day(datetime.now(UTC), "UTC")
    block = prompt_context.format_todos_block([_date_alone(due_at=today)], user_timezone="UTC")
    assert "Pay rent (date only, no time), due today" in block
    assert "00:00" not in block and "overdue" not in block


def test_a_reading_aloud_names_the_day_alone() -> None:
    reading = format_reminder_reading([_date_alone()], "America/New_York")
    assert reading == "Pay rent — Tuesday, Nov 10."
    assert format_schedule_when(NOV_10_NY, "America/New_York", has_time=True).endswith("12:00 AM")


def test_a_card_shows_a_date_alone_as_its_day() -> None:
    write = PlannedWrite(kind="update", todo_id=uuid4(), title="Pay rent", fields={"due_at": 1})
    write.due_at, write.has_time = NOV_10_NY, False
    card = proposals.card_item(write, "America/New_York")
    # No instant the phone would draw at midnight.
    assert card.due_at is None and card.when == "Tuesday, Nov 10"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change", "timed", "line"),
    [
        ({"shift_days": 1}, False, "Moved: Pay rent — Wednesday, Jan 7."),
        (
            {"keep_date": True, "hour": 18, "minute": 0},
            True,
            "Moved: Pay rent — Tuesday, Jan 6, 6:00 PM.",
        ),
    ],
)
async def test_a_spoken_move_keeps_a_date_alone_and_a_clock_gives_it_a_time(
    change: dict[str, Any], timed: bool, line: str
) -> None:
    spoken: Any = SimpleNamespace(
        keep_date=False, hour=None, minute=None, day=None, shift_days=0, repeat=None, topic=None
    )
    for key, value in change.items():
        setattr(spoken, key, value)
    update = AsyncMock()
    # A day still to come, so the clock said is on it.
    rent = _date_alone(due_at=datetime(2032, 1, 6, tzinfo=NEW_YORK))
    with patch.object(todos_repo, "update", update):
        said, ok = await _apply_saved_fields(
            fake_session(),
            rent,
            spoken,
            title="Pay rent",
            user_timezone="America/New_York",
        )
    assert ok and said == line
    assert _call(update).kwargs["due_has_time"] is timed


# ── a new zone ─────────────────────────────────────────────────────────────


class _Savepoint:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _apia(day: int) -> TodoItem:
    return _date_alone(
        due_at=due_day.stored_due(datetime(2026, 11, day), "Pacific/Apia", has_time=False)
    )


@pytest.mark.asyncio
async def test_a_new_zone_moves_each_date_alone_furthest_first_and_only_if_unchanged() -> None:
    # Apia to Pago Pago: the 10th's new start is the 11th's old one.
    session = fake_session()
    session.begin_nested = MagicMock(return_value=_Savepoint())
    tenth, eleventh = _apia(10), _apia(11)
    move = AsyncMock(return_value=True)
    with (
        patch.object(todos_repo, "list_date_only", AsyncMock(return_value=[tenth, eleventh])),
        patch.object(service, "move_due_day_if_current", move),
    ):
        await service.keep_date_only_days(
            session, tenth.user_id, old_timezone="Pacific/Apia", new_timezone="Pacific/Pago_Pago"
        )
    first, second = ((*c.args[1:], c.kwargs["was"], c.kwargs["to"]) for c in move.await_args_list)
    assert first[0] == eleventh.id and second[0] == tenth.id
    # Each names the day it was read at, so an edit made meanwhile is left alone.
    assert first[1] == eleventh.due_at and second[1] == tenth.due_at
    assert second[2] == eleventh.due_at


@pytest.mark.asyncio
async def test_a_clash_at_one_new_midnight_never_holds_the_others_back() -> None:
    session = fake_session()
    session.begin_nested = MagicMock(return_value=_Savepoint())
    clash = IntegrityError("UPDATE", {}, Exception("uq_todo_open_content_due"))
    move = AsyncMock(side_effect=[clash, True])
    with (
        patch.object(todos_repo, "list_date_only", AsyncMock(return_value=[_apia(10), _apia(20)])),
        patch.object(service, "move_due_day_if_current", move),
    ):
        await service.keep_date_only_days(
            session, uuid4(), old_timezone="UTC", new_timezone="Asia/Tokyo"
        )
    assert move.await_count == 2


@pytest.mark.asyncio
async def test_a_moved_day_writes_only_the_row_as_it_was_read() -> None:
    session = fake_session()
    session.execute.return_value = MagicMock(rowcount=0)
    later = NOV_10_NY + timedelta(hours=3)
    moved = await move_due_day_if_current(session, uuid4(), was=NOV_10_NY, to=later)
    sql = _sql(_call(session.execute).args[0])
    assert not moved
    assert "todo_items.due_at = " in sql and "todo_items.due_has_time IS false" in sql


@pytest.mark.asyncio
@pytest.mark.parametrize("zone", ["America/Los_Angeles", "America/New_York"])
async def test_a_new_profile_zone_moves_the_days_in_the_same_commit(zone: str) -> None:
    from app.modules.account import lifecycle

    user = make_user(timezone="America/New_York")
    session = fake_session()
    order: list[str] = []
    session.commit.side_effect = lambda: order.append("commit")
    keep = AsyncMock(side_effect=lambda *_a, **_k: order.append("keep"))
    with (
        patch.object(lifecycle.users_repo, "update", AsyncMock(return_value=user)) as update,
        patch.object(lifecycle.todos_service, "keep_date_only_days", keep),
        patch.object(lifecycle.user_cache, "publish_change", AsyncMock()),
    ):
        await lifecycle.update_account(session, user, isolated_settings(), {"timezone": zone})
    if zone == "America/New_York":
        # The same zone again (every foreground): nothing to move.
        keep.assert_not_awaited()
        return
    assert order == ["keep", "commit"]
    assert _call(update).kwargs["commit"] is False
    assert _call(keep).kwargs == {"old_timezone": "America/New_York", "new_timezone": zone}


# ── review: a card for today, an older app, the profile's zone, duplicates ──


def test_a_card_can_move_a_date_alone_to_today() -> None:
    today = due_day.start_of_day(datetime.now(UTC), "UTC")
    alone = {"due_at": today, "due_has_time": False}
    assert proposals._upcoming(alone, "UTC") == alone
    daily = proposals._upcoming({**alone, "recurrence_rule": "daily"}, "UTC")
    assert daily["due_at"] == today
    with pytest.raises(proposals.ProposalError):
        proposals._upcoming({**alone, "due_at": today - timedelta(days=1)}, "UTC")
    with pytest.raises(proposals.ProposalError):
        proposals._upcoming({"due_at": datetime.now(UTC) - timedelta(minutes=1)}, "UTC")


@pytest.mark.asyncio
async def test_an_older_app_moving_a_date_alone_keeps_it_alone() -> None:
    # An app without the flag keeps the 00:00 it showed: the 12th's start in New York.
    twelfth = datetime(2026, 11, 12, 5, tzinfo=UTC)
    written = await _patched(_date_alone(), {"due_at": twelfth})
    assert written == {"due_at": twelfth, "due_has_time": False}


def test_the_phone_reads_a_date_alone_by_the_day_the_profile_holds() -> None:
    tokyo = "Asia/Tokyo"
    held = due_day.stored_due(datetime(2026, 11, 10), tokyo, has_time=False)
    stamp = datetime(2026, 11, 1, tzinfo=UTC)
    rent = _date_alone(due_at=held, created_at=stamp, updated_at=stamp)
    # The instant is the 9th in UTC; the day is Tokyo's 10th.
    out = todos_router._todo_out(rent, make_user(timezone=tokyo))
    assert out.due_date == date(2026, 11, 10)
    rent.due_has_time = True
    assert todos_router._todo_out(rent, make_user(timezone=tokyo)).due_date is None


def _spoken(**change: Any) -> Any:
    fields: dict[str, Any] = {
        "keep_date": False,
        "hour": None,
        "minute": None,
        "day": None,
        "shift_days": 0,
        "repeat": None,
        "topic": None,
    }
    return SimpleNamespace(**(fields | change))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", [{"day": "friday"}, {"keep_date": True, "hour": 18, "minute": 0}]
)
async def test_a_spoken_change_reads_a_date_alone_in_the_profiles_zone(
    change: dict[str, Any],
) -> None:
    # Profile New York, phone in Los Angeles, where New York's midnight is 21:00 the day before.
    session = fake_session()
    session.get = AsyncMock(return_value=SimpleNamespace(timezone="America/New_York"))
    tuesday = _date_alone(due_at=datetime(2032, 1, 6, tzinfo=NEW_YORK))
    update = AsyncMock()
    with patch.object(todos_repo, "update", update):
        said, ok = await _apply_saved_fields(
            session,
            tuesday,
            _spoken(**change),
            title="Pay rent",
            user_timezone="America/Los_Angeles",
        )
    moved = _call(update).kwargs["due_at"]
    if change.get("day"):
        assert due_day.local_day(moved, "America/New_York").weekday() == 4
        assert moved == due_day.start_of_day(moved, "America/New_York")
        assert ok and said.startswith("Moved: Pay rent — Friday, ")
    else:
        # The clock said is the phone's, on the date alone's own day.
        los_angeles = ZoneInfo("America/Los_Angeles")
        assert moved.astimezone(los_angeles) == datetime(2032, 1, 6, 18, tzinfo=los_angeles)


@pytest.mark.asyncio
async def test_a_date_alone_never_comes_back_as_a_timed_duplicate() -> None:
    user: Any = SimpleNamespace(id=uuid4(), timezone="America/New_York")
    clash = IntegrityError("insert", {}, Exception("uq_todo_open_content_due"))
    duplicate = AsyncMock(return_value=None)
    with (
        patch.object(todos_repo, "create", AsyncMock(side_effect=clash)),
        patch.object(todos_repo, "get_open_dated_duplicate", duplicate),
        pytest.raises(todos_crud.TodosError) as refused,
    ):
        await todos_crud.create_todo(
            fake_session(),
            user,
            content="Pay rent",
            topic=None,
            chat_id=None,
            due_at=datetime(2026, 11, 10),
            due_has_time=False,
        )
    assert _call(duplicate).kwargs["due_has_time"] is False
    assert refused.value.detail == "You already have this to-do on that day."


@pytest.mark.asyncio
async def test_a_duplicate_is_one_of_the_same_kind() -> None:
    session = fake_session()
    await todos_repo.get_open_dated_duplicate(
        session, uuid4(), content="Pay rent", due_at=NOV_10_NY, due_has_time=False
    )
    assert "todo_items.due_has_time IS false" in _sql(_call(session.execute).args[0])
    state = ReminderWrites(
        session=fake_session(), user_id=uuid4(), chat_id=uuid4(), user_timezone="America/New_York"
    )
    state.existing = [_date_alone()]
    # Chat's "pay rent at midnight" is not the date alone at that midnight.
    assert _existing_open_match(state, "Pay rent", NOV_10_NY) is None


@pytest.mark.asyncio
async def test_an_edit_clash_on_a_date_alone_says_day_not_time() -> None:
    user: Any = SimpleNamespace(id=uuid4(), timezone="America/New_York")
    clash = IntegrityError("update", {}, Exception("uq_todo_open_content_due"))
    with (
        patch.object(todos_repo, "get_by_id", AsyncMock(return_value=_date_alone())),
        patch.object(todos_repo, "update", AsyncMock(side_effect=clash)),
        pytest.raises(todos_crud.TodosError) as refused,
    ):
        await todos_crud.update_todo(fake_session(), user, uuid4(), {"content": "Rent"})
    assert refused.value.detail == "You already have this to-do on that day."


# ── against Postgres ───────────────────────────────────────────────────────


async def _user(session: Any, **columns: object) -> Any:
    user = await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Date User",
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


async def test_a_date_saved_alone_has_no_notify_at_and_no_push(db_session: Any) -> None:
    user = await _user(
        db_session,
        timezone="America/New_York",
        reminder_lead_minutes=10,
        push_notifications_enabled=True,
    )
    app = FastAPI()
    app.include_router(todos_router.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/todos",
            json={"content": "Pay rent", "due_at": "2032-01-02T00:00:00", "due_has_time": False},
        )
        page = await client.get("/todos/page")
    assert created.status_code == 201
    row = created.json()
    assert row["due_has_time"] is False and row["notify_at"] is None
    assert datetime.fromisoformat(row["due_at"]) == datetime(2032, 1, 2, tzinfo=NEW_YORK)
    assert [item["notify_at"] for item in page.json()["items"]] == [None]
    pushed = await push_service.collect_push_page(
        db_session, now=datetime(2032, 1, 2, 9, tzinfo=NEW_YORK)
    )
    assert "Pay rent" not in [m.message["body"] for m in pushed.messages]


async def test_a_new_zone_moves_a_date_alone_and_keeps_its_updated_at(db_session: Any) -> None:
    user = await _user(db_session, timezone="America/New_York")
    edited = datetime(2031, 12, 1, tzinfo=UTC)
    rent = TodoItem(
        user_id=user.id,
        content="Pay rent",
        due_at=datetime(2032, 1, 2, tzinfo=NEW_YORK),
        due_has_time=False,
        due_set_at=edited,
        updated_at=edited,
    )
    db_session.add(rent)
    await db_session.flush()
    await service.keep_date_only_days(
        db_session, user.id, old_timezone="America/New_York", new_timezone="America/Los_Angeles"
    )
    await db_session.refresh(rent)
    assert rent.due_at == datetime(2032, 1, 2, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert rent.updated_at == edited


async def test_same_titled_days_cross_the_date_line_together(db_session: Any) -> None:
    user = await _user(db_session, timezone="Pacific/Apia")
    stamp = datetime(2026, 11, 1, tzinfo=UTC)
    days = [
        TodoItem(
            user_id=user.id,
            content="Gym",
            due_at=due_day.stored_due(datetime(2026, 11, day), "Pacific/Apia", has_time=False),
            due_has_time=False,
            due_set_at=stamp,
        )
        for day in (10, 11)
    ]
    db_session.add_all(days)
    await db_session.flush()
    await service.keep_date_only_days(
        db_session, user.id, old_timezone="Pacific/Apia", new_timezone="Pacific/Pago_Pago"
    )
    for row, day in zip(days, (10, 11), strict=True):
        await db_session.refresh(row)
        assert row.due_at is not None
        assert due_day.local_day(row.due_at, "Pacific/Pago_Pago") == date(2026, 11, day)


async def test_a_date_alone_and_a_time_at_its_midnight_are_two_to_dos(db_session: Any) -> None:
    user = await _user(db_session, timezone="America/New_York")
    timed = await todos_crud.create_todo(
        db_session, user, content="Pay rent", topic=None, chat_id=None, due_at=NOV_10_NY
    )
    alone = await todos_crud.create_todo(
        db_session,
        user,
        content="Pay rent",
        topic=None,
        chat_id=None,
        due_at=NOV_10_NY,
        due_has_time=False,
    )
    assert alone.id != timed.id and alone.due_has_time is False


async def test_a_new_zone_leaves_a_date_alone_edited_meanwhile(db_session: Any) -> None:
    user = await _user(db_session, timezone="America/New_York")
    rent = TodoItem(
        user_id=user.id,
        content="Pay rent",
        due_at=datetime(2032, 1, 2, tzinfo=NEW_YORK),
        due_has_time=False,
        due_set_at=datetime(2031, 12, 1, tzinfo=UTC),
    )
    db_session.add(rent)
    await db_session.flush()
    read_at = datetime(2032, 1, 2, tzinfo=NEW_YORK)
    rent.due_at = datetime(2032, 1, 5, tzinfo=NEW_YORK)
    await db_session.flush()
    moved = await move_due_day_if_current(
        db_session, rent.id, was=read_at, to=datetime(2032, 1, 2, tzinfo=ZoneInfo("Europe/Paris"))
    )
    await db_session.refresh(rent)
    assert not moved and rent.due_at == datetime(2032, 1, 5, tzinfo=NEW_YORK)


# ── the migration ──────────────────────────────────────────────────────────


def test_every_existing_to_do_keeps_its_time() -> None:
    path = Path(__file__).resolve().parents[4] / "alembic/versions/0127_todo_due_has_time.py"
    spec = importlib.util.spec_from_file_location("todo_due_has_time_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    op = MagicMock()
    module.op = op  # type: ignore[attr-defined]
    module.upgrade()
    table, column = op.add_column.call_args.args
    assert table == "todo_items" and column.name == "due_has_time"
    assert isinstance(column.type, sa.Boolean) and column.nullable is False
    assert column.server_default is not None
    # The open-duplicate unique, under its name, tells a date alone from a time.
    created = " ".join(str(c.args[0]) for c in op.execute.call_args_list)
    assert "CREATE UNIQUE INDEX uq_todo_open_content_due" in created
    assert "lower(content), due_at, due_has_time)" in created
    assert module.down_revision == "0126_user_location_chosen_at"
