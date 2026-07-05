"""Tests for the Google Calendar fetch fan-out (cap + concurrency + partial failure)."""

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways import google_calendar_gateway as gw
from app.gateways.google_calendar_gateway import CalendarEvent


def _event(cal_name: str) -> CalendarEvent:
    from datetime import UTC, datetime

    return CalendarEvent(
        id=str(uuid4()),
        title=f"Event in {cal_name}",
        start=datetime.now(UTC),
        end=None,
        calendar_name=cal_name,
    )


@pytest.mark.asyncio
async def test_list_upcoming_events_caps_calendar_fanout(monkeypatch):
    settings = Settings(
        google_client_id="x",
        google_client_secret="y",
        calendar_max_calendars=2,
        calendar_fetch_concurrency=5,
    )
    calendars = [(f"cal-{i}", f"Calendar {i}") for i in range(10)]

    fetched_calendar_ids: list[str] = []

    async def fake_fetch(client, headers, *, calendar_id, calendar_name, **_kwargs):
        fetched_calendar_ids.append(calendar_id)
        return [_event(calendar_name)]

    with (
        patch.object(gw, "_access_token", AsyncMock(return_value="token")),
        patch.object(gw, "_list_selected_calendars", AsyncMock(return_value=calendars)),
        patch.object(gw, "_fetch_events_for_calendar", fake_fetch),
        patch.object(gw.httpx, "AsyncClient") as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        await gw.list_upcoming_events(settings, refresh_token="rt")

    assert len(fetched_calendar_ids) == 2


@pytest.mark.asyncio
async def test_list_upcoming_events_bounds_concurrency(monkeypatch):
    settings = Settings(
        google_client_id="x",
        google_client_secret="y",
        calendar_max_calendars=20,
        calendar_fetch_concurrency=2,
    )
    calendars = [(f"cal-{i}", f"Calendar {i}") for i in range(6)]

    in_flight = 0
    max_in_flight = 0

    async def fake_fetch(client, headers, *, calendar_id, calendar_name, **_kwargs):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return [_event(calendar_name)]

    with (
        patch.object(gw, "_access_token", AsyncMock(return_value="token")),
        patch.object(gw, "_list_selected_calendars", AsyncMock(return_value=calendars)),
        patch.object(gw, "_fetch_events_for_calendar", fake_fetch),
        patch.object(gw.httpx, "AsyncClient") as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        await gw.list_upcoming_events(settings, refresh_token="rt")

    assert max_in_flight <= 2


@pytest.mark.asyncio
async def test_list_upcoming_events_reports_partial_failures(monkeypatch):
    settings = Settings(
        google_client_id="x",
        google_client_secret="y",
        calendar_max_calendars=10,
        calendar_fetch_concurrency=5,
    )
    calendars = [("cal-ok", "Ok"), ("cal-fail", "Fails"), ("cal-ok-2", "Ok 2")]

    async def fake_fetch(client, headers, *, calendar_id, calendar_name, **_kwargs):
        if calendar_id == "cal-fail":
            raise RuntimeError("boom")
        return [_event(calendar_name)]

    with (
        patch.object(gw, "_access_token", AsyncMock(return_value="token")),
        patch.object(gw, "_list_selected_calendars", AsyncMock(return_value=calendars)),
        patch.object(gw, "_fetch_events_for_calendar", fake_fetch),
        patch.object(gw.httpx, "AsyncClient") as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await gw.list_upcoming_events(settings, refresh_token="rt")

    assert result.failed_calendars == 1
    assert len(result.events) == 2
