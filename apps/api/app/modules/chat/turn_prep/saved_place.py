"""The place the phone last saved, as a turn without a fix of its own may use it.

A place the phone saved within the hour is where the user is. Older, it is where they last
were, and the prompt and the "Where am I?" answer say so; past a day it answers nothing:
San Francisco saved in the morning answered "What's the weather tomorrow?" in New York that
evening as if it were current (review, 2026-11-09). The phone saves its place on each
return to the app once it is an hour old, so a saved place this old is one the phone could
not read since.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.timezone import resolve_timezone
from app.models.orm import User
from app.modules.account import profile as profile_service

SAVED_PLACE_CURRENT = timedelta(hours=1)
SAVED_PLACE_MAX_AGE = timedelta(hours=24)


def saved_place(user: User, now: datetime) -> tuple[str | None, datetime | None]:
    """The place the phone last saved, if a turn may use it, and its time when not current."""
    label = profile_service.user_location_label(user)
    saved_at = user.location_saved_at if isinstance(user.location_saved_at, datetime) else None
    if not label or saved_at is None or now - saved_at > SAVED_PLACE_MAX_AGE:
        return None, None
    return label, saved_at if now - saved_at > SAVED_PLACE_CURRENT else None


def _reported_when(as_of: datetime, timezone: str | None) -> str:
    """When the phone reported a place: "at 9:05 AM, about 6 hours ago"."""
    now = datetime.now(resolve_timezone(timezone))
    hours = max(1, round((now - as_of).total_seconds() / 3600))
    ago = "about an hour ago" if hours == 1 else f"about {hours} hours ago"
    return f"at {as_of.astimezone(now.tzinfo).strftime('%I:%M %p').lstrip('0')}, {ago}"


def last_reported_place(location: str, as_of: datetime, timezone: str | None) -> str:
    """A saved place that is no longer current, as the prompt gives it."""
    return (
        f"{location} (where the phone last reported, {_reported_when(as_of, timezone)}; "
        "the user may have moved since, so say it is that place when it matters)"
    )


def last_report_answer(location: str, as_of: datetime, timezone: str | None) -> str:
    """The answer to "Where am I?" from a saved place that is no longer current."""
    now = datetime.now(resolve_timezone(timezone))
    time_str = now.strftime("%A, %B %d, %Y at %I:%M %p %Z")
    return (
        f"Your phone last reported **{location}**, {_reported_when(as_of, timezone)}. "
        f"Local time: {time_str}."
    )
