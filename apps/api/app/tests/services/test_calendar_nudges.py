from datetime import UTC, datetime, timedelta

from app.gateways.google_calendar_gateway import CalendarEvent
from app.services.calendar_nudges import (
    events_needing_nudge,
    format_calendar_nudge,
    minutes_until_event_start,
    should_nudge_calendar_event,
)


def _event(minutes_ahead: int, *, all_day: bool = False) -> CalendarEvent:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    return CalendarEvent(
        id="evt-1",
        title="Team sync",
        start=now + timedelta(minutes=minutes_ahead),
        end=now + timedelta(minutes=minutes_ahead + 30),
        all_day=all_day,
    )


def test_should_nudge_within_lead_window():
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    assert should_nudge_calendar_event(_event(10), now=now, lead_minutes=15) is True
    assert should_nudge_calendar_event(_event(20), now=now, lead_minutes=15) is False
    assert should_nudge_calendar_event(_event(-5), now=now, lead_minutes=15) is False
    assert should_nudge_calendar_event(_event(10, all_day=True), now=now, lead_minutes=15) is False


def test_events_needing_nudge_filters_list():
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    events = [_event(8), _event(30), _event(12)]
    nudged = events_needing_nudge(events, now=now, lead_minutes=15)
    assert [e.title for e in nudged] == ["Team sync", "Team sync"]


def test_minutes_until_event_start():
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    assert minutes_until_event_start(_event(14), now=now) == 14


def test_format_calendar_nudge_uses_locale_template():
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    title, body = format_calendar_nudge(_event(14), now=now, locale="en")
    assert title == "Upcoming meeting"
    assert body == "Team sync starts in 14 min"

    soon_title, soon_body = format_calendar_nudge(_event(1), now=now, locale="en")
    assert soon_title == "Upcoming meeting"
    assert soon_body == "Team sync starts soon"
