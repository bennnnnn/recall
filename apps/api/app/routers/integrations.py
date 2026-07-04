import logging
from datetime import datetime
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_redis, get_settings_dep
from app.core.secrets import encrypt_refresh_token
from app.gateways.google_calendar_gateway import GoogleCalendarError, exchange_server_auth_code
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
from app.services import home as home_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/google-calendar", tags=["integrations"])


async def _fetch_google_email(access_token: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            email = str(data.get("email") or "").strip()
            return email or None
    except Exception:
        logger.exception("Failed to fetch Google account email")
        return None


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
        token_data = await exchange_server_auth_code(settings, body.server_auth_code)
    except GoogleCalendarError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    refresh_token_raw = str(token_data.get("refresh_token") or "").strip()
    access_token = str(token_data.get("access_token") or "").strip()
    if not refresh_token_raw:
        existing = await calendar_repo.get_for_user(session, user.id)
        if existing:
            # Reuse the already-encrypted stored token (e.g. re-grant without a
            # new refresh token). Don't re-encrypt — it's already ciphertext.
            refresh_token = existing.refresh_token
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google did not return a refresh token. Revoke Recall in your Google account and try again.",
            )
    else:
        # Fresh token from Google — encrypt before it touches the DB.
        refresh_token = encrypt_refresh_token(settings, refresh_token_raw)

    email = await _fetch_google_email(access_token) if access_token else None
    google_email = email or user.email
    scopes = str(token_data.get("scope") or "calendar.readonly")

    await calendar_repo.upsert(
        session,
        user_id=user.id,
        google_email=google_email,
        refresh_token=refresh_token,
        scopes=scopes,
    )
    try:
        await redis.delete(calendar_service._cache_key(user.id))
    except Exception:
        logger.exception("Failed to clear calendar cache after connect")
    await home_service.invalidate_home_cache(user.id)
    return GoogleCalendarStatusOut(
        connected=True,
        email=google_email,
        configured=True,
        can_write=calendar_service.has_write_scope(scopes),
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_calendar(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    await google_integrations_service.revoke_on_disconnect(
        session,
        settings,
        user.id,
        disconnect="calendar",
    )
    await calendar_repo.delete_for_user(session, user.id)
    try:
        await redis.delete(calendar_service._cache_key(user.id))
    except Exception:
        logger.exception("Failed to clear calendar cache after disconnect")
    await home_service.invalidate_home_cache(user.id)


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
