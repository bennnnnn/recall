import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.gateways.google_calendar_gateway import CalendarEvent
from app.services.calendar import (
    format_calendar_block,
    format_not_connected_answer,
    is_external_calendar_question,
    should_inject_calendar_block,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("check my calendar", True),
        ("what's on my calendar tomorrow", True),
        ("any meetings today", True),
        ("what am I doing today", True),
        ("Ethiopias game score", False),
        ("what's due today", False),
    ],
)
def test_is_external_calendar_question(text, expected):
    assert is_external_calendar_question(text) is expected


def test_format_not_connected_mentions_settings():
    answer = format_not_connected_answer()
    assert "Google Calendar" in answer
    assert "Settings" in answer


@pytest.mark.parametrize(
    "text,expected",
    [
        ("check my calendar", True),
        ("schedule a meeting tomorrow", True),
        ("am I free at 3pm", True),
        (
            "How's my day looking so far — anything you think I should prioritize?",
            True,
        ),
        ("Help me plan my day based on what you know about me.", True),
        ("solve for the hypotenuse", False),
        ("best restaurants near me", False),
        ("what is photosynthesis", False),
    ],
)
def test_should_inject_calendar_block(text, expected):
    assert should_inject_calendar_block(text) is expected


def test_format_calendar_block_lists_events():
    start = datetime.now(UTC) + timedelta(days=1)
    block = format_calendar_block(
        [
            CalendarEvent(
                id="evt-1",
                title="Team sync",
                start=start,
                end=start + timedelta(hours=1),
                location="Zoom",
            )
        ],
        "UTC",
    )
    assert "Team sync" in block
    assert "Zoom" in block


def test_format_calendar_block_skips_past_events():
    from app.services.calendar import _events_within_days

    past_start = datetime.now(UTC) - timedelta(days=2)
    past = CalendarEvent(
        id="past",
        title="Yesterday",
        start=past_start,
        end=past_start + timedelta(hours=1),
        location=None,
    )
    future_start = datetime.now(UTC) + timedelta(days=1)
    future = CalendarEvent(
        id="future",
        title="Tomorrow",
        start=future_start,
        end=future_start + timedelta(hours=1),
        location=None,
    )
    assert [e.id for e in _events_within_days([past, future], 14)] == ["future"]


def test_format_calendar_block_uses_custom_window():
    block = format_calendar_block([], "UTC", days=14)
    assert "next 14 days" in block


def test_format_not_connected_mentions_create():
    answer = format_not_connected_answer()
    assert "Google Calendar" in answer
    assert "Settings" in answer
    # Updated copy: no longer says "won't create"; now mentions it can create events.
    assert "won't create" not in answer
    assert "create" in answer.lower()


@pytest.mark.parametrize(
    "text,expected",
    [
        ("schedule a meeting tomorrow", True),
        ("book time on my calendar", True),
        ("what is photosynthesis", False),
        ("", False),
    ],
)
def test_is_calendar_create_request(text, expected):
    from app.services.calendar import is_calendar_create_request

    assert is_calendar_create_request(text) is expected


def test_datetime_from_iso_parses_z_suffix():
    from app.services.calendar import datetime_from_iso

    dt = datetime_from_iso("2026-06-30T14:00:00Z")
    assert dt.year == 2026
    assert dt.hour == 14


@pytest.mark.asyncio
async def test_is_connected():
    from unittest.mock import AsyncMock, patch

    from app.services.calendar import is_connected

    session = AsyncMock()
    with patch(
        "app.services.calendar.calendar_repo.get_for_user",
        AsyncMock(return_value=object()),
    ):
        assert await is_connected(session, uuid4()) is True


@pytest.mark.asyncio
async def test_has_write_access():
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.calendar import has_write_access

    session = AsyncMock()
    conn = MagicMock()
    conn.scopes = "https://www.googleapis.com/auth/calendar.events"
    with patch(
        "app.services.calendar.calendar_repo.get_for_user",
        AsyncMock(return_value=conn),
    ):
        assert await has_write_access(session, uuid4()) is True


