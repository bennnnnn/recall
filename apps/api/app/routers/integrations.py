from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_redis, get_settings_dep
from app.gateways.google_calendar_gateway import GoogleCalendarError
from app.models.orm import User
from app.models.schemas import (
    CalendarConflictOut,
    CalendarConflictsOut,
    CalendarEventProposalIn,
    CalendarEventProposalOut,
    GoogleCalendarConnectRequest,
    GoogleCalendarEventOut,
    GoogleCalendarEventsOut,
    GoogleCalendarStatusOut,
)
from app.repositories import calendar_connections as calendar_repo
from app.services import calendar as calendar_service
from app.services import google_integrations as google_integrations_service

router = APIRouter(prefix="/integrations/google-calendar", tags=["integrations"])


@router.get("/status", response_model=GoogleCalendarStatusOut)
async def calendar_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> GoogleCalendarStatusOut:
    row = await calendar_repo.get_for_user(session, user.id)
    return GoogleCalendarStatusOut(
        connected=row is not None,
        email=row.google_email if row else None,
        configured=bool(settings.google_client_id and settings.google_client_secret),
        can_write=calendar_service.has_write_scope(row.scopes) if row else False,
    )


@router.get("/events", response_model=GoogleCalendarEventsOut)
async def calendar_events(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> GoogleCalendarEventsOut:
    raw = await calendar_service.list_events_for_api(session, redis, user, settings)
    events = [
        GoogleCalendarEventOut(
            id=event.id,
            title=event.title,
            start_at=event.start,
            end_at=event.end,
            location=event.location,
            all_day=event.all_day,
            calendar_name=event.calendar_name,
        )
        for event in raw.events
    ]
    return GoogleCalendarEventsOut(events=events, load_error=raw.load_error)


@router.post("/connect", response_model=GoogleCalendarStatusOut)
async def connect_calendar(
    body: GoogleCalendarConnectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> GoogleCalendarStatusOut:
    try:
        result = await google_integrations_service.connect_calendar(
            session, redis, settings, user, body.server_auth_code
        )
    except google_integrations_service.GoogleConnectError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return GoogleCalendarStatusOut(
        connected=True,
        email=result.email,
        configured=True,
        can_write=calendar_service.has_write_scope(result.scopes),
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_calendar(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    await google_integrations_service.disconnect_calendar(session, redis, settings, user.id)


@router.post("/events/propose", response_model=CalendarEventProposalOut)
async def propose_calendar_event(
    body: CalendarEventProposalIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> CalendarEventProposalOut:
    if body.end_at <= body.start_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="end_at must be after start_at"
        )
    connection = await calendar_repo.get_for_user(session, user.id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Calendar not connected"
        )
    if not calendar_service.has_write_scope(connection.scopes):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calendar write access required. Re-connect with write permission in Settings.",
        )
    proposal_id = str(uuid4())
    await calendar_service.store_event_proposal(
        redis,
        user.id,
        proposal_id,
        {
            "title": body.title,
            "start": body.start_at.isoformat(),
            "end": body.end_at.isoformat(),
            "location": body.location or "",
            "description": body.description or "",
        },
    )
    return CalendarEventProposalOut(
        proposal_id=proposal_id,
        title=body.title,
        start_at=body.start_at,
        end_at=body.end_at,
        location=body.location,
    )


@router.post("/events/{proposal_id}/confirm", response_model=GoogleCalendarEventOut)
async def confirm_calendar_event(
    proposal_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> GoogleCalendarEventOut:
    try:
        event = await calendar_service.confirm_create_event(
            session, redis, user, settings, proposal_id
        )
    except GoogleCalendarError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return GoogleCalendarEventOut(
        id=event.id,
        title=event.title,
        start_at=event.start,
        end_at=event.end,
        location=event.location,
        all_day=event.all_day,
        calendar_name=event.calendar_name,
    )


@router.get("/conflicts", response_model=CalendarConflictsOut)
async def calendar_conflicts(
    due_at: datetime = Query(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> CalendarConflictsOut:
    result = await calendar_service.list_events_for_api(session, redis, user, settings)
    conflicts = calendar_service.find_conflicting_events(result.events, due_at)
    return CalendarConflictsOut(
        conflicts=[
            CalendarConflictOut(
                event_id=e.id,
                title=e.title,
                start_at=e.start,
                end_at=e.end,
            )
            for e in conflicts
        ]
    )
