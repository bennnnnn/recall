from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_redis, get_settings_dep
from app.core.rate_limit import allow_request
from app.gateways.google_auth import GoogleAuthError
from app.models.orm import User
from app.models.schemas import AuthResponse, DevAuthRequest, GoogleAuthRequest, UserOut, UserUpdate
from app.repositories import users as users_repo
from app.services import auth as auth_service
from app.services import export_service
from app.services import memory as memory_service
from app.services import plan as plan_service
from app.services import subscription as subscription_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    # Trust X-Forwarded-For when present (deploy behind a proxy that sets it).
    # Take the first hop; fall back to the direct connection.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/google", response_model=AuthResponse)
async def google_login(
    body: GoogleAuthRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> AuthResponse:
    # Per-IP, not global: a global bucket lets a credential-stuffer trip the
    # limit and lock real users out of signing in.
    allowed = await allow_request(
        redis,
        f"rate:auth:google:{_client_ip(request)}",
        limit=30,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again shortly.",
        )
    try:
        return await auth_service.login_with_google(session, settings, body.id_token, redis)
    except GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/dev", response_model=AuthResponse)
async def dev_login(
    body: DevAuthRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> AuthResponse:
    if not settings.dev_auth_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev auth disabled")
    try:
        return await auth_service.login_dev(
            session,
            settings,
            email=body.email,
            name=body.name,
            redis=redis,
        )
    except GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> UserOut:
    fields = body.model_dump(exclude_unset=True)
    if "enabled_models" in fields:
        try:
            fields["enabled_models"] = plan_service.validate_enabled_models_for_update(
                user,
                fields["enabled_models"],
                settings,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    memory_toggled = (
        "memory_enabled" in fields
        and fields["memory_enabled"] != user.memory_enabled
    )
    updated = await users_repo.update(
        session,
        user,
        **fields,
    )
    if memory_toggled:
        await memory_service.invalidate_memory_block(user.id)
    return UserOut.model_validate(updated)


@router.post("/me/pro-dev", response_model=UserOut)
async def dev_upgrade_pro(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> UserOut:
    """Dev-only helper to simulate a Pro subscription."""
    if not settings.dev_auth_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev upgrade disabled")
    updated = await users_repo.update(session, user, plan="pro")
    return UserOut.model_validate(updated)


@router.post("/me/sync-subscription", response_model=UserOut)
async def sync_subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> UserOut:
    """Refresh plan from RevenueCat after a purchase or restore."""
    if not settings.revenuecat_secret_key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Subscriptions are not configured on this server",
        )
    updated = await subscription_service.sync_user_plan_from_revenuecat(session, user, settings)
    return UserOut.model_validate(updated)


@router.get("/me/export")
async def export_me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await export_service.build_export(session, user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    await users_repo.delete_user(session, user.id)
