"""Calendar / Gmail home starter chips."""

from __future__ import annotations

from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.schemas import HomeStarter
from app.services import calendar as calendar_service
from app.services import email as email_service
from app.services.home.util import (
    CALENDAR_TODAY_END_HOUR,
    CALENDAR_TOMORROW_END_HOUR,
    CALENDAR_TOMORROW_START_HOUR,
    EMAIL_END_HOUR,
    MORNING_START_HOUR,
    local_hour_for_tz,
)


async def integration_starters(
    session: AsyncSession,
    user_id: UUID,
    settings: Settings,
    *,
    tz: ZoneInfo,
) -> list[HomeStarter]:
    """Surface connected calendar/Gmail as home chips — time-of-day aware."""
    hour = local_hour_for_tz(tz)
    starters: list[HomeStarter] = []

    if settings.google_calendar_enabled and await calendar_service.is_connected(session, user_id):
        if MORNING_START_HOUR <= hour < CALENDAR_TODAY_END_HOUR:
            starters.append(
                HomeStarter(
                    text="Today's calendar",
                    prompt=(
                        "What's on my calendar for the rest of today and what should I prepare for?"
                    ),
                    kind="general",
                )
            )
        elif CALENDAR_TOMORROW_START_HOUR <= hour < CALENDAR_TOMORROW_END_HOUR:
            starters.append(
                HomeStarter(
                    text="Tomorrow's calendar",
                    prompt=(
                        "What's on my calendar tomorrow and what should I prepare ahead of time?"
                    ),
                    kind="general",
                )
            )

    if (
        settings.gmail_enabled
        and await email_service.is_connected(session, user_id)
        and MORNING_START_HOUR <= hour < EMAIL_END_HOUR
    ):
        starters.append(
            HomeStarter(
                text="Email to handle",
                prompt=(
                    "Check my inbox — anything I need to reply to or follow up on this morning?"
                ),
                kind="general",
            )
        )
    return starters
