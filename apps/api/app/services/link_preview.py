import asyncio
import hashlib
import ipaddress
import json
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from app.core.config import Settings
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

_OG_TAG_RE = re.compile(
    r'<meta\s+(?:[^>]*?\s)?(?:property|name)=["\'](og:[^"\']+|description|twitter:title)["\'](?:\s[^>]*)?\scontent=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)

_PRIVATE_IP_ERR = "Blocked request to internal/private address"
_USER_AGENT = "RecallLinkPreview/1.0"


def _is_blocked_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_unspecified
        or addr.is_multicast
        or addr.is_reserved
    )


def _format_netloc(ip: str, port: int | None) -> str:
    host = f"[{ip}]" if ":" in ip else ip
    if port is not None:
        return f"{host}:{port}"
    return host


def _host_header(hostname: str, port: int | None, scheme: str) -> str:
    if port is None or (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        return hostname
    return f"{hostname}:{port}"


def _pin_url(url: str, ip: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(netloc=_format_netloc(ip, parsed.port)))


async def _resolve_external_host(url: str) -> tuple[str, str]:
    """Resolve URL hostname once and return (hostname, pinned public IP).

    Raises ValueError if the hostname is missing, unresolvable, or resolves to
    any private/loopback/link-local/reserved address. Callers must connect to
    the returned IP (not re-resolve) to close the DNS-rebinding TOCTOU window.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Unsupported URL scheme")
    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("URL has no hostname")

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        if _is_blocked_ip(literal):
            raise ValueError(_PRIVATE_IP_ERR)
        return hostname, str(literal)

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, None)
    except OSError as exc:
        raise ValueError(f"Cannot resolve hostname: {hostname}") from exc

    public_ips: list[str] = []
    for _family, _type, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(addr):
            raise ValueError(_PRIVATE_IP_ERR)
        if ip_str not in public_ips:
            public_ips.append(ip_str)

    if not public_ips:
        raise ValueError(f"Cannot resolve hostname: {hostname}")
    return hostname, public_ips[0]


async def _validate_external_url(url: str) -> None:
    """Resolve URL hostname and validate all resulting IPs are external."""
    await _resolve_external_host(url)


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "meta":
            data = {k.lower(): (v or "") for k, v in attrs}
            key = data.get("property") or data.get("name")
            content = data.get("content")
            if key and content:
                self.meta[key.lower()] = content


async def _get_pinned(
    client: httpx.AsyncClient,
    url: str,
) -> httpx.Response:
    """GET *url* via a DNS-pinned IP so resolution cannot change mid-request."""
    parsed = urlparse(url)
    hostname, ip = await _resolve_external_host(url)
    pinned = _pin_url(url, ip)
    headers = {
        "User-Agent": _USER_AGENT,
        "Host": _host_header(hostname, parsed.port, parsed.scheme),
    }
    extensions: dict[str, str] = {}
    if parsed.scheme == "https":
        extensions["sni_hostname"] = hostname
    return await client.get(pinned, headers=headers, extensions=extensions or None)


async def fetch_link_preview(url: str) -> dict[str, str | None]:
    parsed = urlparse(url)
    domain = parsed.netloc or url
    title: str | None = None
    description: str | None = None

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(6.0),
            follow_redirects=False,
        ) as client:
            resp = await _get_pinned(client, url)
            # Manual redirect handling with per-hop resolve+pin
            max_hops = 5
            hops = 0
            current_url = url
            while resp.status_code in (301, 302, 303, 307, 308) and hops < max_hops:
                redirect_target = resp.headers.get("Location")
                if not redirect_target:
                    break
                current_url = urljoin(current_url, redirect_target)
                resp = await _get_pinned(client, current_url)
                hops += 1
            resp.raise_for_status()
            html = resp.text[:120_000]
    except ValueError:
        # Re-raised from _resolve_external_host — blocked internal address
        logger.debug("Link preview blocked internal address: %s", url)
        return {"url": url, "title": None, "description": None, "domain": domain}
    except Exception:
        logger.debug("Link preview fetch failed for %s", url, exc_info=True)
        return {"url": url, "title": None, "description": None, "domain": domain}

    parser = _MetaParser()
    try:
        parser.feed(html)
    except Exception:
        logger.debug("Meta parse failed", exc_info=True)

    title = parser.meta.get("og:title") or parser.meta.get("twitter:title") or parser.title
    description = parser.meta.get("og:description") or parser.meta.get("description")

    if not title:
        m = _TITLE_RE.search(html)
        if m:
            title = m.group(1).strip()

    if not title and not description:
        for match in _OG_TAG_RE.finditer(html):
            key, value = match.group(1).lower(), match.group(2).strip()
            if key in {"og:title", "twitter:title"} and not title:
                title = value
            if key in {"og:description", "description"} and not description:
                description = value

    return {
        "url": url,
        "title": title,
        "description": description,
        "domain": domain,
    }


def _preview_cache_key(url: str) -> str:
    digest = hashlib.sha256(url.strip().lower().encode()).hexdigest()[:32]
    return f"linkpreview:{digest}"


async def fetch_link_preview_cached(settings: Settings, url: str) -> dict[str, str | None]:
    cache_key = _preview_cache_key(url)
    redis = get_redis_client()
    try:
        cached = await redis.get(cache_key)
        if cached:
            payload = json.loads(cached)
            if isinstance(payload, dict):
                return {
                    "url": str(payload.get("url") or url),
                    "title": payload.get("title"),
                    "description": payload.get("description"),
                    "domain": str(payload.get("domain") or urlparse(url).netloc or url),
                }
    except Exception:
        logger.debug("Link preview cache read failed", exc_info=True)

    result = await fetch_link_preview(url)
    try:
        await redis.set(
            cache_key,
            json.dumps(result),
            ex=max(60, settings.link_preview_cache_ttl),
        )
    except Exception:
        logger.debug("Link preview cache write failed", exc_info=True)
    return result
