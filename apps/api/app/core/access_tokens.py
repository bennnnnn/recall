"""App JWT access tokens (create / decode). Not Google OAuth."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import Settings


class AccessTokenError(Exception):
    """Raised when an access JWT is missing, malformed, or otherwise invalid."""


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
        raise AccessTokenError("Invalid access token") from exc
