import asyncio
import logging
from typing import Any

from google.auth import exceptions as google_exceptions
from google.auth.transport import requests
from google.oauth2 import id_token

from app.core.blocking import run_blocking
from app.core.config import Settings
from app.core.validation import claim_is_true
from app.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

# Reuse one Request (and its underlying Session) so Google cert fetches get
# HTTP keep-alive instead of a cold TLS handshake on every sign-in.
_google_request: requests.Request | None = None

# Extra wait past the HTTP timeout before giving up on the worker thread
# (DNS resolution is not covered by the requests timeout).
_THREAD_GRACE_SECONDS = 2.0


def _shared_google_request() -> requests.Request:
    global _google_request
    if _google_request is None:
        _google_request = requests.Request()
    return _google_request


class GoogleAuthError(AuthenticationError):
    """A Google ID token the server does not accept."""


class GoogleAuthUnavailableError(Exception):
    """Google's signing certs could not be fetched in time; the token is not judged.

    Not a ``GoogleAuthError``: callers answer 503 (retry) rather than 401,
    which the app treats as "signed out".
    """

    code = "google_unavailable"


class _BoundedRequest:
    """Google transport callable that never waits longer than ``timeout``.

    ``id_token.verify_oauth2_token`` calls the transport without a timeout,
    so google-auth's 120s default applied to every cert fetch.
    """

    def __init__(self, inner: requests.Request, timeout: float) -> None:
        self._inner = inner
        self._timeout = timeout

    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: Any = None,
        headers: Any = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        bounded = self._timeout if timeout is None else min(timeout, self._timeout)
        return self._inner(
            url, method=method, body=body, headers=headers, timeout=bounded, **kwargs
        )


def _verify_google_id_token_sync(id_token_str: str, settings: Settings) -> dict[str, Any]:
    request = _BoundedRequest(_shared_google_request(), settings.google_auth_timeout_seconds)
    try:
        # google-auth ships no type hints for id_token.
        payload: dict[str, Any] = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            id_token_str,
            request,
            settings.google_client_id,
        )
    except google_exceptions.TransportError as exc:
        logger.warning("Google cert fetch failed: %s", exc)
        raise GoogleAuthUnavailableError("Google sign-in is unavailable right now") from exc
    except (ValueError, google_exceptions.GoogleAuthError) as exc:
        # GoogleAuthError covers a wrong issuer, which used to surface as a 500.
        logger.warning("Google ID token verification failed: %s", exc)
        raise GoogleAuthError("Invalid Google ID token", code="google_token_invalid") from exc

    if not claim_is_true(payload.get("email_verified")):
        raise GoogleAuthError(
            "Google email address is not verified", code="google_email_unverified"
        )

    return payload


async def verify_google_id_token(id_token_str: str, settings: Settings) -> dict[str, Any]:
    """Verify a Google ID token off the event loop, on sign-in's own threads.

    Its own pool (``core/blocking.py``): queued behind R2 calls and PDF parses on the
    shared one, sign-in ran past its budget and answered 503.
    """
    deadline = settings.google_auth_timeout_seconds + _THREAD_GRACE_SECONDS
    try:
        return await asyncio.wait_for(
            run_blocking("sign_in", _verify_google_id_token_sync, id_token_str, settings),
            timeout=deadline,
        )
    except TimeoutError as exc:
        logger.warning("Google ID token verification timed out after %.1fs", deadline)
        raise GoogleAuthUnavailableError("Google sign-in is unavailable right now") from exc
