from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.services.ics_parser import parse_ics_event, parse_ics_invite


def test_parse_ics_event_extracts_utc_datetime():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Interview with Acme
DTSTART:20260630T140000Z
END:VEVENT
END:VCALENDAR"""
    title, due_at = parse_ics_event(ics)
    assert title == "Interview with Acme"
    assert due_at == datetime(2026, 6, 30, 14, 0, tzinfo=UTC)


def test_parse_ics_invite_unfolds_summary_and_parses_tzid():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Flight to NYC\\, terminal B
DTSTART;TZID=America/Los_Angeles:20260708T153000
LOCATION:SFO Terminal 2
END:VEVENT
END:VCALENDAR"""
    invite = parse_ics_invite(ics)
    assert invite is not None
    assert invite.title == "Flight to NYC, terminal B"
    assert invite.location == "SFO Terminal 2"
    assert invite.due_at is not None
    assert invite.due_at.tzinfo == ZoneInfo("America/Los_Angeles")


def test_parse_ics_invite_supports_all_day_date():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Conference day
DTSTART;VALUE=DATE:20260715
END:VEVENT
END:VCALENDAR"""
    invite = parse_ics_invite(ics, default_tz="America/Los_Angeles")
    assert invite is not None
    assert invite.title == "Conference day"
    assert invite.due_at == datetime(2026, 7, 15, tzinfo=ZoneInfo("America/Los_Angeles"))


def test_parse_ics_invite_floating_datetime_uses_default_tz():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Local standup
DTSTART:20260715T090000
END:VEVENT
END:VCALENDAR"""
    invite = parse_ics_invite(ics, default_tz="America/New_York")
    assert invite is not None
    assert invite.due_at == datetime(2026, 7, 15, 9, 0, tzinfo=ZoneInfo("America/New_York"))


def test_parse_ics_invite_skips_cancelled_event():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
STATUS:CANCELLED
SUMMARY:Old meeting
DTSTART:20260701T080000Z
END:VEVENT
END:VCALENDAR"""
    assert parse_ics_invite(ics) is None


def test_parse_ics_invite_parses_loose_properties_without_vevent():
    ics = "SUMMARY:Flight AA123\nDTSTART:20260701T080000Z"
    invite = parse_ics_invite(ics)
    assert invite is not None
    assert invite.title == "Flight AA123"
    assert invite.due_at == datetime(2026, 7, 1, 8, 0, tzinfo=UTC)


def test_parse_ics_invite_unfolds_wrapped_lines():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Quarterly business review with 
 leadership team
DTSTART:20260702T170000Z
END:VEVENT
END:VCALENDAR"""
    invite = parse_ics_invite(ics)
    assert invite is not None
    assert invite.title == "Quarterly business review with leadership team"
