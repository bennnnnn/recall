"""Calendar write and conflict detection tests."""

from datetime import UTC, datetime, timedelta

import pytest

from app.gateways.google_calendar_gateway import CalendarEvent
from app.services.calendar import find_conflicting_events, has_write_scope


def test_has_write_scope():
    assert has_write_scope("https://www.googleapis.com/auth/calendar.events")
    assert not has_write_scope("https://www.googleapis.com/auth/calendar.readonly")


def test_find_conflicting_events():
    due = datetime(2026, 6, 30, 14, 0, tzinfo=UTC)
    events = [
        CalendarEvent(
            id="1",
            title="Lunch",
            start=datetime(2026, 6, 30, 13, 30, tzinfo=UTC),
            end=datetime(2026, 6, 30, 14, 30, tzinfo=UTC),
        ),
        CalendarEvent(
            id="2",
            title="Later",
            start=datetime(2026, 6, 30, 18, 0, tzinfo=UTC),
            end=datetime(2026, 6, 30, 19, 0, tzinfo=UTC),
        ),
    ]
    conflicts = find_conflicting_events(events, due)
    assert len(conflicts) == 1
    assert conflicts[0].title == "Lunch"


@pytest.mark.asyncio
async def test_materialize_calendar_proposals_injects_id(fake_redis):
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    from app.core.config import Settings
    from app.services import calendar as calendar_service

    user = MagicMock()
    user.id = uuid4()
    session = AsyncMock()
    settings = Settings()

    connection = MagicMock()
    connection.scopes = "https://www.googleapis.com/auth/calendar.events"

    text = (
        "Here is your event:\n```calendar_proposal\n"
        '{"title":"Team sync","start_at":"2026-06-28T15:00:00-07:00",'
        '"end_at":"2026-06-28T16:00:00-07:00","location":"Zoom"}\n```'
    )

    with (
        patch(
            "app.services.calendar.google_calendar_gateway.is_configured",
            return_value=True,
        ),
        patch(
            "app.services.calendar.calendar_repo.get_for_user",
            AsyncMock(return_value=connection),
        ),
    ):
        updated = await calendar_service.materialize_calendar_proposals(
            session, fake_redis, user, settings, text
        )

    assert "proposal_id" in updated
    assert "Team sync" in updated
    assert "Zoom" in updated
