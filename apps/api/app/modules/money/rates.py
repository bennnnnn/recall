"""Today's average rate for a product, looked up on the web and checked before it is used.

One search ("average 30-year fixed mortgage rate this week United States") and one small
structured read of its top results give a rate, the date it describes and the page that
states it. The reading is used only when the rate is plausible for the product, the date
is recent (both set on the catalog row) and the page is one the search returned; anything
else is no average, and the reply then gives no market note and no marker. One answer
serves every turn for the same product (or kind of it: a used car), term and country for
``money_rate_cache_seconds``, and an answer with no checked rate for a quarter of an hour;
turns asking while a lookup is on its way share it. Nothing here raises into the turn.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.gateways.mcp.base import TavilyBudget
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import User
from app.models.routing_lanes import ROUTING
from app.modules.money.catalog import Product, RateLookup
from app.modules.web_search import run_cached_search

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "money:average:"
# A product, term and country the web gave no checked rate for, kept a quarter of an hour:
# every turn about it searched again (audit, 2026-11-25), and a rate published since is found
# soon after.
_MISS = "missing"
_MISS_SECONDS = 15 * 60
_MISSED = object()
# The lookup running for each (event loop, cache key): a turn that asks while one is on its
# way waits for that answer instead of starting a second search (single flight).
_IN_FLIGHT: dict[tuple[int, str], asyncio.Task[MarketRate | None]] = {}
# The search results the reading may cite; more only dilute a small model's attention.
_TOP_RESULTS = 5
_READ_MAX_TOKENS = 96
# The read runs while the reply streams; past this it is dropped, never waited on.
_READ_TIMEOUT_SECONDS = 4.0
_READ_INSTRUCTIONS = (
    "You read one interest rate out of web search results. Use only a rate a result "
    "states, for the product and country asked, with the date that result gives for it "
    "(the week or month it describes, or its publication date). Reply with JSON only: "
    '{"found": true, "rate_percent": 6.27, "as_of": "YYYY-MM-DD", "source_url": "<the '
    'url of the result that states it, exactly as listed>"}. If no result states such a '
    'rate, reply {"found": false}. Never estimate or average numbers yourself.'
)


@dataclass(frozen=True)
class MarketRate:
    """One average rate in percent, the day it describes, and the page that states it."""

    value: float
    as_of: date
    source_title: str
    source_url: str
    # What the rate is, in the reply's words ("30-year fixed mortgage rate").
    name: str
    country: str
    # Said beside the rate when it stands in for the kind asked (``Variant.stand_in``).
    caveat: str = ""
    # Said beside an average of kinds priced far apart (``RateLookup.spread``): it judges
    # no rate. Read from the catalog row, never cached, so a change to the row shows at once.
    spread: str = ""


class RateReading(BaseModel):
    """The structured read of the search results (validated before use, golden rule 6)."""

    found: bool
    rate_percent: float | None = Field(default=None, ge=0, le=100)
    as_of: str | None = Field(default=None, max_length=32)
    source_url: str | None = Field(default=None, max_length=2048)


def search_query(lookup: RateLookup, bucket: float | None, country: str) -> str:
    return f"average {lookup.describe(bucket)} this week {country}"


async def current_average(
    product: Product,
    term: float | None,
    country: str,
    settings: Settings,
    redis: Redis | None,
    *,
    user: User | None = None,
    today: date | None = None,
    variant: str = "",
    budget: TavilyBudget | None = None,
) -> MarketRate | None:
    """Today's checked average for ``product`` (its ``variant`` kind) at ``term`` in
    ``country``, or None.

    A miss is a search on the turn's ``budget`` (its one search; no user: the free
    provider only); the answer then serves everyone asking the same thing until it
    expires.
    """
    lookup = product.rate_lookup(variant)
    if lookup is None:
        return None
    bucket = lookup.term_bucket(term)
    term_key = f"{bucket:g}" if bucket is not None else "-"
    kind = product.key if lookup is product.lookup else f"{product.key}-{variant}"
    key = f"{_CACHE_PREFIX}{kind}:{term_key}:{country.lower()}"
    day = today or datetime.now(UTC).date()
    cached = await _cached(redis, key)
    if cached is _MISSED:
        return None
    if isinstance(cached, MarketRate) and _fresh(cached.as_of, lookup, day):
        return replace(cached, spread=lookup.spread)
    search = _Search(settings, redis, user, budget)
    flight = (id(asyncio.get_running_loop()), key)
    running = _IN_FLIGHT.get(flight)
    if running is None:
        running = asyncio.ensure_future(_look_up(search, key, lookup, bucket, country, day))
        _IN_FLIGHT[flight] = running
        running.add_done_callback(lambda _done: _IN_FLIGHT.pop(flight, None))
    found = await asyncio.shield(running)
    return None if found is None else replace(found, spread=lookup.spread)


@dataclass(frozen=True)
class _Search:
    """Whose search a lookup runs on: the turn that started it."""

    settings: Settings
    redis: Redis | None
    user: User | None
    budget: TavilyBudget | None


async def _look_up(
    search: _Search,
    key: str,
    lookup: RateLookup,
    bucket: float | None,
    country: str,
    today: date,
) -> MarketRate | None:
    """One search and one read for ``key``; a checked rate is kept for the cache's time, and
    an answer with no checked rate for ``_MISS_SECONDS``. A search or a read that failed is
    never kept: the next turn tries again."""
    try:
        hits, _ = await run_cached_search(
            search.settings,
            [search_query(lookup, bucket, country)],
            user=search.user,
            redis=search.redis,
            budget=search.budget,
        )
    except Exception:
        logger.info("money rate search failed for %s", key, exc_info=True)
        return None
    shown = hits[:_TOP_RESULTS]
    reading = await _read(shown, lookup, bucket, country, search.settings, today)
    found = checked(reading, shown, lookup, bucket, country, today)
    if found is not None:
        await _store(search.redis, key, found, search.settings.money_rate_cache_seconds)
    elif reading is not None:
        await _store_miss(search.redis, key)
    return found


async def _read(
    hits: Sequence[WebSearchHit],
    lookup: RateLookup,
    bucket: float | None,
    country: str,
    settings: Settings,
    today: date,
) -> RateReading | None:
    """The small model's reading of the results; None when there are none or it failed."""
    if not hits:
        return None
    listing = "\n\n".join(
        f"[{index}] {hit.title}\nurl: {hit.url}\n{hit.snippet[:600]}"
        for index, hit in enumerate(hits, 1)
    )
    asked = f"Product: average {lookup.describe(bucket)}. Country: {country}. Today: {today}."
    try:
        reading = await litellm_gateway.complete_structured(
            settings=settings,
            model_alias=ROUTING.background,
            messages=[
                {"role": "system", "content": _READ_INSTRUCTIONS},
                {"role": "user", "content": f"{asked}\n\nResults:\n\n{listing}"},
            ],
            schema=RateReading,
            max_tokens=_READ_MAX_TOKENS,
            timeout_seconds=_READ_TIMEOUT_SECONDS,
            allow_fallback=False,
        )
    except Exception:
        logger.info("money rate read failed", exc_info=True)
        return None
    return reading if isinstance(reading, RateReading) else None


