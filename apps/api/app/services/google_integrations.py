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
from app.core.secrets import (
    OAuthTokenDecryptError,
    decrypt_refresh_token,
    encrypt_refresh_token,
)
from app.gateways import (
    google_calendar_gateway,
    google_gmail_gateway,
    google_oauth,
    google_oauth_revoke,
)
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
    try:
        return decrypt_refresh_token(settings, stored).strip()
    except OAuthTokenDecryptError as exc:
        raise GoogleConnectError(str(exc)) from exc


def _google_emails_match(left: str | None, right: str | None) -> bool:
    a = (left or "").strip().lower()
    b = (right or "").strip().lower()
    return bool(a and a == b)


def _resolve_stored_refresh_token(
    settings: Settings,
    refresh_token_raw: str,
    existing_encrypted: str | None,
    *,
    sibling_encrypted: str | None = None,
    sibling_google_email: str | None = None,
    connect_google_email: str | None = None,
) -> str:
    cleaned = refresh_token_raw.strip()
    if cleaned:
        return encrypt_refresh_token(settings, cleaned)
    if existing_encrypted:
        # Reuse the already-encrypted stored token (e.g. re-grant without a
        # new refresh token). Don't re-encrypt — it's already ciphertext.
        return existing_encrypted
    # Incremental Google grants often omit refresh_token. The sibling
    # product's token is the same grant when both rows are the same account.
    if sibling_encrypted and _google_emails_match(sibling_google_email, connect_google_email):
        return sibling_encrypted
    raise GoogleConnectError(_MISSING_REFRESH)


