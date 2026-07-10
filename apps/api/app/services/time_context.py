"""User-local time context for LLM prompts (foundation for due dates & reminders)."""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "UTC"

_TIME_QUESTION = re.compile(
    r"^\s*(?:"
    r"what(?:'s| is) the time(?:\s+now)?"
    r"|what time is it(?:\s+now)?"
    r"|what time(?:\s+now)?"
    r"|tell me the (?:current )?time"
    r"|current time\??"
    r"|do you know the time\??"
    r"|time(?:\s+please)?\??"
    r")\s*[.!?]*\s*$",
    re.IGNORECASE,
)

# "What time is it in Tokyo / DC / …" — not the user's local clock.
_REMOTE_TIME_QUESTION = re.compile(
    r"^\s*(?:"
    r"what(?:'s| is) the time(?:\s+now)?\s+in\b.+"
    r"|what time is it(?:\s+now)?\s+in\b.+"
    r"|what time(?:\s+now)?\s+in\b.+"
    r"|current time\s+in\b.+"
    r"|time(?:\s+please)?\s+in\b.+"
    r")\s*[.!?]*\s*$",
    re.IGNORECASE | re.DOTALL,
)

_SCHEDULED_EVENT = re.compile(
    r"\b(meeting|appointment|flight|event|class|call|interview|game|train|bus)\b",
    re.IGNORECASE,
)


_LOCATION_QUESTION = re.compile(
    r"^\s*(?:"
    r"where am i\??"
    r"|what(?:'s| is) my location\??"
    r"|where(?:'s| is) my location\??"
    r"|where(?:'re| are) we\??"
    r"|my location\??"
    r"|location\??"
    r")\s*[.!?]*\s*$",
    re.IGNORECASE,
)


def resolve_timezone(tz: str | None) -> ZoneInfo:
    try:
        return ZoneInfo((tz or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def effective_timezone(profile_tz: str | None, client_tz: str | None = None) -> str:
    """Prefer device timezone from the client; fall back to stored profile."""
    if client_tz and client_tz.strip():
        try:
            ZoneInfo(client_tz.strip())
            return client_tz.strip()
        except ZoneInfoNotFoundError:
            pass
    cleaned = (profile_tz or DEFAULT_TIMEZONE).strip()
    return cleaned or DEFAULT_TIMEZONE


def prefers_12h_clock(locale: str | None) -> bool:
    code = (locale or "en").split("-")[0].lower()
    return code == "en"


def format_digital_clock(when: datetime, locale: str | None = None) -> str:
    if prefers_12h_clock(locale):
        return when.strftime("%I:%M:%S %p")
    return when.strftime("%H:%M:%S")


def is_remote_time_question(text: str) -> bool:
    """True when the user asks for the time in another place (not local)."""
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_REMOTE_TIME_QUESTION.match(cleaned))


def is_time_question(text: str) -> bool:
    """True for the user's *local* current-time question only."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if is_remote_time_question(cleaned):
        return False
    if _TIME_QUESTION.match(cleaned):
        return _SCHEDULED_EVENT.search(cleaned) is None
    if re.match(
        r"^\s*(?:again|one more time|tell me again|refresh|update(?:\s+it)?)\s*[.!?]*\s*$",
        cleaned,
        re.IGNORECASE,
    ):
        return True
    return False


def is_location_question(text: str) -> bool:
    return bool(_LOCATION_QUESTION.match(text.strip()))


def format_location_answer(location: str | None, timezone: str | None) -> str:
    tz = resolve_timezone(timezone)
    now = datetime.now(tz)
    time_str = now.strftime("%A, %B %d, %Y at %I:%M %p %Z")
    if location:
        return f"You're in **{location}**. Local time: {time_str}."
    return (
        "I don't have your location yet. Enable location access for Recall in your "
        "device Settings, then reopen the app — I'll pick up your city automatically."
    )


def format_time_answer(timezone: str | None, locale: str | None = None) -> str:
    del locale  # live widget reads timezone from the user profile on device
    return "```clock\n```"


def format_time_context(
    timezone: str | None,
    locale: str | None = None,
    location: str | None = None,
) -> str:
    tz = resolve_timezone(timezone)
    now = datetime.now(tz)
    digital = format_digital_clock(now, locale)
    parts = [
        f"User local date & time ({now.tzname()}): "
        f"{now.strftime('%A, %B %d, %Y %H:%M %Z')}. "
        f"Digital clock now: {digital}.",
    ]
    if location:
        parts.append(f"User approximate location (from device GPS): {location}.")
    else:
        parts.append("User location is not synced yet.")
    parts.append(
        "When the user asks what time it is *here* (no other city/place), reply with "
        "only an empty ```clock``` fence. The app renders a live circular analog clock "
        "for their local timezone — never paste timezone names, HH:MM text, or any "
        "other content inside that empty fence. "
        "When they ask the time in another city or place, do NOT use an empty clock "
        "fence (that would show the user's local time). Put the place's IANA timezone "
        "alone inside the fence, e.g. ```clock\\nAmerica/New_York\\n``` for Washington "
        "DC / US Eastern, or answer in short prose with the local time there. "
        "When they ask where they are, use the location above if set. "
        "Use this when answering questions about today, deadlines, overdue tasks, "
        "or how long until something is due."
    )
    return " ".join(parts)


def normalize_due_at(due_at: datetime | None, user_timezone: str | None) -> datetime | None:
    if due_at is None:
        return None
    tz = resolve_timezone(user_timezone)
    if due_at.tzinfo is None:
        localized = due_at.replace(tzinfo=tz)
    else:
        localized = due_at.astimezone(tz)
    return localized.astimezone(UTC)


def describe_due_at(
    due_at: datetime | None,
    user_timezone: str | None,
    *,
    checked: bool = False,
) -> str:
    if due_at is None or checked:
        return ""
    tz = resolve_timezone(user_timezone)
    now = datetime.now(tz)
    if due_at.tzinfo:
        due_local = due_at.astimezone(tz)
    else:
        due_local = due_at.replace(tzinfo=UTC).astimezone(tz)
    delta = due_local - now
    if delta.total_seconds() < 0:
        if due_local.date() == now.date():
            return "overdue today"
        days = max(1, abs(delta.days))
        return f"overdue by {days} day{'s' if days != 1 else ''}"
    if due_local.date() == now.date():
        return f"due today {due_local.strftime('%H:%M')}"
    days = delta.days
    if days == 0:
        hours = max(1, int(delta.total_seconds() // 3600))
        return f"due in {hours} hour{'s' if hours != 1 else ''}"
    if days <= 7:
        return f"due in {days} day{'s' if days != 1 else ''} ({due_local.strftime('%a %b %d')})"
    return f"due {due_local.strftime('%a %b %d, %Y')}"
