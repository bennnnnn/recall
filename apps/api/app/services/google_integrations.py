"""Google Calendar/Gmail integration lifecycle helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import Settings
from app.core.secrets import decrypt_refresh_token, encrypt_refresh_token
from app.gateways import google_oauth, google_oauth_revoke
from app.gateways.google_calendar_gateway import GoogleCalendarError, exchange_server_auth_code
from app.gateways.google_gmail_gateway import GoogleGmailError, exchange_gmail_auth_code
from app.models.orm import User
from app.repositories import calendar_connections as calendar_repo
from app.repositories import gmail_connections as gmail_repo
from app.repositories import suggested_reminders as suggested_repo
from app.services import calendar as calendar_service
from app.services import email as email_service
from app.services import home as home_service

logger = logging.getLogger(__name__)

_MISSING_REFRESH = (
    "Google did not return a refresh token. Revoke Recall in your Google account and try again."
)


class GoogleConnectError(Exception):
    """User-facing connect/disconnect failure (map to HTTP 400)."""


@dataclass(frozen=True)
class CalendarConnectResult:
    email: str
    scopes: str


@dataclass(frozen=True)
class GmailConnectResult:
    email: str
    scopes: str


def _decrypt_token(settings: Settings, stored: str) -> str:
    return decrypt_refresh_token(settings, stored).strip()


def _resolve_stored_refresh_token(
    settings: Settings,
    refresh_token_raw: str,
    existing_encrypted: str | None,
) -> str:
    cleaned = refresh_token_raw.strip()
    if cleaned:
        return encrypt_refresh_token(settings, cleaned)
    if existing_encrypted:
        # Reuse the already-encrypted stored token (e.g. re-grant without a
        # new refresh token). Don't re-encrypt — it's already ciphertext.
        return existing_encrypted
    raise GoogleConnectError(_MISSING_REFRESH)


async def revoke_on_disconnect(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    *,
    disconnect: Literal["calendar", "gmail"],
) -> None:
    """Revoke the disconnected integration's refresh token unless Gmail/Calendar share it."""
    calendar = await calendar_repo.get_for_user(session, user_id)
    gmail = await gmail_repo.get_for_user(session, user_id)

    if disconnect == "calendar":
        if calendar is None:
            return
        cal_token = _decrypt_token(settings, calendar.refresh_token)
        if not cal_token:
            return
        if gmail is not None:
            gmail_token = _decrypt_token(settings, gmail.refresh_token)
            if gmail_token and gmail_token == cal_token:
                return
        await google_oauth_revoke.revoke_refresh_token(cal_token)
        return

    if gmail is None:
        return
    gmail_token = _decrypt_token(settings, gmail.refresh_token)
    if not gmail_token:
        return
    if calendar is not None:
        cal_token = _decrypt_token(settings, calendar.refresh_token)
        if cal_token and cal_token == gmail_token:
            return
    await google_oauth_revoke.revoke_refresh_token(gmail_token)


async def revoke_all_google_tokens_for_user(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
) -> None:
    """Best-effort revoke of every unique Google refresh token before account deletion."""
    calendar = await calendar_repo.get_for_user(session, user_id)
    gmail = await gmail_repo.get_for_user(session, user_id)
    seen: set[str] = set()
    for conn in (calendar, gmail):
        if conn is None:
            continue
        raw = _decrypt_token(settings, conn.refresh_token)
        if not raw or raw in seen:
            continue
        seen.add(raw)
        await google_oauth_revoke.revoke_refresh_token(raw)


async def connect_calendar(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    user: User,
    server_auth_code: str,
) -> CalendarConnectResult:
    try:
        token_data = await exchange_server_auth_code(settings, server_auth_code)
    except GoogleCalendarError as exc:
        raise GoogleConnectError(str(exc)) from exc

    refresh_token_raw = str(token_data.get("refresh_token") or "").strip()
    access_token = str(token_data.get("access_token") or "").strip()
    existing = await calendar_repo.get_for_user(session, user.id)
    refresh_token = _resolve_stored_refresh_token(
        settings,
        refresh_token_raw,
        existing.refresh_token if existing else None,
    )

    email = await google_oauth.fetch_google_email(access_token) if access_token else None
    google_email = email or user.email
    scopes = str(token_data.get("scope") or "calendar.readonly")

    await calendar_repo.upsert(
        session,
        user_id=user.id,
        google_email=google_email,
        refresh_token=refresh_token,
        scopes=scopes,
    )
    await calendar_service.clear_events_cache(redis, user.id)
    await home_service.invalidate_home_cache(user.id)
    return CalendarConnectResult(email=google_email, scopes=scopes)


async def disconnect_calendar(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    user_id: UUID,
) -> None:
    await revoke_on_disconnect(session, settings, user_id, disconnect="calendar")
    await calendar_repo.delete_for_user(session, user_id)
    await calendar_service.clear_events_cache(redis, user_id)
    await home_service.invalidate_home_cache(user_id)


async def connect_gmail(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    user: User,
    server_auth_code: str,
) -> GmailConnectResult:
    try:
        token_data = await exchange_gmail_auth_code(settings, server_auth_code)
    except GoogleGmailError as exc:
        raise GoogleConnectError(str(exc)) from exc

    refresh_token_raw = str(token_data.get("refresh_token") or "").strip()
    access_token = str(token_data.get("access_token") or "").strip()
    existing = await gmail_repo.get_for_user(session, user.id)
    refresh_token = _resolve_stored_refresh_token(
        settings,
        refresh_token_raw,
        existing.refresh_token if existing else None,
    )

    email = await google_oauth.fetch_google_email(access_token) if access_token else None
    if not email:
        raise GoogleConnectError(
            "Could not verify the Gmail account. Connect again and grant Gmail read access."
        )
    scopes = str(token_data.get("scope") or "")
    if "gmail.readonly" not in scopes:
        raise GoogleConnectError(
            "Gmail read permission was not granted. Try disconnecting Gmail, "
            "revoke Recall in your Google account, then connect again."
        )

    await gmail_repo.upsert(
        session,
        user_id=user.id,
        google_email=email,
        refresh_token=refresh_token,
        scopes=scopes or "gmail.readonly",
    )
    await email_service.clear_gmail_cache(redis, user.id)
    try:
        await jobs.enqueue(redis, "gmail_sync", {"user_id": str(user.id)})
    except Exception:
        logger.exception("Failed to enqueue gmail sync after connect")
    await home_service.invalidate_home_cache(user.id)
    return GmailConnectResult(email=email, scopes=scopes or "gmail.readonly")


async def disconnect_gmail(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    user_id: UUID,
) -> None:
    await revoke_on_disconnect(session, settings, user_id, disconnect="gmail")
    await suggested_repo.delete_for_user(session, user_id)
    await gmail_repo.delete_for_user(session, user_id)
    await email_service.clear_gmail_cache(redis, user_id)
    await home_service.invalidate_home_cache(user_id)
