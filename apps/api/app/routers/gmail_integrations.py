import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_redis, get_settings_dep
from app.gateways.google_gmail_gateway import GoogleGmailError, exchange_gmail_auth_code
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/google-gmail", tags=["integrations"])


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
        token_data = await exchange_gmail_auth_code(settings, body.server_auth_code)
    except GoogleGmailError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    refresh_token = str(token_data.get("refresh_token") or "").strip()
    access_token = str(token_data.get("access_token") or "").strip()
    if not refresh_token:
        existing = await gmail_repo.get_for_user(session, user.id)
        if existing:
            refresh_token = existing.refresh_token
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google did not return a refresh token. Revoke Recall in your Google account and try again.",
            )

    email = await _fetch_google_email(access_token) if access_token else None
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not verify the Gmail account. Connect again and grant Gmail read access.",
        )
    google_email = email
    scopes = str(token_data.get("scope") or "")
    if "gmail.readonly" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail read permission was not granted. Try disconnecting Gmail, "
            "revoke Recall in your Google account, then connect again.",
        )

    await gmail_repo.upsert(
        session,
        user_id=user.id,
        google_email=google_email,
        refresh_token=refresh_token,
        scopes=scopes or "gmail.readonly",
    )
    try:
        from redis.asyncio import Redis

        redis_client: Redis = redis
        await redis_client.delete(email_service._cache_key(user.id))
    except Exception:
        logger.exception("Failed to clear gmail cache after connect")
    try:
        await jobs.enqueue(redis, "gmail_sync", {"user_id": str(user.id)})
    except Exception:
        logger.exception("Failed to enqueue gmail sync after connect")

    return GoogleGmailStatusOut(
        connected=True,
        email=google_email,
        configured=True,
        last_sync_at=None,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_gmail(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    await suggested_repo.delete_for_user(session, user.id)
    await gmail_repo.delete_for_user(session, user.id)


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
