"""Resolve client IP for rate limiting — only trust X-Forwarded-For behind a known proxy."""

from __future__ import annotations

import ipaddress

from starlette.requests import Request

from app.core.config import Settings


def _parse_ip(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def _is_trusted_proxy(host: str, settings: Settings) -> bool:
    parsed = _parse_ip(host)
    if parsed is None:
        return False
    addr = ipaddress.ip_address(parsed)
    for raw in settings.trusted_proxy_cidrs.split(","):
        cidr = raw.strip()
        if not cidr:
            continue
        try:
            if addr in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def client_ip(request: Request, settings: Settings) -> str:
    host = request.client.host if request.client else "unknown"
    if not settings.trust_x_forwarded_for:
        return host
    if not _is_trusted_proxy(host, settings):
        return host
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    parsed = _parse_ip(forwarded) if forwarded else None
    return parsed or host
