"""Revoke Google OAuth refresh tokens (best-effort; never raises)."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

REVOKE_URL = "https://oauth2.googleapis.com/revoke"
DEFAULT_TIMEOUT = 10.0


async def revoke_refresh_token(token: str) -> bool:
    """Ask Google to invalidate a refresh token. Returns True when accepted."""
    cleaned = token.strip()
    if not cleaned:
        return False
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                REVOKE_URL,
                params={"token": cleaned},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.status_code == 200:
            return True
        if response.status_code == 400:
            # Already invalid or unknown — treat as done for our purposes.
            return True
        logger.warning(
            "Google OAuth revoke unexpected status=%s body=%s",
            response.status_code,
            response.text[:200],
        )
        return False
    except Exception:
        logger.warning("Google OAuth revoke failed", exc_info=True)
        return False
