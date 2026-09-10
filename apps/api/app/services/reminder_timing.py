"""Shared reminder lead-time rules for push and prompt logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.orm import User
from app.services import time_context as time_context_service
from app.services.locale import normalize_locale_code

DEFAULT_REMINDER_LEAD_MINUTES = 10
MAX_REMINDER_LEAD_MINUTES = 60
VALID_REMINDER_LEAD_MINUTES = frozenset({5, 10, 15, 30, 60})
OVERDUE_MAX_HOURS = 48


def resolve_reminder_lead_minutes(raw: int | None) -> int:
    if raw in VALID_REMINDER_LEAD_MINUTES:
        return raw
    return DEFAULT_REMINDER_LEAD_MINUTES


def should_notify_todo(
    due_at: datetime,
    *,
    now: datetime,
    lead_minutes: int,
) -> bool:
    """True when a reminder push/local alert should fire."""
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    if due_at < now:
        overdue_cutoff = now - timedelta(hours=OVERDUE_MAX_HOURS)
        return due_at >= overdue_cutoff

    lead = resolve_reminder_lead_minutes(lead_minutes)
    return due_at <= now + timedelta(minutes=lead)


# BUG FIX (nit): user_local_hour/user_day_key/learning_dedupe_key were
# copy-pasted between push_notifications.py and reminder_emails.py with only
# the Redis key prefix differing. Shared here so the two can't drift apart.
def in_quiet_hours(user: User, now: datetime | None = None) -> bool:
    """True when the user has quiet hours on and ``now`` is inside the window.

    ``quiet_hours_enabled is not True`` so MagicMocks in tests are not treated as
    opted-in. A zero-length window (start == end) is never quiet. Ranges that
    wrap midnight (e.g. 22:00–07:00) use the user's timezone.
    """
    if getattr(user, "quiet_hours_enabled", False) is not True:
        return False
    start = getattr(user, "quiet_hours_start_minute", None)
    end = getattr(user, "quiet_hours_end_minute", None)
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    if start == end or not (0 <= start <= 1439 and 0 <= end <= 1439):
        return False
    tz = time_context_service.resolve_timezone(getattr(user, "timezone", None))
    instant = now.astimezone(tz) if now is not None else datetime.now(tz)
    minute = instant.hour * 60 + instant.minute
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


def user_local_hour(user: User, *, now: datetime | None = None) -> int:
    tz = time_context_service.resolve_timezone(user.timezone)
    instant = now.astimezone(tz) if now is not None else datetime.now(tz)
    return instant.hour


def user_day_key(user: User, *, now: datetime | None = None) -> str:
    tz = time_context_service.resolve_timezone(user.timezone)
    instant = now.astimezone(tz) if now is not None else datetime.now(tz)
    return instant.strftime("%Y-%m-%d")


def learning_dedupe_key(prefix: str, user_id: UUID, day_key: str) -> str:
    return f"{prefix}:{user_id}:{day_key}"


# BUG FIX: reminder_emails.py used to hardcode "Reminder"/"Overdue reminder" in
# English directly, never localizing it, even though push_notifications.py's
# equivalent (title) was already locale-aware. Shared here — same reasoning as
# the helpers above — so push and email can't drift on this either.
_REMINDER_TITLES: dict[str, dict[str, str]] = {
    "en": {"reminder": "Reminder", "overdue": "Overdue reminder"},
    "es": {"reminder": "Recordatorio", "overdue": "Recordatorio atrasado"},
    "fr": {"reminder": "Rappel", "overdue": "Rappel en retard"},
    "de": {"reminder": "Erinnerung", "overdue": "Überfällige Erinnerung"},
    "it": {"reminder": "Promemoria", "overdue": "Promemoria in ritardo"},
    "pt": {"reminder": "Lembrete", "overdue": "Lembrete atrasado"},
    "ru": {"reminder": "Напоминание", "overdue": "Просроченное напоминание"},
    "tr": {"reminder": "Hatırlatma", "overdue": "Gecikmiş hatırlatma"},
}


def reminder_title(*, is_overdue: bool, locale: str | None) -> str:
    code = normalize_locale_code(locale)
    bundle = _REMINDER_TITLES.get(code, _REMINDER_TITLES["en"])
    return bundle["overdue"] if is_overdue else bundle["reminder"]
