"""Symmetric encryption for OAuth refresh tokens at rest.

Calendar and Gmail integrations store Google OAuth refresh tokens in Postgres.
A database leak must not expose reusable tokens, so they're encrypted with
Fernet (authenticated symmetric encryption) keyed off ``OAUTH_TOKEN_ENCRYPTION_KEY``.

Backward compatibility: existing rows written before encryption was added hold
plaintext Google tokens (``g/…`` / ``1//…``). Those still decrypt as passthrough.
Ciphertext that fails under the current key (rotation mismatch) fails closed —
we never treat Fernet garbage as a Google refresh token.
"""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings

logger = logging.getLogger(__name__)

_PLAINTEXT_PREFIXES = ("g/", "1//")  # Google refresh tokens start with these
# Fernet tokens are urlsafe-base64 and typically start with this version byte.
_FERNET_PREFIX = "gAAAA"


class OAuthTokenDecryptError(ValueError):
    """Stored ciphertext cannot be decrypted with the configured key."""


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

    Legacy plaintext Google tokens (known prefixes) pass through. Ciphertext
    that fails ``InvalidToken`` raises ``OAuthTokenDecryptError`` so a rotated
    key cannot silently feed Fernet bytes to Google.
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
    except InvalidToken as exc:
        if stored.startswith(_FERNET_PREFIX):
            logger.error("OAuth refresh token decrypt failed (key rotation?)")
            raise OAuthTokenDecryptError(
                "Cannot decrypt OAuth refresh token; reconnect the integration."
            ) from exc
        # Non-Fernet, non-Google-prefix legacy row — tolerate as plaintext.
        return stored
