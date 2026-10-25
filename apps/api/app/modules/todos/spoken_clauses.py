"""Several reminders in one message, and the clock that finishes one of them.

"remind me to call mom at 5pm and to pay rent on friday at 9am" saved one
reminder, "call mom and to pay rent at 9am", on Friday at 5 PM. Each clause is
now read on its own, so each keeps its own title and time. A message splits
only when every clause names its own day or clock: "email John and to cc Sarah
at 9am" stays one reminder. A clause with a clock and no day takes the day of
the clause before it ("tomorrow … at 5pm and … at 9am"), else the next such
clock, as a single reminder does.
"""

from __future__ import annotations

import re
from dataclasses import replace
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.todos.spoken_add import SpokenAdd, day_for_a_bare_clock, parse_spoken_add
from app.modules.todos.spoken_when import parse_clock_only

# What starts the first reminder; a later one starts at _NEXT_REMINDER_RE.
_FIRST_REQUEST_RE = re.compile(
    r"\bremind\s+me\b|\b(?:set|create|add|make)\s+(?:me\s+)?(?:a\s+)?reminders?\b",
    re.IGNORECASE,
)
# "…, and remind me to …", ". Also remind me to …", "… and to pay rent …".
_NEXT_REMINDER_RE = re.compile(
    r"(?:\s*[,;]\s*|\s*[.!?]\s+|\s+)(?:and\s+)?(?:also\s+|then\s+|plus\s+)?"
    r"(?:(?:please|pls)\s+)?(?:(?:can|could)\s+you\s+)?remind\s+me\b(?:\s+to\b)?\s*"
    r"|,?\s+and\s+(?:also\s+)?to\s+(?=[^\W\d_])",
    re.IGNORECASE,
)
_REQUEST = "remind me to "


def reminder_clauses(text: str | None) -> list[str]:
    """The message as one request per reminder it asks for; one item when it asks for one."""
    if not text or not text.strip():
        return []
    first = _FIRST_REQUEST_RE.search(text)
    bounds = list(_NEXT_REMINDER_RE.finditer(text, first.end())) if first else []
    if not bounds:
        return [text]
    pieces = [text[: bounds[0].start()]]
    for here, after in zip(bounds, [*bounds[1:], None], strict=True):
        end = after.start() if after is not None else len(text)
        pieces.append(_REQUEST + text[here.end() : end].strip())
    return [piece.strip(" ,;") for piece in pieces if piece.strip(" ,;.!?")]


def parse_spoken_adds(user_text: str | None, *, user_timezone: str | None) -> list[SpokenAdd]:
    """Each add the message states, with the day a clock alone means filled in."""
    clauses = reminder_clauses(user_text)
    split = _split_adds(clauses)
    if split is not None:
        return _with_days(clauses, split, user_timezone)
    single = parse_spoken_add(user_text)
    return [] if single is None else [_with_day(single, user_text, user_timezone)]


async def pending_add(
    session: AsyncSession, chat_id: UUID, current: str, *, dated: bool = True
) -> SpokenAdd | None:
    """The add they just described, when this message is only the missing clock.

    In "call mom at 5pm and pay rent on friday", that is the rent. ``dated``: only an add
    that named its day; any add without a clock otherwise.
    """
    from app.modules.chat import history as chat_history

    rows = await chat_history.recent_messages(session, chat_id, limit=8)
    skipped_current = False
    for message in reversed(rows):
        if getattr(message, "role", None) != "user":
            continue
        body = (getattr(message, "content", None) or "").strip()
        if not skipped_current and body == current.strip():
            skipped_current = True
            continue
        if parse_clock_only(body) is not None:
            continue
        single = parse_spoken_add(body)
        adds = _split_adds(reminder_clauses(body)) or ([single] if single else [])
        return next((add for add in adds if add.hour is None and (add.day or not dated)), None)
    return None


# The server's own question for a reminder with no time (``reply_check.NEED_A_TIME``, and
# "When should I remind you to call mom?").
_ASKED_WHEN_RE = re.compile(r"(?:^|\n)\s*When should I remind you\b[^\n]*\?\s*$")


async def answered_when(
    session: AsyncSession,
    chat_id: UUID,
    current: str,
    prior_assistant: str | None,
    *,
    user_timezone: str | None = None,
) -> SpokenAdd | None:
    """The add this message finishes by giving its time, or None.

    A bare clock ("7pm") finishes the add that named its day. After the server asked
    "When should I remind you?", any when does: live (2026-10-25), "can you remind me
    about the python practice again?" was asked when, and "7pm tomorrow" saved nothing.
    The answer is read onto the add's own words ("remind me to <task> 7pm tomorrow"); one
    that says more than when ("tomorrow, and buy milk") is its own message.
    """
    clock = parse_clock_only(current)
    if clock is not None:
        dated = await pending_add(session, chat_id, current)
        if dated is not None:
            return replace(dated, hour=clock[0], minute=clock[1])
    if not prior_assistant or not _ASKED_WHEN_RE.search(prior_assistant):
        return None
    pending = await pending_add(session, chat_id, current, dated=False)
    if pending is None:
        return None
    request = f"{_REQUEST}{pending.title} {current}"
    answered = parse_spoken_add(request)
    if answered is None or answered.title.casefold() != pending.title.casefold():
        return None
    if answered.hour is None and answered.after_minutes is None:
        return None
    if answered.day is None and pending.day is not None:
        return replace(answered, day=pending.day)
    return _with_day(answered, request, user_timezone)


def _split_adds(clauses: list[str]) -> list[SpokenAdd] | None:
    """One add per clause, or None when the message is one reminder."""
    if len(clauses) < 2:
        return None
    adds = [parse_spoken_add(clause) for clause in clauses]
    if any(add is None or (add.day is None and add.hour is None) for add in adds):
        return None
    return [add for add in adds if add is not None]


def _with_days(
    clauses: list[str], adds: list[SpokenAdd], user_timezone: str | None
) -> list[SpokenAdd]:
    resolved: list[SpokenAdd] = []
    # Only a day the user said carries over; "at 5pm" read as today does not.
    said: str | None = None
    for clause, add in zip(clauses, adds, strict=True):
        own = add.day
        if own is None and add.repeat is None and add.hour is not None and said:
            add = replace(add, day=said)
        resolved.append(_with_day(add, clause, user_timezone))
        said = own or said
    return resolved


def _with_day(add: SpokenAdd, request: str | None, user_timezone: str | None) -> SpokenAdd:
    """ "At 9pm every night" starts tonight; "at 7pm" alone is the next 7pm."""
    if add.day is None and add.repeat and add.hour is not None:
        return replace(add, day="today")
    return day_for_a_bare_clock(add, request, user_timezone=user_timezone)
