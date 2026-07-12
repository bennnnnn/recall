from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_redis, get_settings_dep
from app.gateways.google_gmail_gateway import GoogleGmailError
from app.models.orm import User
from app.models.schemas import (
    GoogleGmailConnectRequest,
    GoogleGmailStatusOut,
    SuggestedReminderOut,
    SuggestedRemindersOut,
    TodoOut,
)
from app.repositories import gmail_connections as gmail_repo
from app.repositories import suggested_reminders as suggested_repo
from app.services import email as email_service
from app.services import google_integrations as google_integrations_service

router = APIRouter(prefix="/integrations/google-gmail", tags=["integrations"])


@router.get("/status", response_model=GoogleGmailStatusOut)
async def gmail_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> GoogleGmailStatusOut:
    row = await gmail_repo.get_for_user(session, user.id)
    return GoogleGmailStatusOut(
        connected=row is not None,
        email=row.google_email if row else None,
        configured=bool(
            settings.google_client_id and settings.google_client_secret and settings.gmail_enabled
        ),
        last_sync_at=row.last_sync_at if row else None,
    )


@router.post("/connect", response_model=GoogleGmailStatusOut)
async def connect_gmail(
    body: GoogleGmailConnectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> GoogleGmailStatusOut:
    try:
        result = await google_integrations_service.connect_gmail(
            session, redis, settings, user, body.server_auth_code
        )
    except google_integrations_service.GoogleConnectError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return GoogleGmailStatusOut(
        connected=True,
        email=result.email,
        configured=True,
        last_sync_at=None,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_gmail(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    await google_integrations_service.disconnect_gmail(session, redis, settings, user.id)


@router.post("/sync")
async def sync_gmail(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
    force: bool = False,
) -> dict[str, int | str | bool]:
    conn = await gmail_repo.get_for_user(session, user.id)
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail is not connected."
        )
    if not email_service.gmail_sync_is_due(conn.last_sync_at, settings, force=force):
        return {
            "status": "skipped",
            "message_count": 0,
            "reminders_created": 0,
            "skipped": True,
        }
    try:
        message_count, reminders_created = await email_service.sync_gmail_for_user(
            session,
            settings,
            user.id,
            redis=redis,
        )
    except GoogleGmailError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {
        "status": "ok",
        "message_count": message_count,
        "reminders_created": reminders_created,
        "skipped": False,
    }


@router.get("/suggested-reminders", response_model=SuggestedRemindersOut)
async def list_suggested_reminders(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SuggestedRemindersOut:
    rows = await suggested_repo.list_pending_for_user(session, user.id)
    return SuggestedRemindersOut(
        reminders=[SuggestedReminderOut.model_validate(row) for row in rows],
        pending_count=len(rows),
    )


@router.post("/suggested-reminders/{reminder_id}/add", response_model=TodoOut)
async def add_suggested_reminder(
    reminder_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TodoOut:
    todo, error = await email_service.add_suggested_reminder(
        session, settings, user.id, reminder_id
    )
    if todo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Could not add reminder",
        )
    return TodoOut.model_validate(todo)


@router.post("/suggested-reminders/{reminder_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_suggested_reminder(
    reminder_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    ok = await email_service.dismiss_suggested_reminder(session, user.id, reminder_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
