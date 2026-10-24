from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.validation import claim_is_true, normalize_display_name
from app.exceptions import AuthenticationError
from app.gateways.apple_auth import verify_apple_id_token

# Re-exported for the account API (maps it to 503, not 401).
from app.gateways.google_auth import (
    GoogleAuthUnavailableError as GoogleAuthUnavailableError,
)
from app.gateways.google_auth import verify_google_id_token
from app.models.orm import User
from app.models.schemas import AuthResponse, UserOut
from app.modules.account import quota_carryover
from app.modules.account import tokens as tokens_service

# Re-exported for the account API (maps it to 409 naming the earlier sign-in).
from app.modules.account.email_authority import AccountExistsError as AccountExistsError
from app.modules.account.email_authority import (
    apple_owns_email,
    google_owns_email,
    previous_sign_in,
)
from app.modules.notifications import enqueue_welcome_email
from app.repositories import users as users_repo


async def _signed_in(
    redis: Redis,
    settings: Settings,
    user: User,
    *,
    is_new_user: bool,
    device_label: str | None,
    platform: str | None,
) -> AuthResponse:
    """Finish any sign-in: welcome a new account, then issue its token pair."""
    if is_new_user and settings.email_enabled:
        # Best-effort: never let a welcome email block signup.
        await enqueue_welcome_email(redis, user.id)

    access_token, refresh_token = await tokens_service.issue_token_pair(
        redis,
        user.id,
        settings,
        device_label=device_label,
        platform=platform,
    )
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


async def login_with_google(
    session: AsyncSession,
    settings: Settings,
    id_token: str,
    redis: Redis,
    *,
    device_label: str | None = None,
    platform: str | None = None,
) -> AuthResponse:
    payload = await verify_google_id_token(id_token, settings)
    google_sub = payload["sub"]
    email = (payload.get("email") or "").strip()
    name = payload.get("name")
    avatar_url = payload.get("picture")

    user = await users_repo.get_by_google_sub(session, google_sub)
    is_new_user = user is None
    # No account has this Google id. One that holds the email (e.g. made with
    # Apple) gains this Google login only when Google owns the address; email
    # is unique, so otherwise the user signs in the way they did before.
    if user is None and email:
        existing = await users_repo.get_by_email(session, email)
        if existing is not None:
            if existing.google_sub or not google_owns_email(payload, email):
                raise AccountExistsError(previous_sign_in(existing, "google"))
            user = await users_repo.update(session, existing, google_sub=google_sub)
            is_new_user = False

    if user is None:
        if not email:
            raise AuthenticationError(
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
        await quota_carryover.restore_for_new_account(
            redis, settings, user.id, provider="google", sub=google_sub
        )
    else:
        # Decide against the current locked row: a profile save may have
        # finished after the identity lookup above. This flow locks no photos.
        await users_repo.refresh_for_update(session, user)
        # A selected profile photo belongs to Recall; subsequent Google login
        # may refresh a provider picture but must not replace a custom upload.
        current_avatar = user.avatar_url
        if isinstance(current_avatar, str) and current_avatar.startswith("/attachments/"):
            avatar_url = current_avatar
        user = await users_repo.update(
            session,
            user,
            email=email or user.email,
            name=user.name if isinstance(user.name, str) and user.name.strip() else name,
            avatar_url=avatar_url or user.avatar_url,
        )

    return await _signed_in(
        redis,
        settings,
        user,
        is_new_user=is_new_user,
        device_label=device_label,
        platform=platform,
    )


async def login_with_apple(
    session: AsyncSession,
    settings: Settings,
    id_token: str,
    redis: Redis,
    *,
    name: str | None = None,
    nonce: str | None = None,
    device_label: str | None = None,
    platform: str | None = None,
) -> AuthResponse:
    # L1: validate the client-supplied display name (trim, collapse, length)
    name = normalize_display_name(name)
    payload = await verify_apple_id_token(id_token, settings, nonce=nonce)
    apple_sub = payload["sub"]
    email = payload.get("email")
    # Apple sends `email_verified` as the string "true"/"false" (not a bool),
    # and omits the claim entirely for relayed tokens. Treat anything that
    # isn't an explicit, unambiguous "true" as unverified — the same intent
    # as Google's `not payload.get("email_verified")` but robust to the
    # string form and to a missing claim (which must not silently pass).
    email_verified = payload.get("email_verified")
    if not claim_is_true(email_verified):
        raise AuthenticationError("Apple email address is not verified")

    user = await users_repo.get_by_apple_sub(session, apple_sub)
    is_new_user = user is None
    # As with Google: an account holding the email gains this Apple login only
    # when Apple owns the address (its relay, iCloud, me.com, mac.com).
    if user is None and email:
        existing = await users_repo.get_by_email(session, email)
        if existing is not None:
            if existing.apple_sub or not apple_owns_email(payload, email):
                raise AccountExistsError(previous_sign_in(existing, "apple"))
            user = await users_repo.update(session, existing, apple_sub=apple_sub)
            is_new_user = False

    if user is None:
        if not email:
            raise AuthenticationError(
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
        await quota_carryover.restore_for_new_account(
            redis, settings, user.id, provider="apple", sub=apple_sub
        )
    else:
        if name:
            await users_repo.refresh_for_update(session, user)
        updates: dict[str, str | None] = {}
        if email:
            updates["email"] = email
        if name and not (isinstance(user.name, str) and user.name.strip()):
            updates["name"] = name
        if updates:
            user = await users_repo.update(session, user, commit=True, **updates)

    return await _signed_in(
        redis,
        settings,
        user,
        is_new_user=is_new_user,
        device_label=device_label,
        platform=platform,
    )


async def login_dev(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    name: str,
    redis: Redis,
    device_label: str | None = None,
    platform: str | None = None,
) -> AuthResponse:
    if not settings.dev_auth_enabled:
        raise AuthenticationError("Dev auth is disabled")

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
        await quota_carryover.restore_for_new_account(
            redis, settings, user.id, provider="google", sub=google_sub
        )
    elif name and user.name != name:
        # Keep dev re-login in step with Google/Apple, which refresh the name
        # each time — so renaming the dev identity takes effect for an existing
        # account instead of being stuck at the name it was first created with.
        user = await users_repo.update(session, user, name=name)

    return await _signed_in(
        redis,
        settings,
        user,
        is_new_user=is_new_user,
        device_label=device_label,
        platform=platform,
    )