def checked(
    reading: RateReading | None,
    hits: Sequence[WebSearchHit],
    lookup: RateLookup,
    bucket: float | None,
    country: str,
    today: date,
) -> MarketRate | None:
    """The reading as a market rate, or None when any check fails."""
    if reading is None or not reading.found or reading.rate_percent is None:
        return None
    low, high = lookup.plausible
    if not low <= reading.rate_percent <= high:
        return None
    try:
        as_of = date.fromisoformat((reading.as_of or "").strip()[:10])
    except ValueError:
        return None
    if not _fresh(as_of, lookup, today):
        return None
    source = next((hit for hit in hits if hit.url == (reading.source_url or "").strip()), None)
    if source is None:
        return None
    return MarketRate(
        value=round(reading.rate_percent, 3),
        as_of=as_of,
        source_title=source.title.strip()[:200],
        source_url=source.url,
        name=lookup.describe(bucket),
        country=country,
        spread=lookup.spread,
    )


def _fresh(as_of: date, lookup: RateLookup, today: date) -> bool:
    """A date no later than tomorrow (time zones) and no older than the row allows."""
    age = (today - as_of).days
    return -1 <= age <= lookup.fresh_days


async def _cached(redis: Redis | None, key: str) -> MarketRate | object | None:
    """The cached rate, ``_MISSED`` when the last lookup found none, else None."""
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        if raw in (_MISS, _MISS.encode()):
            return _MISSED
        data = json.loads(raw)
        return MarketRate(
            value=float(data["value"]),
            as_of=date.fromisoformat(str(data["as_of"])),
            source_title=str(data["source_title"]),
            source_url=str(data["source_url"]),
            name=str(data["name"]),
            country=str(data["country"]),
        )
    except Exception:
        logger.debug("money rate cache read failed for %s", key, exc_info=True)
        return None


async def _store(redis: Redis | None, key: str, rate: MarketRate, seconds: int) -> None:
    if redis is None:
        return
    payload = {
        "value": rate.value,
        "as_of": rate.as_of.isoformat(),
        "source_title": rate.source_title,
        "source_url": rate.source_url,
        "name": rate.name,
        "country": rate.country,
    }
    try:
        await redis.set(key, json.dumps(payload), ex=seconds)
    except Exception:
        logger.debug("money rate cache write failed for %s", key, exc_info=True)


async def _store_miss(redis: Redis | None, key: str) -> None:
    if redis is None:
        return
    try:
        await redis.set(key, _MISS, ex=_MISS_SECONDS)
    except Exception:
        logger.info("money rate miss not kept for %s", key, exc_info=True)
