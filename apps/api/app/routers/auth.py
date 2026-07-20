import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client_ip import client_ip
from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import (
    get_current_user,
    get_redis,
    get_settings_dep,
    redis_unavailable_http_exception,
    security,
)
from app.core.dev_guards import is_loopback_ip, require_dev_privilege_access
from app.core.rate_limit import allow_request_fail_closed
from app.exceptions import RedisUnavailableError
from app.gateways.google_auth import GoogleAuthError
from app.models.orm import User
from app.models.schemas import (
    AppleAuthRequest,
    AuthResponse,
    DevAuthRequest,
    GoogleAuthRequest,
    LogoutRequest,
    RefreshRequest,
    UserOut,
    UserUpdate,
)
from app.repositories import users as users_repo
from app.services import attachment_lifecycle, export_service
from app.services import auth as auth_service
from app.services import google_integrations as google_integrations_service
from app.services import home as home_service
from app.services import memory as memory_service
from app.services import plan as plan_service
from app.services import subscription as subscription_service
from app.services import tokens as tokens_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_RATE_LIMIT = 30
_LOGIN_RATE_WINDOW_SECONDS = 60
# Refresh tokens can be leaked; cap online guessing volume per IP. Separate
# bucket from login so a burst of refreshes can't lock out fresh logins.
_REFRESH_RATE_LIMIT = 60
_REFRESH_RATE_WINDOW_SECONDS = 60


async def _enforce_login_rate_limit(
    redis: Redis,
    request: Request,
    settings: Settings,
    *,
    provider: str,
) -> None:
    """Per-provider login throttle; raises 429 when the bucket is exhausted.

    Per-IP, not global: a global bucket lets a credential-stuffer trip the
    limit and lock real users out of signing in. Redis errors fail closed
    (deny) so an outage cannot remove the throttle.
    """
    allowed = await allow_request_fail_closed(
        redis,
        f"rate:auth:{provider}:{client_ip(request, settings)}",
        limit=_LOGIN_RATE_LIMIT,
        window_seconds=_LOGIN_RATE_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again shortly.",
            headers={"Retry-After": str(_LOGIN_RATE_WINDOW_SECONDS)},
        )


@router.post("/google", response_model=AuthResponse)
async def google_login(
    body: GoogleAuthRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> AuthResponse:
    await _enforce_login_rate_limit(redis, request, settings, provider="google")
    try:
        return await auth_service.login_with_google(session, settings, body.id_token, redis)
    except GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/apple", response_model=AuthResponse)
async def apple_login(
    body: AppleAuthRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> AuthResponse:
    await _enforce_login_rate_limit(redis, request, settings, provider="apple")
    try:
        return await auth_service.login_with_apple(
            session,
            settings,
            body.id_token,
            redis,
            name=body.name,
        )
    except GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/dev", response_model=AuthResponse)
async def dev_login(
    body: DevAuthRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> AuthResponse:
    if not settings.dev_auth_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev auth disabled")
    # Dev auth bypasses provider token verification, so without a limit a
    # single client can mint arbitrary accounts or credential-stuff when dev
    # auth is on.
    await _enforce_login_rate_limit(redis, request, settings, provider="dev")
    # Fail-closed against a dev config accidentally exposed on a public host:
    # refuse non-loopback callers unless the operator explicitly opted in with
    # DEV_AUTH_ALLOW_REMOTE. Use the raw TCP peer — not client_ip() — so a
    # spoofed Fly-Client-IP / X-Forwarded-For of 127.0.0.1 cannot bypass the
    # guard behind a pass-through proxy.
    peer = request.client.host if request.client is not None else ""
    if not settings.dev_auth_allow_remote and not is_loopback_ip(peer):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
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


@router.post("/refresh", response_model=AuthResponse)
async def refresh_session(
    body: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> AuthResponse:
    # Rate-limit refresh: a leaked refresh token shouldn't be hammerable
    # online. Reuse the login throttle pattern with its own per-IP bucket.
    allowed = await allow_request_fail_closed(
        redis,
        f"rate:auth:refresh:{client_ip(request, settings)}",
        limit=_REFRESH_RATE_LIMIT,
        window_seconds=_REFRESH_RATE_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many refresh attempts. Try again shortly.",
            headers={"Retry-After": str(_REFRESH_RATE_WINDOW_SECONDS)},
        )
    try:
        access_token, refresh_token, user = await tokens_service.refresh_token_pair(
            redis, body.refresh_token, session, settings
        )
    except RedisUnavailableError as exc:
        raise redis_unavailable_http_exception(exc) from exc
    except GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> None:
    try:
        if body.refresh_token:
            await tokens_service.revoke_access_token(redis, credentials.credentials, settings)
            await tokens_service.revoke_refresh_token(redis, body.refresh_token)
        else:
            # Client lost refresh — resolve user before revoke, then kill all sessions.
            user_id = await tokens_service.verify_access_token(
                redis, credentials.credentials, settings
            )
            await tokens_service.revoke_access_token(redis, credentials.credentials, settings)
            await tokens_service.purge_user_sessions(redis, user_id, settings)
    except RedisUnavailableError as exc:
        raise redis_unavailable_http_exception(exc) from exc
    except GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


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
    memory_toggled = "memory_enabled" in fields and fields["memory_enabled"] != user.memory_enabled
    updated = await users_repo.update(
        session,
        user,
        **fields,
    )
    if memory_toggled:
        await memory_service.invalidate_memory_block(user.id)
    await home_service.invalidate_home_cache(user.id)
    return UserOut.model_validate(updated)


@router.post("/me/pro-dev", response_model=UserOut)
async def dev_upgrade_pro(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> UserOut:
    """Dev-only helper to simulate a Pro subscription."""
    require_dev_privilege_access(request, settings, user)
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
) -> StreamingResponse:
    return StreamingResponse(
        export_service.iter_export_json(user),
        media_type="application/json",
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> None:
    # Kill every outstanding session before the row goes — otherwise a
    # logged-in client keeps a working access token until its own exp, with
    # only the (now-deleted) DB user check to stop it.
    await tokens_service.purge_user_sessions(redis, user.id, settings)
    try:
        await google_integrations_service.revoke_all_google_tokens_for_user(
            session,
            settings,
            user.id,
        )
    except google_integrations_service.GoogleConnectError:
        # Decrypt/key-rotation failures must not block account deletion after
        # sessions are already purged — sibling disconnect endpoints return
        # 400; here we best-effort revoke and continue wiping the account.
        logger.warning(
            "Google token revoke failed during account delete; continuing wipe user_id=%s",
            user.id,
            exc_info=True,
        )
    # Storage bytes before DB rows — delete_user only clears attachment rows.
    await attachment_lifecycle.purge_attachments_for_user(session, settings, user.id)
    await users_repo.delete_user(session, user.id)
