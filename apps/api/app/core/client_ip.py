"""Resolve client IP for rate limiting — only trust forwarded headers behind a known proxy."""

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


def _client_from_x_forwarded_for(forwarded: str, settings: Settings) -> str | None:
    """Pick the rightmost hop that is not a trusted proxy.

    Clients can prepend spoofed addresses to X-Forwarded-For; proxies append.
    Walking from the right and skipping trusted proxies yields the connecting
    client as seen by the outermost trusted hop — not the leftmost spoof.
    """
    hops: list[str] = []
    for part in forwarded.split(","):
        parsed = _parse_ip(part)
        if parsed is not None:
            hops.append(parsed)
    for hop in reversed(hops):
        if not _is_trusted_proxy(hop, settings):
            return hop
    return None


def client_ip(request: Request, settings: Settings) -> str:
    host = request.client.host if request.client else "unknown"
    if not settings.trust_x_forwarded_for:
        return host
    if not _is_trusted_proxy(host, settings):
        return host

    # Fly sets this to the edge-seen client IP; prefer it over XFF when present.
    fly_ip = _parse_ip(request.headers.get("fly-client-ip", ""))
    if fly_ip is not None:
        return fly_ip

    forwarded = request.headers.get("x-forwarded-for", "")
    from_xff = _client_from_x_forwarded_for(forwarded, settings) if forwarded.strip() else None
    return from_xff or host
