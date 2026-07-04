"""Google Calendar/Gmail integration lifecycle helpers."""

from __future__ import annotations

import logging
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.secrets import decrypt_refresh_token
from app.gateways import google_oauth_revoke
from app.repositories import calendar_connections as calendar_repo
from app.repositories import gmail_connections as gmail_repo

logger = logging.getLogger(__name__)


def _decrypt_token(settings: Settings, stored: str) -> str:
    return decrypt_refresh_token(settings, stored).strip()


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
