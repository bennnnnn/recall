"""The push scheduler's per-minute scans, against Postgres.

* "Aged unsent reminders" counted every old unsent dated to-do, whatever the
  user's push settings, so it logged a WARNING every minute forever (everyone
  who denied notification permission keeps such rows).
* A user without a push token got one WARNING per to-do per minute for up to
  48h (push is on by default).
* The reminder query matched every unsent row due before now + 60 min, so the
  scan grew with every to-do that ever aged out.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.orm import PushToken, TodoItem
from app.modules.notifications import push as push_service
from app.repositories import users as users_repo
from app.services.reminder_timing import OVERDUE_MAX_HOURS

# Far from any row another test may leave behind; both scans are global.
NOW = datetime(2031, 3, 1, 12, 0, tzinfo=UTC)
JUST_AGED = NOW - timedelta(hours=OVERDUE_MAX_HOURS, seconds=30)


async def _user(session, *, push: bool = True, token: bool = True):
    user = await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Push User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )
    user.push_notifications_enabled = push
    if token:
        session.add(
            PushToken(
                user_id=user.id, expo_push_token=f"ExponentPushToken[{uuid4()}]", platform="ios"
            )
        )
    await session.flush()
    return user


def _todo(session, user, due_at: datetime, content: str = "Call the dentist") -> TodoItem:
    item = TodoItem(user_id=user.id, content=content, due_at=due_at)
    session.add(item)
    return item


async def test_aged_unsent_counts_only_push_eligible_rows_that_just_aged_out(db_session):
    eligible = await _user(db_session)
    tokenless = await _user(db_session, token=False)
    push_off = await _user(db_session, push=False)
    _todo(db_session, eligible, JUST_AGED)
    _todo(db_session, eligible, NOW - timedelta(hours=OVERDUE_MAX_HOURS + 24), "Old one")
    _todo(db_session, tokenless, JUST_AGED)
    _todo(db_session, push_off, JUST_AGED)
    await db_session.flush()

    assert await push_service.log_aged_unsent_reminders(db_session, now=NOW) == 1
    # The next cycle no longer counts it: each aged row is reported once.
    later = NOW + push_service.AGED_UNSENT_WINDOW
    assert await push_service.log_aged_unsent_reminders(db_session, now=later) == 0


async def test_tokenless_reminders_are_not_a_warning_per_todo(
    db_session, caplog: pytest.LogCaptureFixture
):
    with_token = await _user(db_session)
    tokenless = await _user(db_session, token=False)
    _todo(db_session, with_token, NOW + timedelta(minutes=5), "Due soon")
    _todo(db_session, with_token, NOW - timedelta(hours=OVERDUE_MAX_HOURS + 1), "Aged out")
    for n in range(3):
        _todo(db_session, tokenless, NOW + timedelta(minutes=n + 1), f"Tokenless {n}")
    await db_session.flush()

    with caplog.at_level(logging.DEBUG, logger="app.modules.notifications.push"):
        messages = await push_service.process_todo_reminders(db_session, now=NOW)

    assert [m.message["body"] for m in messages] == ["Due soon"]
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert "no push token users=1" in caplog.text
