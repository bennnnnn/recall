import hashlib
import json
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.gateways.safe_fetch import fetch_safely
from app.gateways.safe_fetch import validate_external_url as _validate_external_url_async

logger = logging.getLogger(__name__)

_OG_TAG_RE = re.compile(
    r'<meta\s+(?:[^>]*?\s)?(?:property|name)=["\'](og:[^"\']+|description|twitter:title)["\'](?:\s[^>]*)?\scontent=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)

_USER_AGENT = "RecallLinkPreview/1.0"
# Cap bytes streamed from the upstream — OG/meta tags live near the top; a
# multi-GB body must not be buffered into API memory (rate limit alone is not
# enough — each request can still be huge within the timeout).
_LINK_PREVIEW_MAX_BODY_BYTES = 128 * 1024
_LINK_PREVIEW_MAX_HTML_CHARS = 120_000


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


async def _validate_external_url(url: str) -> None:
    """Resolve URL hostname and validate all resulting IPs are external."""
    await _validate_external_url_async(url)


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
            # SSRF-safe fetch: DNS pinning + per-hop re-validation of every
            # redirect target. Replaces the hand-rolled _get_pinned + redirect
            # loop, which duplicated fetch_safely's logic and could drift.
            resp = await fetch_safely(
                client,
                url,
                headers={"User-Agent": _USER_AGENT},
                max_body_bytes=_LINK_PREVIEW_MAX_BODY_BYTES,
            )
            resp.raise_for_status()
            html = resp.text[:_LINK_PREVIEW_MAX_HTML_CHARS]
    except ValueError:
        # Re-raised from resolve_external_host -- blocked internal address
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
