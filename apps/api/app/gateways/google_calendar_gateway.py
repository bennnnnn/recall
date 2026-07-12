"""Google Calendar OAuth + event fetch (server-side only)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from app.core.config import Settings
from app.gateways import google_oauth
from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
DEFAULT_TIMEOUT = 15.0


class GoogleCalendarError(Exception):
    pass


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    title: str
    start: datetime
    end: datetime | None
    location: str | None = None
    all_day: bool = False
    calendar_name: str | None = None


@dataclass(frozen=True)
class CalendarFetchResult:
    events: list[CalendarEvent]
    # How many of the user's calendars failed to fetch this round — merged
    # events are still returned (best-effort), but a caller presenting this
    # as "your schedule" should know it may be incomplete.
    failed_calendars: int = 0


def is_configured(settings: Settings) -> bool:
    return bool(
        settings.google_calendar_enabled
        and settings.google_client_id.strip()
        and settings.google_client_secret.strip()
    )


async def exchange_server_auth_code(settings: Settings, code: str) -> dict[str, Any]:
    try:
        return await google_oauth.exchange_auth_code(settings, code)
    except google_oauth.GoogleOAuthError as exc:
        raise GoogleCalendarError("Could not connect Google Calendar.") from exc


async def _access_token(settings: Settings, refresh_token: str) -> str:
    try:
        return await google_oauth.refresh_access_token(settings, refresh_token)
    except google_oauth.GoogleOAuthError as exc:
        raise GoogleCalendarError("Google Calendar authorization expired.") from exc


def _parse_event_time(raw: dict[str, Any], tz_name: str) -> datetime | None:
    if not isinstance(raw, dict):
        return None
    tz = ZoneInfo(tz_name or "UTC")
    if raw.get("dateTime"):
        value = str(raw["dateTime"])
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(UTC)
        except ValueError:
            return None
    if raw.get("date"):
        try:
            year, month, day = map(int, str(raw["date"]).split("-"))
            local = datetime(year, month, day, tzinfo=tz)
            return local.astimezone(UTC)
        except ValueError:
            return None
    return None


def _events_from_payload(
    data: dict[str, Any],
    *,
    timezone: str,
    calendar_name: str | None = None,
) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        start_raw = item.get("start") or {}
        end_raw = item.get("end") or {}
        all_day = (
            isinstance(start_raw, dict)
            and bool(start_raw.get("date"))
            and not start_raw.get("dateTime")
        )
        start = _parse_event_time(start_raw, timezone)
        if start is None:
            continue
        end = _parse_event_time(end_raw, timezone)
        title = str(item.get("summary") or "Busy").strip() or "Busy"
        location_raw = item.get("location")
        location = str(location_raw).strip() if location_raw else None
        event_id = str(item.get("id") or f"{title}:{start.isoformat()}").strip()
        events.append(
            CalendarEvent(
                id=event_id,
                title=title,
                start=start,
                end=end,
                location=location,
                all_day=all_day,
                calendar_name=calendar_name,
            )
        )
    return events


async def _list_selected_calendars(
    client: httpx.AsyncClient,
    headers: dict[str, str],
) -> list[tuple[str, str]]:
    response = await client.get(CALENDAR_LIST_URL, headers=headers)
    response.raise_for_status()
    calendars: list[tuple[str, str]] = []
    for item in response.json().get("items") or []:
        if not isinstance(item, dict):
            continue
        if item.get("selected") is False:
            continue
        cal_id = str(item.get("id") or "").strip()
        if not cal_id:
            continue
        name = str(item.get("summary") or cal_id).strip()
        calendars.append((cal_id, name))
    return calendars


async def _fetch_events_for_calendar(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    calendar_id: str,
    calendar_name: str,
    time_min: str,
    time_max: str,
    timezone: str,
    max_results: int,
) -> list[CalendarEvent]:
    url = CALENDAR_EVENTS_URL.format(calendar_id=quote(calendar_id, safe=""))
    params = {
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": str(max_results),
        "timeZone": timezone,
    }
    response = await client.get(url, params=params, headers=headers)
    response.raise_for_status()
    return _events_from_payload(
        response.json(),
        timezone=timezone,
        calendar_name=calendar_name,
    )


async def list_upcoming_events(
    settings: Settings,
    *,
    refresh_token: str,
    calendar_id: str = "primary",
    timezone: str | None = None,
    days: int = 7,
) -> CalendarFetchResult:
    if not is_configured(settings):
        return CalendarFetchResult(events=[])

    tz = timezone or "UTC"
    access = await _access_token(settings, refresh_token)
    now = datetime.now(UTC)
    time_min = now.isoformat().replace("+00:00", "Z")
    time_max = (now + timedelta(days=max(1, days))).isoformat().replace("+00:00", "Z")
    headers = {"Authorization": f"Bearer {access}"}
    per_calendar_max = max(20, min(100, days * 2))

    try:
        client = get_pooled_client(DEFAULT_TIMEOUT)
        if calendar_id == "primary":
            calendars = await _list_selected_calendars(client, headers)
        else:
            calendars = [(calendar_id, calendar_id)]

        if not calendars:
            calendars = [("primary", "Primary")]

        max_calendars = max(1, settings.calendar_max_calendars)
        if len(calendars) > max_calendars:
            logger.info(
                "Capping calendar fan-out from %s to %s selected calendars",
                len(calendars),
                max_calendars,
            )
            calendars = calendars[:max_calendars]

        semaphore = asyncio.Semaphore(max(1, settings.calendar_fetch_concurrency))

        async def _bounded_fetch(cal_id: str, cal_name: str) -> list[CalendarEvent]:
            async with semaphore:
                return await _fetch_events_for_calendar(
                    client,
                    headers,
                    calendar_id=cal_id,
                    calendar_name=cal_name,
                    time_min=time_min,
                    time_max=time_max,
                    timezone=tz,
                    max_results=per_calendar_max,
                )

        batches = await asyncio.gather(
            *(_bounded_fetch(cal_id, cal_name) for cal_id, cal_name in calendars),
            return_exceptions=True,
        )
    except Exception:
        logger.exception("Google Calendar events fetch failed")
        raise GoogleCalendarError("Could not load calendar events.") from None

    merged: dict[str, CalendarEvent] = {}
    failed_calendars = 0
    for batch in batches:
        if isinstance(batch, Exception):
            logger.warning("Skipping calendar batch: %s", batch)
            failed_calendars += 1
            continue
        if not isinstance(batch, list):
            continue
        for event in batch:
            merged.setdefault(event.id, event)

    return CalendarFetchResult(
        events=sorted(merged.values(), key=lambda event: event.start),
        failed_calendars=failed_calendars,
    )


async def create_event(
    settings: Settings,
    *,
    refresh_token: str,
    calendar_id: str,
    title: str,
    start: datetime,
    end: datetime,
    timezone: str,
    location: str | None = None,
    description: str | None = None,
) -> CalendarEvent:
    if not is_configured(settings):
        raise GoogleCalendarError("Google Calendar is not configured.")

    access = await _access_token(settings, refresh_token)
    headers = {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "summary": title.strip() or "Event",
        "start": {
            "dateTime": start.astimezone(ZoneInfo(timezone)).isoformat(),
            "timeZone": timezone,
        },
        "end": {"dateTime": end.astimezone(ZoneInfo(timezone)).isoformat(), "timeZone": timezone},
    }
    if location:
        body["location"] = location
    if description:
        body["description"] = description

    url = CALENDAR_EVENTS_URL.format(calendar_id=quote(calendar_id or "primary", safe=""))
    try:
        client = get_pooled_client(DEFAULT_TIMEOUT)
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.exception("Google Calendar create event failed")
        raise GoogleCalendarError("Could not create calendar event.") from exc

    parsed = _events_from_payload({"items": [data]}, timezone=timezone)
    if not parsed:
        raise GoogleCalendarError("Created event could not be parsed.")
    return parsed[0]
