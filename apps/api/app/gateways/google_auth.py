import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from google.auth.transport import requests
from google.oauth2 import id_token

from app.core.config import Settings

logger = logging.getLogger(__name__)


class GoogleAuthError(Exception):
    pass


def verify_google_id_token(id_token_str: str, settings: Settings) -> dict:
    try:
        return id_token.verify_oauth2_token(
            id_token_str,
            requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        logger.warning("Google ID token verification failed: %s", exc)
        raise GoogleAuthError("Invalid Google ID token") from exc


def create_access_token(user_id: UUID, settings: Settings) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise GoogleAuthError("Invalid access token") from exc
