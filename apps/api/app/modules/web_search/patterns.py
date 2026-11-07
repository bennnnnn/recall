"""Patterns the search tool shapes a query and its places answer with (news, nearby, venues)."""

from __future__ import annotations

import re

from app.modules.web_search.weather import is_weather_request as is_weather_request
from app.services.text_normalize import collapse_ws as collapse_ws

_NEWS = re.compile(
    r"\b("
    r"what(?:['\u2019]s| is) (?:happening|going on|new(?!\s+with\s+(?:you|u|ya|yourself)\b)|in the news)"
    r"|top (?:news|stories|headlines)"
    r"|news (?:today|this week|stories)"
    r"|in the world today"
    r"|world news|current events"
    r"|what(?:['\u2019]s| is) cookin(?:['\u2019]|g)?(?: in the world)?"
    r")\b",
    re.IGNORECASE,
)


# Proximity intent — any "near me / nearest / closest …" ask, not a venue-type list.
_NEARBY_INTENT = re.compile(
    r"\b("
    r"near\s+me|nearby|around\s+here|in\s+(?:this\s+)?town"
    r"|close\s+(?:by|to\s+me)"
    r"|(?:the\s+)?(?:nearest|closest)\b"
    r")\b",
    re.IGNORECASE,
)


# Abstract "nearest X" subjects — not a maps search. Matched with bounded
# index scans (not ``nearest.+word``) to avoid poly-ReDoS on chat text.
_NON_GEOGRAPHIC_NEAREST_WORDS = (
    "number",
    "numbers",
    "integer",
    "prime",
    "multiple",
    "match",
    "deadline",
    "star",
    "planet",
    "galaxy",
    "sun",
    "moon",
    "approach",
    "analogy",
    "synonym",
    "equivalent",
    "friend",
    "relative",
    "cousin",
    "neighbor",
    "neighbour",
    "guess",
    "approximation",
    "solution",
    "competitor",
    "rival",
)
_GEO_PHRASE_GAP = 120


def _find_word(haystack: str, word: str, start: int = 0) -> int:
    """Index of a whole-word match of ``word`` in lowercase ``haystack``, or -1."""
    n = len(word)
    i = start
    while True:
        i = haystack.find(word, i)
        if i == -1:
            return -1
        before_ok = i == 0 or not haystack[i - 1].isalnum()
        after = i + n
        after_ok = after >= len(haystack) or not haystack[after].isalnum()
        if before_ok and after_ok:
            return i
        i = after


def non_geographic_nearest(text: str) -> bool:
    """True for 'nearest prime' / 'closest friend' — not venue search."""
    low = text.lower()
    for anchor in ("nearest", "closest"):
        start = 0
        while True:
            i = _find_word(low, anchor, start)
            if i == -1:
                break
            rest = low[i + len(anchor) : i + len(anchor) + _GEO_PHRASE_GAP]
            if any(_find_word(rest, w) != -1 for w in _NON_GEOGRAPHIC_NEAREST_WORDS):
                return True
            start = i + 1
    return False


def best_near_phrase(text: str) -> bool:
    """True for 'best … in/near/around/by …' without ``best.+near`` ReDoS."""
    low = text.lower()
    start = 0
    while True:
        i = _find_word(low, "best", start)
        if i == -1:
            return False
        rest = low[i + 4 : i + 4 + _GEO_PHRASE_GAP]
        if any(_find_word(rest, w) != -1 for w in ("in", "near", "around", "by")):
            return True
        start = i + 1


# Implicit nearby intent without saying "near me" (e.g. "where should I eat tonight?").
_IMPLICIT_LOCAL = re.compile(
    r"\b(?:"
    r"where\s+(?:should|can|do)\s+(?:I|we)\s+(?:eat|get|find|go|stay|park)"
    r"|where\s+to\s+(?:eat|go|get|stay|park)"
    r"|what(?:'s| is)\s+(?:good|open)\s+(?:around|near|nearby)"
    r")\b",
    re.IGNORECASE,
)


# Real-estate asks that need sale/rent/address clarified — not generic "places near me".
_AMBIGUOUS_NEARBY_SUBJECT = re.compile(
    r"\b(?:"
    r"house|houses|home|homes|property|properties|building|buildings"
    r"|apartment|apartments|condo|condos|flat|flats|unit|units"
    r")\b",
    re.IGNORECASE,
)


_QUALIFIED_NEARBY = re.compile(
    r"\b(?:"
    r"for\s+sale|to\s+(?:buy|rent|lease)|for\s+rent|rentals?|buying|leasing"
    r"|open\s+(?:now|today)|24\s*hours?"
    r"|near\s+\d|at\s+\d|from\s+\d|\d+\s+\w+\s+(?:st|street|ave|avenue|rd|road|blvd|dr|drive|way|ln|lane)\b"
    r")\b",
    re.IGNORECASE,
)


_PROXIMITY_PHRASES = (
    r"\bnear\s+me\b",
    r"\bnearby\b",
    r"\baround\s+here\b",
    r"\bin(?:\s+this)?\s+town\b",
    r"\bclose\s+(?:by|to\s+me)\b",
    r"\b(?:the\s+)?(?:nearest|closest)\b",
    r"\bbest\b",
)


_STREET_SUFFIX = (
    r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Pl|Place|"
    r"Ct|Court|Sq|Square|Pkwy|Parkway)"
)


_ADDRESS_RE = re.compile(
    rf"\b(\d+\s+[\w\s.'#-]{{2,40}}{_STREET_SUFFIX}\b(?:,\s*[\w\s.'-]{{2,30}})?)",
    re.IGNORECASE,
)


_PRICE_RE = re.compile(r"(?<![\w$])(\$\$\$|\$\$|\$)(?![\w$])")


_NUMBERED_VENUE_LINE = re.compile(r"^\s*\d+\.\s+")
