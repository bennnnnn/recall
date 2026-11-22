"""Which half of the day an hour said with no am or pm means: one rule, shown on the card.

"Remind me to move my car tmrw at 5" was asked "5 am or 5 pm?" and, answered, often asked
again (live QA, 2026-11-22: 16 of 30 reminder requests got no card). Nobody means 5 in the
morning without saying so, and the card the user taps shows the time it picked, so the
card is the confirmation: an hour said on its own is settled by this rule, never asked.

- 12 is noon (midnight is said as midnight or 12am).
- 1 to 6 are the afternoon or evening: 5 is 5 PM, "call mom at 6" is 6 PM (an early
  morning is said as such: "6am", "6 in the morning").
- 7 to 11 are the first of the two still ahead on that day: "tomorrow at 7" is 7 AM, "today
  at 8" said at 3 PM is 8 PM. With no day, the first still ahead today, else tomorrow's. A
  repeat ("every day at 8") is the morning one, from the next day it falls on.

A part of the day said beside it ("at 9 tonight", "8 in the morning") is read before this
rule, by ``spoken_when``; so is a 24-hour clock ("at 17").
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING

from app.modules.todos.spoken_when import due_on_day

if TYPE_CHECKING:
    from app.modules.todos.spoken_add import SpokenAdd

# The latest hour (12-hour clock) only ever meant after noon when said alone.
_ALWAYS_AFTERNOON = 6


def _candidates(hour: int) -> tuple[int, ...]:
    """The 24-hour hours a 12-hour ``hour`` may mean, earliest first."""
    if hour == 12:
        return (12,)
    if 1 <= hour <= _ALWAYS_AFTERNOON:
        return (hour + 12,)
    return (hour, hour + 12)


def settle_hour(
    hour: int, minute: int, day: str | None, now: datetime, *, repeats: bool = False
) -> tuple[str, int] | None:
    """(day, 24-hour hour) for ``hour`` said with no am or pm, on ``day`` (None: the next
    one); None for an hour outside 1 to 12 or a day the calendar cannot place. ``now`` is
    the user's local time. A repeat ("every day at 8") keeps the earlier half whatever the
    time now: it starts on the next one."""
    if not 1 <= hour <= 12:
        return None
    options = _candidates(hour)
    if repeats:
        options = options[:1]
    for name in [day] if day else ["today", "tomorrow"]:
        for candidate in options:
            due = due_on_day(name, candidate, minute, now)
            if due is None:
                return None
            if due > now:
                return name, candidate
    # All of them passed today: the last, which the caller reports as passed.
    return (day or "tomorrow"), options[-1]


def settle_bare(
    add: SpokenAdd, *, user_timezone: str | None, now: datetime | None = None
) -> SpokenAdd:
    """``add`` with its bare hour (``SpokenAdd.bare``) settled by the rule, and the day it
    falls on when none was said; any other add comes back unchanged."""
    if add.bare is None or add.hour is not None or add.after_minutes is not None:
        return add
    from app.services import time_context as time_context_service

    tz = time_context_service.resolve_timezone(user_timezone)
    local = now.astimezone(tz) if now is not None else datetime.now(tz)
    hour, minute = add.bare
    settled = settle_hour(hour, minute, add.day, local, repeats=add.repeat is not None)
    if settled is None:
        return add
    day, clock = settled
    return replace(add, day=day, hour=clock, minute=minute, bare=None)
