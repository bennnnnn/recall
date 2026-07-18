"""Global REST rate limiting (Redis sliding window via INCR+EXPIRE)."""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.access_tokens import AccessTokenError, decode_access_token
from app.core.client_ip import client_ip
from app.core.config import Settings, get_settings
from app.core.rate_limit import allow_request
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

_SKIP_PREFIXES = ("/health", "/webhooks/", "/legal/")


def _client_key(request: Request, settings: Settings) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        try:
            user_id = decode_access_token(token, settings)
            return f"user:{user_id}"
        except AccessTokenError:
            pass
    return f"ip:{client_ip(request, settings)}"


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
            # Fail closed: a Redis outage must not let the rate limiter
            # silently disappear — that would expose every protected
            # endpoint to unbounded traffic during the outage. Returning
            # 429 (with a Retry-After) is the safe default; clients retry
            # with backoff and the limit re-engages the moment Redis is back.
            logger.warning("REST rate limit check failed; failing closed", exc_info=True)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit unavailable. Please retry shortly."},
                headers={"Retry-After": "5"},
            )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
            )
        return await call_next(request)
