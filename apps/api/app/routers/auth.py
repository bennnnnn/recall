from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
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
)
from app.core.dev_guards import is_loopback_ip, require_dev_privilege_access
from app.core.rate_limit import allow_request_fail_closed
from app.exceptions import RedisUnavailableError
from app.models.orm import User
from app.models.schemas import (
    AppleAuthRequest,
    AuthResponse,
    DevAuthRequest,
    GoogleAuthRequest,
    LogoutRequest,
    RefreshRequest,
    SettingsConfirmOut,
    UserOut,
    UserUpdate,
)
from app.services import account_lifecycle, export_service, web_session
from app.services import auth as auth_service
from app.services import settings_proposal as settings_proposal_service
from app.services import subscription as subscription_service
from app.services import tokens as tokens_service

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
) -> JSONResponse:
    await _enforce_login_rate_limit(redis, request, settings, provider="google")
    try:
        auth = await auth_service.login_with_google(session, settings, body.id_token, redis)
    except auth_service.GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return web_session.auth_json_response(request, settings, auth)


@router.post("/apple", response_model=AuthResponse)
async def apple_login(
    body: AppleAuthRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> JSONResponse:
    await _enforce_login_rate_limit(redis, request, settings, provider="apple")
    try:
        auth = await auth_service.login_with_apple(
            session,
            settings,
            body.id_token,
            redis,
            name=body.name,
        )
    except auth_service.GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return web_session.auth_json_response(request, settings, auth)


@router.post("/dev", response_model=AuthResponse)
async def dev_login(
    body: DevAuthRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> JSONResponse:
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
        auth = await auth_service.login_dev(
            session,
            settings,
            email=body.email,
            name=body.name,
            redis=redis,
        )
    except auth_service.GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return web_session.auth_json_response(request, settings, auth)


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
) -> JSONResponse:
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
    cookie_refresh = web_session.cookie_value(request, web_session.REFRESH_COOKIE)
    presented = (body.refresh_token or "").strip() or cookie_refresh
    if not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )
    if cookie_refresh and not (body.refresh_token or "").strip():
        if not web_session.is_web_origin(request, settings):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing refresh token",
            )
        web_session.require_web_csrf(request)
    try:
        access_token, refresh_token, user = await tokens_service.refresh_token_pair(
            redis, presented, session, settings
        )
    except RedisUnavailableError as exc:
        raise redis_unavailable_http_exception(exc) from exc
    except auth_service.GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return web_session.auth_json_response(
        request,
        settings,
        AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user,
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis),
) -> Response:
    cookie_refresh = web_session.cookie_value(request, web_session.REFRESH_COOKIE)
    refresh_token = body.refresh_token or cookie_refresh
    if cookie_refresh and not body.refresh_token:
        if not web_session.is_web_origin(request, settings):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing refresh token",
            )
        web_session.require_web_csrf(request)
    auth_header = request.headers.get("authorization", "")
    access_token: str | None = None
    if auth_header.lower().startswith("bearer "):
        access_token = auth_header[7:]
    try:
        await account_lifecycle.logout(
            redis,
            settings,
            access_token=access_token,
            refresh_token=refresh_token,
        )
    except RedisUnavailableError as exc:
        raise redis_unavailable_http_exception(exc) from exc
    except auth_service.GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    if web_session.is_web_origin(request, settings):
        web_session.clear_web_session_cookies(response, settings)
    return response


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> UserOut:
    fields = body.model_dump(exclude_unset=True)
    try:
        updated = await account_lifecycle.update_account(session, user, settings, fields)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserOut.model_validate(updated)


@router.post("/me/settings-proposals/{proposal_id}/confirm", response_model=SettingsConfirmOut)
async def confirm_settings_proposal(
    proposal_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> SettingsConfirmOut:
    try:
        result = await settings_proposal_service.confirm_proposal(
            session, redis, user, settings, proposal_id
        )
    except settings_proposal_service.SettingsProposalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return SettingsConfirmOut(
        user=UserOut.model_validate(result["user"]),
        appearance=result.get("appearance"),
        applied=result["applied"],
    )


@router.post("/me/pro-dev", response_model=UserOut)
async def dev_upgrade_pro(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> UserOut:
    """Dev-only helper to simulate a Pro subscription."""
    require_dev_privilege_access(request, settings, user)
    updated = await account_lifecycle.upgrade_to_pro_for_dev(session, user)
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
    try:
        await account_lifecycle.delete_account(session, redis, settings, user)
    except account_lifecycle.SessionPurgeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not revoke sessions. Please retry.",
        ) from exc
