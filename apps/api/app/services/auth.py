from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import Settings
from app.gateways.google_auth import GoogleAuthError, create_access_token, verify_google_id_token
from app.models.orm import User
from app.models.schemas import AuthResponse, UserOut
from app.repositories import users as users_repo


async def login_with_google(
    session: AsyncSession,
    settings: Settings,
    id_token: str,
    redis: Redis,
) -> AuthResponse:
    payload = verify_google_id_token(id_token, settings)
    google_sub = payload["sub"]
    email = payload.get("email", "")
    name = payload.get("name")
    avatar_url = payload.get("picture")

    user = await users_repo.get_by_google_sub(session, google_sub)
    is_new_user = user is None
    if user is None:
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

    token = create_access_token(user.id, settings)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


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

    if is_new_user and settings.email_enabled:
        await jobs.enqueue_welcome_email(redis, user.id)

    token = create_access_token(user.id, settings)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


async def get_current_user(session: AsyncSession, user_id: UUID) -> User | None:
    return await users_repo.get_by_id(session, user_id)
