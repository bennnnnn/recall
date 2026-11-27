"""A new account starts in the language its sign-in page was shown in.

The phone opens in its own language before anyone signs in, and sends that language with
the sign-in. Only a new account takes it: an existing one keeps the language it has, which
is the user's. A language Recall has no strings for is dropped, never a refused sign-in.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import User
from app.models.schemas import AuthResponse
from app.models.schemas.auth import GoogleAuthRequest, UserUpdate
from app.modules.account import service as auth_service
from app.repositories import users

_SETTINGS = Settings(
    dev_auth_enabled=True, email_enabled=False, jwt_secret="test-secret-long-enough-32-chars!!"
)


async def _sign_in(
    provider: str, session: AsyncSession, redis: Redis, sub: str, *, locale: str | None
) -> AuthResponse:
    """One real sign-in through the account service; only the provider's token check is faked."""
    email = f"{sub}@icloud.com"
    payload = {"sub": sub, "email": email, "email_verified": "true", "name": "Ada"}
    if provider == "google":
        with patch(
            "app.modules.account.service.verify_google_id_token", AsyncMock(return_value=payload)
        ):
            return await auth_service.login_with_google(
                session, _SETTINGS, "tok", redis, locale=locale
            )
    if provider == "apple":
        with patch(
            "app.modules.account.service.verify_apple_id_token", AsyncMock(return_value=payload)
        ):
            return await auth_service.login_with_apple(
                session, _SETTINGS, "tok", redis, locale=locale
            )
    return await auth_service.login_dev(
        session, _SETTINGS, email=email, name="Ada", redis=redis, locale=locale
    )


async def _stored_locale(session: AsyncSession, user_id: object) -> str:
    row = await session.get(User, user_id, populate_existing=True)
    assert row is not None
    return row.locale


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["google", "apple", "dev"])
async def test_sign_in_starts_a_new_account_in_the_page_language(
    db_session: AsyncSession, fake_redis: Redis, provider: str
) -> None:
    auth = await _sign_in(provider, db_session, fake_redis, str(uuid4()), locale="fr")

    assert await _stored_locale(db_session, auth.user.id) == "fr"
    # The reply carries it, so the phone stays in French after signing in.
    assert auth.user.locale == "fr"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["google", "apple", "dev"])
async def test_sign_in_keeps_an_existing_account_language(
    db_session: AsyncSession, fake_redis: Redis, provider: str
) -> None:
    sub = str(uuid4())
    email = f"{sub}@icloud.com"
    ids = {
        "google": {"google_sub": sub},
        "apple": {"apple_sub": sub},
        "dev": {"google_sub": f"dev:{email}"},
    }[provider]
    user = await users.create(
        db_session,
        email=email,
        name="Ada",
        avatar_url=None,
        google_sub=ids.get("google_sub"),
        apple_sub=ids.get("apple_sub"),
    )

    auth = await _sign_in(provider, db_session, fake_redis, sub, locale="es")

    assert auth.user.id == user.id
    assert await _stored_locale(db_session, user.id) == "en"


@pytest.mark.asyncio
async def test_sign_in_without_a_language_starts_in_english(
    db_session: AsyncSession, fake_redis: Redis
) -> None:
    auth = await _sign_in("dev", db_session, fake_redis, str(uuid4()), locale=None)

    assert await _stored_locale(db_session, auth.user.id) == "en"


@pytest.mark.parametrize(
    ("sent", "kept"),
    [("fr", "fr"), ("pt-BR", "pt"), (" ES ", "es"), ("de", None), ("", None), (None, None)],
)
def test_sign_in_request_keeps_only_a_supported_language(
    sent: str | None, kept: str | None
) -> None:
    assert GoogleAuthRequest(id_token="tok", locale=sent).locale == kept


@pytest.mark.parametrize("sent", ["fr", "pt-BR", " ES ", "  hi  "])
def test_sign_in_and_a_profile_save_read_a_language_alike(sent: str) -> None:
    """One rule (``supported_locale_code``): " ES " is Spanish on sign-in and on PATCH."""
    signed_in = GoogleAuthRequest(id_token="tok", locale=sent).locale
    saved = UserUpdate(locale=sent).locale
    assert saved is not None
    assert saved == signed_in


@pytest.mark.parametrize("sent", ["de", "klingon"])
def test_a_language_recall_lacks_is_dropped_on_sign_in_and_refused_on_save(sent: str) -> None:
    assert GoogleAuthRequest(id_token="tok", locale=sent).locale is None
    with pytest.raises(ValidationError):
        UserUpdate(locale=sent)
