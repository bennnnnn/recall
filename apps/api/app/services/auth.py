from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways.google_auth import GoogleAuthError, create_access_token, verify_google_id_token
from app.models.orm import User
from app.models.schemas import AuthResponse, UserOut
from app.repositories import users as users_repo


async def login_with_google(
    session: AsyncSession,
    settings: Settings,
    id_token: str,
) -> AuthResponse:
    payload = verify_google_id_token(id_token, settings)
    google_sub = payload["sub"]
    email = payload.get("email", "")
    name = payload.get("name")
    avatar_url = payload.get("picture")

    user = await users_repo.get_by_google_sub(session, google_sub)
    if user is None:
        user = await users_repo.create(
            session,
            google_sub=google_sub,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )

    token = create_access_token(user.id, settings)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


async def login_dev(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    name: str,
) -> AuthResponse:
    if not settings.dev_auth_enabled:
        raise GoogleAuthError("Dev auth is disabled")

    google_sub = f"dev:{email}"
    user = await users_repo.get_by_google_sub(session, google_sub)
    if user is None:
        user = await users_repo.create(
            session,
            google_sub=google_sub,
            email=email,
            name=name,
            avatar_url=None,
        )

    token = create_access_token(user.id, settings)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


async def get_current_user(session: AsyncSession, user_id: UUID) -> User | None:
    return await users_repo.get_by_id(session, user_id)
