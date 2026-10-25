"""What a refused sign-in answers: its status, and a code the login screen words.

The login screen showed the server's English as it came ("Invalid Google ID token",
"Google sign-in is unavailable right now", "Apple email address is not verified") in
every language. Each refusal of ``/auth/google``, ``/auth/apple`` and ``/auth/dev`` now
names a code (``docs/fixtures/error_codes.json``), and the phone shows its own line for it:

* **401** ``google_token_invalid``, ``apple_token_invalid``, ``apple_key_unknown``: the
  token does not verify. ``google_email_unverified``, ``apple_email_unverified``: the
  provider has not verified the address. ``google_email_missing``,
  ``apple_email_missing``: a new account, and the provider shared no address.
  ``apple_not_configured``: this server has no Apple client id.
* **403** ``dev_auth_disabled``: dev login is off.
* **409** ``account_exists`` (``email_authority.py``).
* **429** ``sign_in_rate_limited``: this identity or address signed in too often
  (``signin_limit.py``).
* **503** ``google_unavailable``, ``apple_unavailable``: the provider's keys could not be
  fetched, so the token was not judged: retry, never a 401 the app reads as signed out.

A body that fails validation keeps FastAPI's 422, and a dev login from another host its
bare 404: the phone sends neither, and words both as a failed sign-in.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from app.exceptions import AuthenticationError, DomainError
from app.modules.account import service as auth_service
from app.modules.account import signin_limit

_PROVIDER_RETRY_AFTER_SECONDS = 5


class SignInRefusedError(DomainError):
    """A sign-in the API turns away: 401 unless it says otherwise."""

    status_code = 401
    default_code = "sign_in_failed"


def rate_limited() -> SignInRefusedError:
    # A Redis outage answers this too: every sign-in limit fails closed.
    return SignInRefusedError(
        "Too many login attempts. Try again shortly.",
        status_code=429,
        code="sign_in_rate_limited",
        headers={"Retry-After": str(signin_limit.WINDOW_SECONDS)},
    )


def dev_disabled() -> SignInRefusedError:
    return SignInRefusedError("Dev auth disabled", status_code=403, code="dev_auth_disabled")


@contextmanager
def refusals() -> Iterator[None]:
    """Answers each way a sign-in fails in its block with its status and code."""
    try:
        yield
    except signin_limit.SignInLimitedError as exc:
        raise rate_limited() from exc
    except (auth_service.GoogleAuthUnavailableError, auth_service.AppleAuthUnavailableError) as exc:
        raise SignInRefusedError(
            str(exc),
            status_code=503,
            code=exc.code,
            headers={"Retry-After": str(_PROVIDER_RETRY_AFTER_SECONDS)},
        ) from exc
    except AuthenticationError as exc:
        raise SignInRefusedError(str(exc), code=exc.code) from exc
