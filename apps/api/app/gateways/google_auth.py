import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from google.auth.transport import requests
from google.oauth2 import id_token

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Reuse one Request (and its underlying Session) so Google cert fetches can
# hit the library's in-process cache / keep-alive instead of a cold TLS+HTTP
# round-trip on every sign-in.
_google_request: requests.Request | None = None


def _shared_google_request() -> requests.Request:
    global _google_request
    if _google_request is None:
        _google_request = requests.Request()
    return _google_request


class GoogleAuthError(Exception):
    pass


def _verify_google_id_token_sync(id_token_str: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = id_token.verify_oauth2_token(
            id_token_str,
            _shared_google_request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        logger.warning("Google ID token verification failed: %s", exc)
        raise GoogleAuthError("Invalid Google ID token") from exc

    if not _is_email_verified(payload.get("email_verified")):
        raise GoogleAuthError("Google email address is not verified")

    return payload


def _is_email_verified(value: object) -> bool:
    """Affirmative only for an explicit verified claim.

    Google sends a bool, but tolerate the string form ("true"/"false") some
    intermediaries pass through. Missing/None/"false"/0 are unverified.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


async def verify_google_id_token(id_token_str: str, settings: Settings) -> dict[str, Any]:
    """Verify a Google ID token off the event loop (sync cert/HTTP in a thread)."""
    return await asyncio.to_thread(_verify_google_id_token_sync, id_token_str, settings)


def create_access_token(user_id: UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise GoogleAuthError("Invalid access token") from exc