@pytest.mark.asyncio
async def test_list_events_for_api_reports_fetch_failure():
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    from app.core.config import Settings
    from app.gateways.google_calendar_gateway import GoogleCalendarError
    from app.services.calendar import list_events_for_api

    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    session = AsyncMock()
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    settings = Settings()

    with (
        patch(
            "app.services.calendar.is_connected",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.calendar.calendar_repo.get_for_user",
            AsyncMock(return_value=MagicMock(refresh_token="rt", calendar_id="primary")),
        ),
        patch(
            "app.services.calendar.google_calendar_gateway.list_upcoming_events",
            AsyncMock(side_effect=GoogleCalendarError("token expired")),
        ),
    ):
        result = await list_events_for_api(session, redis, user, settings)

    assert result.events == []
    assert result.load_error == "fetch_failed"


@pytest.mark.asyncio
async def test_fetch_upcoming_events_uses_redis_cache():
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    from app.core.config import Settings
    from app.services.calendar import fetch_upcoming_events

    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings()

    redis = AsyncMock()
    redis.get = AsyncMock(
        return_value=json.dumps(
            [
                {
                    "id": "evt-1",
                    "title": "Standup",
                    "start": "2026-06-30T09:00:00+00:00",
                    "end": "2026-06-30T09:30:00+00:00",
                }
            ]
        )
    )

    with (
        patch(
            "app.services.calendar.calendar_repo.get_for_user",
            AsyncMock(return_value=MagicMock(refresh_token="rt", calendar_id="primary")),
        ),
    ):
        events = await fetch_upcoming_events(session, redis, user, settings)

    assert len(events) == 1
    assert events[0].title == "Standup"


@pytest.mark.asyncio
async def test_load_calendar_for_prompt_not_configured():
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    from app.core.config import Settings
    from app.services.calendar import load_calendar_for_prompt

    with patch(
        "app.services.calendar.google_calendar_gateway.is_configured",
        return_value=False,
    ):
        block = await load_calendar_for_prompt(
            AsyncMock(), AsyncMock(), MagicMock(id=uuid4()), Settings()
        )
    assert block is None


@pytest.mark.asyncio
async def test_load_calendar_for_prompt_not_connected_is_explicit():
    """Disconnected calendar must not look like an empty schedule."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    from app.core.config import Settings
    from app.services.calendar import load_calendar_for_prompt

    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"

    with (
        patch(
            "app.services.calendar.google_calendar_gateway.is_configured",
            return_value=True,
        ),
        patch(
            "app.services.calendar.is_connected",
            AsyncMock(return_value=False),
        ),
    ):
        block = await load_calendar_for_prompt(AsyncMock(), AsyncMock(), user, Settings())

    assert block is not None
    assert "not connected" in block.lower()
    assert "do not say the calendar is empty" in block.lower()
    assert "No upcoming events" not in block


@pytest.mark.asyncio
async def test_load_calendar_for_prompt_notes_partial_failure():
    """A user shouldn't be told "nothing else scheduled" when some of their
    calendars actually failed to load — the prompt block must say so."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.core.config import Settings
    from app.gateways.google_calendar_gateway import CalendarFetchResult
    from app.services.calendar import load_calendar_for_prompt

    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(google_client_id="x", google_client_secret="y")

    with (
        patch(
            "app.services.calendar.is_connected",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.calendar._load_cached_events",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.calendar.calendar_repo.get_for_user",
            AsyncMock(return_value=MagicMock(refresh_token="rt", calendar_id="primary")),
        ),
        patch(
            "app.services.calendar.google_calendar_gateway.list_upcoming_events",
            AsyncMock(return_value=CalendarFetchResult(events=[], failed_calendars=2)),
        ),
        patch(
            "app.services.calendar._store_cached_events",
            AsyncMock(),
        ),
    ):
        block = await load_calendar_for_prompt(session, redis, user, settings)

    assert block is not None
    assert "2 of the user's calendars couldn't be loaded" in block


@pytest.mark.asyncio
async def test_store_and_load_event_proposal(fake_redis):
    from uuid import uuid4

    from app.services.calendar import load_event_proposal, store_event_proposal

    user_id = uuid4()
    proposal_id = "prop-1"
    payload = {
        "title": "Sync",
        "start": "2026-06-30T09:00:00+00:00",
        "end": "2026-06-30T10:00:00+00:00",
    }

    await store_event_proposal(fake_redis, user_id, proposal_id, payload)
    loaded = await load_event_proposal(fake_redis, user_id, proposal_id)

    assert loaded == payload
