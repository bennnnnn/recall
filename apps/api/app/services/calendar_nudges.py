"""Proactive calendar push nudges — notify before upcoming meetings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.gateways.google_calendar_gateway import CalendarEvent

CALENDAR_NUDGE_REDIS_PREFIX = "recall:push:calendar"


def calendar_nudge_redis_key(user_id: UUID, event_id: str) -> str:
    return f"{CALENDAR_NUDGE_REDIS_PREFIX}:{user_id}:{event_id}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def minutes_until_event_start(event: CalendarEvent, *, now: datetime) -> int | None:
    if event.all_day:
        return None
    start = _as_utc(event.start)
    current = _as_utc(now)
    if start <= current:
        return None
    return max(1, int((start - current).total_seconds() // 60))


def should_nudge_calendar_event(
    event: CalendarEvent,
    *,
    now: datetime,
    lead_minutes: int,
) -> bool:
    """True when the event starts within the lead window (not yet started)."""
    if event.all_day:
        return False
    start = _as_utc(event.start)
    current = _as_utc(now)
    if start <= current:
        return False
    return start - current <= timedelta(minutes=max(1, lead_minutes))


def events_needing_nudge(
    events: list[CalendarEvent],
    *,
    now: datetime,
    lead_minutes: int,
) -> list[CalendarEvent]:
    return [
        event
        for event in events
        if should_nudge_calendar_event(event, now=now, lead_minutes=lead_minutes)
    ]


def nudge_ttl_seconds(event: CalendarEvent, *, now: datetime) -> int:
    start = _as_utc(event.start)
    current = _as_utc(now)
    remaining = int((start - current).total_seconds())
    return max(300, remaining + 3600)


_NUDGE_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Upcoming meeting",
        "body": "{title} starts in {minutes} min",
        "body_soon": "{title} starts soon",
    },
    "es": {
        "title": "Próxima reunión",
        "body": "{title} empieza en {minutes} min",
        "body_soon": "{title} empieza pronto",
    },
    "fr": {
        "title": "Réunion à venir",
        "body": "{title} commence dans {minutes} min",
        "body_soon": "{title} commence bientôt",
    },
    "de": {
        "title": "Bevorstehendes Meeting",
        "body": "{title} beginnt in {minutes} Min.",
        "body_soon": "{title} beginnt gleich",
    },
    "it": {
        "title": "Prossimo appuntamento",
        "body": "{title} inizia tra {minutes} min",
        "body_soon": "{title} inizia a breve",
    },
    "pt": {
        "title": "Próxima reunião",
        "body": "{title} começa em {minutes} min",
        "body_soon": "{title} começa em breve",
    },
    "ru": {
        "title": "Предстоящая встреча",
        "body": "{title} через {minutes} мин",
        "body_soon": "{title} скоро начнётся",
    },
    "tr": {
        "title": "Yaklaşan toplantı",
        "body": "{title} {minutes} dk içinde başlıyor",
        "body_soon": "{title} yakında başlıyor",
    },
}


def format_calendar_nudge(
    event: CalendarEvent,
    *,
    now: datetime,
    locale: str | None,
) -> tuple[str, str]:
    from app.services.locale import normalize_locale_code

    code = normalize_locale_code(locale)
    strings = _NUDGE_STRINGS.get(code, _NUDGE_STRINGS["en"])
    minutes = minutes_until_event_start(event, now=now) or 1
    title = strings["title"]
    if minutes <= 2:
        body = strings["body_soon"].format(title=event.title)
    else:
        body = strings["body"].format(title=event.title, minutes=minutes)
    return title, body
