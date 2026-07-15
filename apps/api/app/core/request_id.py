"""Attach a request ID to every HTTP response for log correlation.

The client may supply an ``X-Request-ID`` header; we accept it only if it
matches a strict allowlist regex (``^[A-Za-z0-9_-]{1,64}$``) so a malicious
or malformed value cannot pollute logs (CRLF injection, log injection via
long values, etc.). Otherwise we generate a fresh UUID4.

The chosen ID is exposed to handlers via ``request.state.request_id`` and to
loggers via the ``request_id_context`` contextvar, which the logging
formatter picks up automatically.
"""

from __future__ import annotations

import contextvars
import logging
import re
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

# Strict allowlist for client-supplied request IDs: alphanumerics, underscore,
# hyphen, 1-64 chars. Anything else (spaces, control chars, newlines, very
# long values) is rejected and a fresh UUID is generated instead -- this
# prevents log injection and keeps log lines readable.
_CLIENT_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

#: Contextvar holding the current request ID, set by RequestIdMiddleware and
#: read by the logging formatter/filter so every log line for a request is
#: correlated without threading the ID through every call.
request_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id_context", default=None
)


def _normalize_request_id(raw: str | None) -> str:
    """Return a valid request ID, generating one if *raw* is missing/invalid."""
    if raw and _CLIENT_REQUEST_ID_RE.fullmatch(raw):
        return raw
    return str(uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_context.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
