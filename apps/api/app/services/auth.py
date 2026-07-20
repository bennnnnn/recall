from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import Settings
from app.gateways.apple_auth import verify_apple_id_token
from app.gateways.google_auth import GoogleAuthError, verify_google_id_token
from app.models.orm import User
from app.models.schemas import AuthResponse, UserOut
from app.repositories import users as users_repo
from app.services import tokens as tokens_service


def _is_verified_truthy(value: object) -> bool:
    """True only for an explicit, unambiguous "verified" claim.

    Apple ships `email_verified` as the string "true"/"false"; Google ships a
    bool. A missing claim or any non-affirmative value (incl. the string
    "false", 0, None) is treated as unverified.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


async def login_with_google(
    session: AsyncSession,
    settings: Settings,
    id_token: str,
    redis: Redis,
) -> AuthResponse:
    payload = await verify_google_id_token(id_token, settings)
    google_sub = payload["sub"]
    email = (payload.get("email") or "").strip()
    name = payload.get("name")
    avatar_url = payload.get("picture")

    user = await users_repo.get_by_google_sub(session, google_sub)
    is_new_user = user is None
    # Mirror Apple sign-in: if no google_sub match but a user with this email
    # already exists (e.g. created via Apple), link the accounts instead of
    # creating a duplicate row — which would hit the unique(email) constraint
    # and surface as an unhandled 500 IntegrityError.
    if user is None and email:
        existing = await users_repo.get_by_email(session, email)
        if existing is not None:
            user = await users_repo.update(session, existing, google_sub=google_sub)
            is_new_user = False

    if user is None:
        if not email:
            raise GoogleAuthError(
                "Google did not share an email. Check that the Google account "
                "has a verified email, or use Apple Sign-In."
            )
        user = await users_repo.create(
            session,
            google_sub=google_sub,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )
    else:
        user = await users_repo.update(
            session,
            user,
            email=email or user.email,
            name=name or user.name,
            avatar_url=avatar_url or user.avatar_url,
        )

    if is_new_user and settings.email_enabled:
        # Best-effort: never let a welcome email block signup.
        await jobs.enqueue_welcome_email(redis, user.id)

    access_token, refresh_token = await tokens_service.issue_token_pair(redis, user.id, settings)
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


async def login_with_apple(
    session: AsyncSession,
    settings: Settings,
    id_token: str,
    redis: Redis,
    *,
    name: str | None = None,
) -> AuthResponse:
    payload = await verify_apple_id_token(id_token, settings)
    apple_sub = payload["sub"]
    email = payload.get("email")
    # Apple sends `email_verified` as the string "true"/"false" (not a bool),
    # and omits the claim entirely for relayed tokens. Treat anything that
    # isn't an explicit, unambiguous "true" as unverified — the same intent
    # as Google's `not payload.get("email_verified")` but robust to the
    # string form and to a missing claim (which must not silently pass).
    email_verified = payload.get("email_verified")
    if not _is_verified_truthy(email_verified):
        raise GoogleAuthError("Apple email address is not verified")

    user = await users_repo.get_by_apple_sub(session, apple_sub)
    is_new_user = user is None
    if user is None and email:
        existing = await users_repo.get_by_email(session, email)
        if existing is not None:
            user = await users_repo.update(session, existing, apple_sub=apple_sub)
            is_new_user = False

    if user is None:
        if not email:
            raise GoogleAuthError(
                "Apple did not share an email. Revoke Recall in Apple ID settings "
                "and sign in again, or use Google Sign-In."
            )
        user = await users_repo.create(
            session,
            apple_sub=apple_sub,
            email=email,
            name=name,
            avatar_url=None,
        )
    else:
        updates: dict[str, str | None] = {}
        if email:
            updates["email"] = email
        if name:
            updates["name"] = name
        if updates:
            user = await users_repo.update(session, user, **updates)

    if is_new_user and settings.email_enabled:
        await jobs.enqueue_welcome_email(redis, user.id)

    access_token, refresh_token = await tokens_service.issue_token_pair(redis, user.id, settings)
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


async def login_dev(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    name: str,
    redis: Redis,
) -> AuthResponse:
    if not settings.dev_auth_enabled:
        raise GoogleAuthError("Dev auth is disabled")

    google_sub = f"dev:{email}"
    user = await users_repo.get_by_google_sub(session, google_sub)
    is_new_user = user is None
    if user is None:
        user = await users_repo.create(
            session,
            google_sub=google_sub,
            email=email,
            name=name,
            avatar_url=None,
        )
    elif name and user.name != name:
        # Keep dev re-login in step with Google/Apple, which refresh the name
        # each time — so renaming the dev identity takes effect for an existing
        # account instead of being stuck at the name it was first created with.
        user = await users_repo.update(session, user, name=name)

    if is_new_user and settings.email_enabled:
        await jobs.enqueue_welcome_email(redis, user.id)

    access_token, refresh_token = await tokens_service.issue_token_pair(redis, user.id, settings)
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


async def get_current_user(session: AsyncSession, user_id: UUID) -> User | None:
    return await users_repo.get_by_id(session, user_id)
