import asyncio
import ipaddress
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

_OG_TAG_RE = re.compile(
    r'<meta\s+(?:[^>]*?\s)?(?:property|name)=["\'](og:[^"\']+|description|twitter:title)["\'](?:\s[^>]*)?\scontent=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)

_PRIVATE_IP_ERR = "Blocked request to internal/private address"


async def _validate_external_url(url: str) -> None:
    """Resolve URL hostname and validate all resulting IPs are external.

    Raises ValueError if the hostname resolves to any private, loopback,
    link-local, or unspecified address.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("URL has no hostname")

    # Non-blocking DNS resolution via asyncio's thread-pool executor
    loop = asyncio.get_event_loop()
    try:
        infos = await loop.getaddrinfo(hostname, None)
    except OSError as exc:
        raise ValueError(f"Cannot resolve hostname: {hostname}") from exc

    for _family, _type, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_unspecified:
            raise ValueError(_PRIVATE_IP_ERR)


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


async def fetch_link_preview(url: str) -> dict[str, str | None]:
    parsed = urlparse(url)
    domain = parsed.netloc or url
    title: str | None = None
    description: str | None = None

    try:
        await _validate_external_url(url)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(6.0),
            follow_redirects=False,
            headers={"User-Agent": "RecallLinkPreview/1.0"},
        ) as client:
            resp = await client.get(url)
            # Manual redirect handling with per-hop validation
            max_hops = 5
            hops = 0
            while resp.status_code in (301, 302, 303, 307, 308) and hops < max_hops:
                redirect_target = resp.headers.get("Location")
                if not redirect_target:
                    break
                redirect_target = urljoin(url, redirect_target)
                await _validate_external_url(redirect_target)
                resp = await client.get(redirect_target)
                hops += 1
            resp.raise_for_status()
            html = resp.text[:120_000]
    except ValueError:
        # Re-raised from _validate_external_url — blocked internal address
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
