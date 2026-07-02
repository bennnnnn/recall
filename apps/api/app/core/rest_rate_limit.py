"""Global REST rate limiting (Redis sliding window via INCR+EXPIRE)."""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings, get_settings
from app.core.rate_limit import allow_request
from app.core.redis import get_redis_client
from app.gateways.google_auth import GoogleAuthError, decode_access_token

logger = logging.getLogger(__name__)

_SKIP_PREFIXES = ("/health", "/webhooks/")


def _client_key(request: Request, settings: Settings) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        try:
            user_id = decode_access_token(token, settings)
            return f"user:{user_id}"
        except GoogleAuthError:
            pass
    host = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or host
    return f"ip:{ip}"


class RestRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if request.method == "OPTIONS" or any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        settings = get_settings()
        limit = settings.rest_rate_limit_per_minute
        if limit <= 0:
            return await call_next(request)

        key = f"rest_rl:{_client_key(request, settings)}"
        try:
            redis = get_redis_client()
            allowed = await allow_request(redis, key, limit=limit, window_seconds=60)
        except Exception:
            logger.debug("REST rate limit check failed; allowing request", exc_info=True)
            return await call_next(request)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
            )
        return await call_next(request)
