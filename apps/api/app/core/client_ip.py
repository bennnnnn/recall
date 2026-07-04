"""Resolve client IP for rate limiting — only trust X-Forwarded-For behind a known proxy."""

from __future__ import annotations

from starlette.requests import Request

from app.core.config import Settings


def client_ip(request: Request, settings: Settings) -> str:
    host = request.client.host if request.client else "unknown"
    if not settings.trust_x_forwarded_for:
        return host
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or host
