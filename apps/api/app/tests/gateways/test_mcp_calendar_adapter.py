import pytest

from app.gateways.mcp.calendar_adapter import CalendarAdapter


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
