import pytest

from app.services.mcp.calendar_adapter import CalendarAdapter


@pytest.mark.asyncio
async def test_conflicts_rejects_malformed_due_at_instead_of_raising():
    """BUG FIX: due_at is model-supplied and only Pydantic-constrained to a
    1-64 char string, not ISO format. A plausible-but-malformed value used to
    raise straight out of the adapter with nothing upstream catching it,
    taking down the whole chat turn instead of returning a tool error the
    model can recover from."""
    adapter = CalendarAdapter()

    result = await adapter.invoke({"action": "conflicts", "due_at": "tomorrow afternoon"})

    assert "Invalid due_at" in result.content


@pytest.mark.asyncio
async def test_conflicts_reports_no_conflicts_for_valid_due_at_and_no_events():
    adapter = CalendarAdapter()

    result = await adapter.invoke(
        {"action": "conflicts", "due_at": "2026-08-01T15:00:00Z", "events": []}
    )

    assert result.content == "No conflicts."


@pytest.mark.asyncio
async def test_conflicts_missing_due_at_does_not_reach_datetime_parsing():
    adapter = CalendarAdapter()

    result = await adapter.invoke({"action": "conflicts", "events": []})

    assert result.content == "Missing due_at."


@pytest.mark.asyncio
async def test_conflicts_uses_google_events_not_only_caller_supplied():
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    from app.core.config import Settings
    from app.gateways.google_calendar_gateway import CalendarEvent
    from app.services.mcp.calendar_adapter import CalendarAdapter, bind_calendar_context

    google_event = CalendarEvent(
        id="g1",
        title="Standup",
        start=datetime(2026, 8, 1, 15, 0, tzinfo=UTC),
        end=datetime(2026, 8, 1, 15, 30, tzinfo=UTC),
    )
    user = MagicMock()
    user.id = uuid4()

    class _FakeSession:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *_args: object) -> None:
            return None

    with (
        bind_calendar_context(user=user, redis=MagicMock(), settings=Settings()),
        patch(
            "app.services.mcp.calendar_adapter.calendar_service.fetch_upcoming_events",
            AsyncMock(return_value=[google_event]),
        ),
        patch(
            "app.services.mcp.calendar_adapter.SessionLocal",
            MagicMock(return_value=_FakeSession()),
        ),
    ):
        adapter = CalendarAdapter()
        result = await adapter.invoke(
            {"action": "conflicts", "due_at": "2026-08-01T15:00:00Z", "events": []}
        )

    assert "Standup" in result.content
