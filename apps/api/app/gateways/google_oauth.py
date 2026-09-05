"""Shared Google OAuth helpers (auth-code exchange, token refresh, userinfo).

Calendar and Gmail gateways wrap these with product-specific error types.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
DEFAULT_TIMEOUT = 15.0
_PERMANENT_OAUTH_ERRORS = frozenset({"invalid_grant", "invalid_client", "unauthorized_client"})


class GoogleOAuthError(Exception):
    def __init__(self, message: str, *, permanent: bool = False) -> None:
        super().__init__(message)
        self.permanent = permanent


async def exchange_auth_code(settings: Settings, code: str) -> dict[str, Any]:
    if not settings.google_client_id.strip() or not settings.google_client_secret.strip():
        raise GoogleOAuthError("Google OAuth is not configured on the server.")

    payload = {
        "code": code.strip(),
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "grant_type": "authorization_code",
    }
    try:
        client = get_pooled_client(DEFAULT_TIMEOUT)
        response = await client.post(TOKEN_URL, data=payload)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.exception("Google OAuth auth code exchange failed")
        raise GoogleOAuthError("Could not complete Google authorization.") from exc


async def refresh_access_token(settings: Settings, refresh_token: str) -> str:
    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        client = get_pooled_client(DEFAULT_TIMEOUT)
        response = await client.post(TOKEN_URL, data=payload)
    except Exception as exc:
        logger.exception("Google OAuth token refresh failed")
        raise GoogleOAuthError("Google authorization expired.") from exc

    if response.status_code >= 400:
        permanent = _oauth_error_is_permanent(response)
        logger.warning(
            "Google OAuth token refresh rejected status=%s permanent=%s",
            response.status_code,
            permanent,
        )
        raise GoogleOAuthError("Google authorization expired.", permanent=permanent)

    data = response.json()
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise GoogleOAuthError("Google authorization expired.")
    return token


def _oauth_error_is_permanent(response: httpx.Response) -> bool:
    if response.status_code not in {400, 401}:
        return False
    try:
        payload = response.json()
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    error = str(payload.get("error") or "").strip().lower()
    return error in _PERMANENT_OAUTH_ERRORS


async def fetch_google_email(access_token: str) -> str | None:
    cleaned = access_token.strip()
    if not cleaned:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {cleaned}"},
            )
            response.raise_for_status()
            data = response.json()
            email = str(data.get("email") or "").strip()
            return email or None
    except Exception:
        logger.exception("Failed to fetch Google account email")
        return None
