"""Global REST rate limiting: a fixed window per caller (Redis INCR + EXPIRE NX).

The window starts at a caller's first request and resets when its key expires, so a
burst that straddles the reset can reach twice the limit in a short span; this is a
coarse flood limit, not a smoothed rate (``core/rate_limit.allow_request``).

A signed-in caller's token is decoded here for its user id, and again by the route's
``get_current_user`` (``access_tokens.check_access``). That second HS256 check costs
microseconds; handing the route a user id this limiter read would give authentication a
second way in, so each decodes its own.
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.access_tokens import AccessTokenError, decode_access_token
from app.core.client_ip import client_ip
from app.core.config import Settings, get_settings
from app.core.domain_errors import domain_error_response
from app.core.rate_limit import allow_request
from app.core.redis import get_redis_client
from app.core.unavailable import unavailable_response
from app.exceptions import RateLimitedError

logger = logging.getLogger(__name__)

# Refresh and Google/Apple sign-in have their own limits, per account or identity and per IP
# (modules/account/refresh_limit.py, signin_limit.py), each IP limit checked before any costly
# work: here, unsigned, every phone behind one carrier NAT address shared one 240-a-minute
# bucket. Dev login stays under this one.
_SKIP_PREFIXES = (
    "/health",
    "/webhooks/",
    "/legal/",
    "/auth/refresh",
    "/auth/google",
    "/auth/apple",
)


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


class RestRateLimitMiddleware:
    """Pure ASGI, so a reply passes straight through: ``BaseHTTPMiddleware`` re-streamed
    every body of every route through a task and a memory stream. Sockets pass untouched."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        refusal = await _refusal(Request(scope)) if scope["type"] == "http" else None
        if refusal is None:
            await self.app(scope, receive, send)
        else:
            await refusal(scope, receive, send)


async def _refusal(request: Request) -> Response | None:
    """The reply that stops this request (over the limit, or the limiter unreadable), or
    None to let it through."""
    path = request.url.path
    if request.method == "OPTIONS" or any(path.startswith(p) for p in _SKIP_PREFIXES):
        return None

    settings = get_settings()
    limit = settings.rest_rate_limit_per_minute
    if limit <= 0:
        return None

    key = f"rest_rl:{_client_key(request, settings)}"
    try:
        redis = get_redis_client()
        allowed = await allow_request(redis, key, limit=limit, window_seconds=60)
    except Exception:
        # Fail closed: a Redis outage must not let the rate limiter
        # silently disappear — that would expose every protected
        # endpoint to unbounded traffic during the outage. It answers what
        # every route answers then: 503 unavailable, Retry-After 5. It was a 429
        # "Rate limit unavailable": every read of the outage looked like the
        # user's own limit, dev login said "too many attempts", and the phone,
        # which checks its connection after a 502/503/504, never did.
        logger.warning("REST rate limit check failed; failing closed", exc_info=True)
        return unavailable_response()

    if not allowed:
        # The shared coded body (``docs/fixtures/error_codes.json``). The English alone
        # named no code: a chat read it as "Couldn't reach the server", dev login as
        # the generic sign-in failure.
        return domain_error_response(
            RateLimitedError("Too many requests. Please slow down.", retry_after_seconds=60)
        )
    return None