async def revoke_on_disconnect(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    *,
    disconnect: Literal["calendar", "gmail"],
) -> bool:
    """Revoke the Google refresh token for the product being disconnected.

    Returns True when Calendar and Gmail shared that token so the sibling
    product must also be disconnected locally (Google revoke is all-or-nothing;
    the remaining product has to reconnect with only its scopes).
    """
    calendar = await calendar_repo.get_for_user(session, user_id)
    gmail = await gmail_repo.get_for_user(session, user_id)

    if disconnect == "calendar":
        if calendar is None:
            return False
        cal_token = _decrypt_token(settings, calendar.refresh_token)
        if not cal_token:
            return False
        shared = False
        if gmail is not None:
            gmail_token = _decrypt_token(settings, gmail.refresh_token)
            shared = bool(gmail_token and gmail_token == cal_token)
        await google_oauth_revoke.revoke_refresh_token(cal_token)
        return shared

    if gmail is None:
        return False
    gmail_token = _decrypt_token(settings, gmail.refresh_token)
    if not gmail_token:
        return False
    shared = False
    if calendar is not None:
        cal_token = _decrypt_token(settings, calendar.refresh_token)
        shared = bool(cal_token and cal_token == gmail_token)
    await google_oauth_revoke.revoke_refresh_token(gmail_token)
    return shared


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
    # Gate the whole connect path on the feature flag + client creds, mirroring
    # Gmail's `exchange_gmail_auth_code` is_configured check. Without this, a
    # deployment that disabled google_calendar_enabled still accepted connects
    # and stored rows that every later fetch would reject — a connected-but-
    # broken state with no in-app signal that the feature is off.
    if not google_calendar_gateway.is_configured(settings):
        raise GoogleConnectError(
            "Calendar integration is not available. Contact support if this is unexpected."
        )
    try:
        token_data = await exchange_server_auth_code(settings, server_auth_code)
    except GoogleCalendarError as exc:
        raise GoogleConnectError(str(exc)) from exc

    refresh_token_raw = str(token_data.get("refresh_token") or "").strip()
    access_token = str(token_data.get("access_token") or "").strip()
    existing = await calendar_repo.get_for_user(session, user.id)
    gmail = await gmail_repo.get_for_user(session, user.id)

    email = await google_oauth.fetch_google_email(access_token) if access_token else None
    google_email = email or user.email
    scopes = str(token_data.get("scope") or "")
    # Exact OAuth tokens only — substring "calendar.readonly" is not enough
    # (and must not confuse calendar.events.readonly with write events).
    scope_tokens = {token for token in scopes.split() if token}
    if (
        google_calendar_gateway.CALENDAR_READONLY_SCOPE not in scope_tokens
        and google_calendar_gateway.CALENDAR_EVENTS_SCOPE not in scope_tokens
    ):
        raise GoogleConnectError(
            "Calendar read permission was not granted. Try disconnecting Calendar, "
            "revoke Recall in your Google account, then connect again."
        )

    refresh_token = _resolve_stored_refresh_token(
        settings,
        refresh_token_raw,
        existing.refresh_token if existing else None,
        sibling_encrypted=gmail.refresh_token if gmail else None,
        sibling_google_email=gmail.google_email if gmail else None,
        # Verified Google email only — never fall back to user.email for
        # sibling reuse (Apple/private-relay accounts can disagree).
        connect_google_email=email,
    )

    await calendar_repo.upsert(
        session,
        user_id=user.id,
        google_email=google_email,
        refresh_token=refresh_token,
        scopes=scopes,
    )
    if refresh_token_raw and gmail is not None and _google_emails_match(email, gmail.google_email):
        await gmail_repo.upsert(
            session,
            user_id=user.id,
            google_email=gmail.google_email,
            refresh_token=refresh_token,
            scopes=gmail.scopes,
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
    try:
        shared = await revoke_on_disconnect(session, settings, user_id, disconnect="calendar")
    except GoogleConnectError:
        # Decrypt/key-rotation failures must not block disconnect — revocation
        # is best-effort; leaving the row would make reconnect re-store the
        # same undecryptable ciphertext with no in-app recovery path.
        logger.warning(
            "Google token revoke failed during calendar disconnect; continuing delete user_id=%s",
            user_id,
            exc_info=True,
        )
        shared = False
    await calendar_repo.delete_for_user(session, user_id)
    await calendar_service.clear_events_cache(redis, user_id)
    if shared is True:
        await suggested_repo.delete_for_user(session, user_id)
        await gmail_repo.delete_for_user(session, user_id)
        await email_service.clear_gmail_cache(redis, user_id)
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
    calendar = await calendar_repo.get_for_user(session, user.id)

    email = await google_oauth.fetch_google_email(access_token) if access_token else None
    if not email:
        raise GoogleConnectError(
            "Could not verify the Gmail account. Connect again and grant Gmail read access."
        )
    scopes = str(token_data.get("scope") or "")
    scope_tokens = {token for token in scopes.split() if token}
    if google_gmail_gateway.GMAIL_READONLY_SCOPE not in scope_tokens:
        raise GoogleConnectError(
            "Gmail read permission was not granted. Try disconnecting Gmail, "
            "revoke Recall in your Google account, then connect again."
        )

    refresh_token = _resolve_stored_refresh_token(
        settings,
        refresh_token_raw,
        existing.refresh_token if existing else None,
        sibling_encrypted=calendar.refresh_token if calendar else None,
        sibling_google_email=calendar.google_email if calendar else None,
        connect_google_email=email,
    )

    await gmail_repo.upsert(
        session,
        user_id=user.id,
        google_email=email,
        refresh_token=refresh_token,
        scopes=scopes or "gmail.readonly",
    )
    if (
        refresh_token_raw
        and calendar is not None
        and _google_emails_match(email, calendar.google_email)
    ):
        await calendar_repo.upsert(
            session,
            user_id=user.id,
            google_email=calendar.google_email,
            refresh_token=refresh_token,
            scopes=calendar.scopes,
            calendar_id=calendar.calendar_id,
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
    try:
        shared = await revoke_on_disconnect(session, settings, user_id, disconnect="gmail")
    except GoogleConnectError:
        logger.warning(
            "Google token revoke failed during Gmail disconnect; continuing delete user_id=%s",
            user_id,
            exc_info=True,
        )
        shared = False
    await suggested_repo.delete_for_user(session, user_id)
    await gmail_repo.delete_for_user(session, user_id)
    await email_service.clear_gmail_cache(redis, user_id)
    if shared is True:
        await calendar_repo.delete_for_user(session, user_id)
        await calendar_service.clear_events_cache(redis, user_id)
    await home_service.invalidate_home_cache(user_id)
