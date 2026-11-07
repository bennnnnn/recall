"""Build Tavily/DuckDuckGo queries from user text."""

from __future__ import annotations

import re
from datetime import datetime

from app.gateways.web_search_gateway import WebSearchHit
from app.modules.web_search.patterns import (
    _NEWS,
)
from app.services import time_context as time_context_service


def _today_label(user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    return datetime.now(tz).strftime("%B %d %Y")


def _today_iso(user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    return datetime.now(tz).strftime("%Y-%m-%d")


def anchor_news_query_to_today(query: str, user_timezone: str | None) -> str:
    """Make a current-news search name the actual local calendar date."""
    return f"{query.strip()} {_today_label(user_timezone)} {_today_iso(user_timezone)}".strip()


def is_current_news_request(text: str) -> bool:
    topical_update = re.search(
        r"\b(?:news|headlines?|stories|developments?|updates?|current events|happening)\b",
        text,
        re.IGNORECASE,
    )
    return bool(
        (_NEWS.search(text) or topical_update)
        and re.search(r"\b(?:today|current|latest|right now)\b", text, re.IGNORECASE)
    )


def is_news_today_request(text: str) -> bool:
    """Return whether the user explicitly constrained news to this day."""
    topical_update = re.search(
        r"\b(?:news|headlines?|stories|developments?|updates?|current events|happening)\b",
        text,
        re.IGNORECASE,
    )
    return bool(
        (_NEWS.search(text) or topical_update)
        and re.search(r"\b(?:today|right now)\b", text, re.IGNORECASE)
    )


def _today_date_markers(now: datetime) -> set[str]:
    """Padded and unpadded labels. `_today_label` emits `October 01 2026`."""
    raw = (
        now.strftime("%Y-%m-%d"),
        now.strftime("%B %d, %Y"),
        now.strftime("%B %d %Y"),
        now.strftime("%B %d"),
        now.strftime("%b %d, %Y"),
        now.strftime("%b %d"),
    )
    markers: set[str] = set()
    for item in raw:
        folded = item.casefold()
        markers.add(folded)
        markers.add(folded.replace(" 0", " "))
    return markers


def _blob_has_date_marker(blob: str, marker: str) -> bool:
    """`October 1` must not match `October 15`."""
    start = 0
    while True:
        at = blob.find(marker, start)
        if at < 0:
            return False
        end = at + len(marker)
        if end >= len(blob) or not blob[end].isdigit():
            return True
        start = at + 1


def filter_hits_to_today(hits: list[WebSearchHit], user_timezone: str | None) -> list[WebSearchHit]:
    """Keep only current-news hits that name today's local date or were published today."""
    from app.modules.web_search.source_dates import published_day

    tz = time_context_service.resolve_timezone(user_timezone)
    now = datetime.now(tz)
    markers = _today_date_markers(now)
    return [
        hit
        for hit in hits
        if published_day(hit.published, user_timezone) == now.date()
        or any(
            _blob_has_date_marker(f"{hit.title} {hit.snippet}".casefold(), marker)
            for marker in markers
        )
    ]


# "near me" becomes "near <place>"; "my location" becomes the place itself.
_LOCATION_PHRASES = (
    (r"\b(?:near|close to)\s+me\b|\bnearby\b|\baround here\b", "near {loc}"),
    (r"\b(?:my|current|the user'?s)\s+(?:current\s+)?location\b", "{loc}"),
)


def anchor_to_location(query: str, location: str | None) -> str:
    """``coffee near me`` with a saved place is ``coffee near Westlands, Nairobi``.

    A search engine has no idea where "me" or "here" is: it answered with New
    York cafés and Milwaukee weather. The place replaces those words, or is
    appended when the query names no part of it ("Westlands Nairobi" does).
    """
    loc = (location or "").strip()
    if not loc:
        return query
    anchored = query
    for pattern, replacement in _LOCATION_PHRASES:
        anchored = re.sub(pattern, replacement.format(loc=loc), anchored, flags=re.I)
    parts = [part.strip().lower() for part in loc.split(",") if len(part.strip()) > 2]
    if not any(part in anchored.lower() for part in parts):
        anchored = f"{anchored} {loc}"
    return anchored
