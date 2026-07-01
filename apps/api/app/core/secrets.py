"""Symmetric encryption for OAuth refresh tokens at rest.

Calendar and Gmail integrations store Google OAuth refresh tokens in Postgres.
A database leak must not expose reusable tokens, so they're encrypted with
Fernet (authenticated symmetric encryption) keyed off ``OAUTH_TOKEN_ENCRYPTION_KEY``.

Backward compatibility: existing rows written before encryption was added hold
plaintext tokens. ``decrypt_refresh_token`` treats a value that fails to
decrypt as plaintext and returns it as-is, so the app keeps working through the
migration. The next write re-encrypts it, so tokens converge to encrypted form
as users reconnect.
"""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings

logger = logging.getLogger(__name__)

_PLAINTEXT_PREFIXES = ("g/", "1//")  # Google refresh tokens start with these


def _fernet(settings: Settings) -> Fernet | None:
    key = settings.oauth_token_encryption_key.strip()
    if not key:
        return None
    return Fernet(key.encode())


def encrypt_refresh_token(settings: Settings, token: str) -> str:
    """Encrypt a refresh token for storage. Falls back to plaintext in dev."""
    if not token:
        return token
    f = _fernet(settings)
    if f is None:
        # Dev only — production startup rejects an empty key.
        logger.debug("Storing refresh token plaintext (no encryption key configured)")
        return token
    return f.encrypt(token.encode()).decode()


def decrypt_refresh_token(settings: Settings, stored: str) -> str:
    """Decrypt a stored refresh token for use with Google APIs.

    Tolerates plaintext (pre-migration) values: if ``stored`` isn't a valid
    Fernet token, return it unchanged. This makes the rollout non-breaking —
    existing connections keep working and get re-encrypted on the next write.
    """
    if not stored:
        return stored
    f = _fernet(settings)
    if f is None:
        return stored
    # Fast path: a plaintext Google token is never a valid Fernet token, so
    # this avoids a thrown+caught InvalidToken on every read of legacy rows.
    if stored.startswith(_PLAINTEXT_PREFIXES):
        return stored
    try:
        return f.decrypt(stored.encode()).decode()
    except InvalidToken:
        # Not encrypted (legacy row) or encrypted under a rotated key we no
        # longer hold — treat as plaintext so the connection still works.
        return stored
