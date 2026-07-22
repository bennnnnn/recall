"""Regex patterns for web search intent detection."""

from __future__ import annotations

import re

# Re-export for detection/subject/query_builders (stable import path).
from app.services.text_normalize import collapse_ws as collapse_ws

_EXPLICIT_SEARCH = re.compile(
    r"\b("
    r"search(?: the)? web"
    r"|look(?: it| that)? up(?: online)?"
    r"|google(?: for| this| it)?"
    r"|web search"
    r"|find(?: me)? (?:online|on the internet)"
    r")\b",
    re.IGNORECASE,
)

# Match against ``collapse_ws``-normalized input (single spaces, no leading/trailing).
_LOOK_IT_UP = re.compile(
    r"^(?:please )?(?:look(?: it| that) up|search(?: for)?(?: it)?)[.!?]*$",
    re.IGNORECASE,
)

_CLARIFICATION = re.compile(
    r"^(?:"
    r"no[,!.]? (?:i meant|the|not)|"
    r"(?:i meant|not that|the ongoing|the current|that one|this one)|"
    r"yes[,!.]? (?:that|the)\b"
    r")",
    re.IGNORECASE,
)

_ONGOING = re.compile(
    r"\b(ongoing|current(?:ly)?|right now|happening now|this one|that one)\b",
    re.IGNORECASE,
)

_WORLD_CUP = re.compile(r"\b(world\s+cup|fifa|wc\s*2026|2026\s+world\s+cup)\b", re.IGNORECASE)

_SHORT_FOLLOWUP_WORDS = 12

_RECENCY_PHRASES = (
    "latest",
    "breaking",
    "today",
    "today's",
    "current",
    "currently",
    "recent",
    "recently",
    "right now",
    "this week",
    "this month",
    "as of",
    "news",
    "headline",
    "stock price",
    "share price",
    "market cap",
    "who won",
    "what happened",
    "score",
    "scores",
    "release date",
)


def has_recency(text: str) -> bool:
    """True when ``text`` (already ``collapse_ws``-normalized) looks time-sensitive.

    Uses substring / index scans — the old ``.+`` alternatives in a single
    regex were CodeQL polynomial-ReDoS sinks on user chat text.
    """
    low = text.lower()

    def _bounded(phrase: str) -> bool:
        start = 0
        while True:
            i = low.find(phrase, start)
            if i == -1:
                return False
            before_ok = i == 0 or not low[i - 1].isalnum()
            after = i + len(phrase)
            after_ok = after >= len(low) or not low[after].isalnum()
            if before_ok and after_ok:
                return True
            start = i + 1

    if any(_bounded(p) for p in _RECENCY_PHRASES):
        return True
    idx = low.find("when did ")
    if idx != -1:
        rest = low[idx + 9 :]
        if any(k in rest for k in (" happen", " release", " launch")):
            return True
    idx = 0
    while True:
        i = low.find("is ", idx)
        if i == -1:
            break
        if i == 0 or not low[i - 1].isalnum():
            rest = low[i + 3 :]
            if "still alive" in rest or "currently alive" in rest:
                return True
        idx = i + 1
    return False


_NEWS = re.compile(
    r"\b("
    r"what(?:'s| is) (?:happening|going on|new|in the news)"
    r"|top (?:news|stories|headlines)"
    r"|news (?:today|this week|stories)"
    r"|in the world(?: today)?"
    r"|world news|current events"
    r"|what(?:'s| is) cookin(?:'|g)?(?: in the world)?"
    r")\b",
    re.IGNORECASE,
)

_SPORTS = re.compile(
    r"\b("
    r"game|games|match|matches|score|scores|result|results|fixture|standings|highlights|"
    r"soccer|football|nba|nfl|mlb|nhl|premier league|world cup|mls|uefa|champions league"
    r")\b",
    re.IGNORECASE,
)

_YESTERDAY = re.compile(r"\byesterday(?:'?s)?\b", re.IGNORECASE)

_SPORTS_LOOKUP = re.compile(
    r"\b("
    r"yesterday(?:'?s)?\s+(?:games?|match(?:es)?|result|score|scores)"
    r"|(?:games?|match(?:es)?|score|scores|results?)\s+(?:from\s+)?yesterday"
    r"|show me (?:the\s+)?yesterday(?:'?s)?\s+(?:games?|match(?:es)?|result|score|scores)"
    r"|show me (?:the\s+)?(?:games?|match(?:es)?|score|scores|results?)"
    r"|who won (?:the\s+)?(?:games?|match(?:es)?|yesterday|last night)"
    r"|last night(?:'s)?\s+(?:games?|match(?:es)?|score|scores)"
    r")\b",
    re.IGNORECASE,
)

_TEAM_SCORE = re.compile(
    r".{2,60}\b(?:games?|match(?:es)?)\s+score",
    re.IGNORECASE,
)

_TEAM_POSSESSIVE_SCORE = re.compile(
    r".{2,40}(?:'s|s)\s+(?:games?|match(?:es)?|score|scores|result|results)",
    re.IGNORECASE,
)

_SKIP = re.compile(
    r"\b("
    r"rewrite|proofread|debug|refactor|explain\s+this\s+code"
    r"|help\s+me\s+write|draft\s+(?:an?\s+)?(?:email|message|reply)"
    r"|remember\s+that|add\s+to\s+(?:my\s+)?(?:todo|list|memory)"
    r"|translate|summarize\s+this\s+(?:text|email|article)"
    r"|vocabulary\s+quiz|interactive\s+vocabulary|quiz\s+me\s+in\s+chat"
    r"|quick\s+quiz|begin\s+with\s+the\s+first\s+question"
    r")\b",
    re.IGNORECASE,
)

_PERSONAL_PLANNING = re.compile(
    r"\b("
    r"what\s+(?:am\s+I|are\s+we|do\s+I|should\s+I)\s+(?:trying\s+to\s+)?(?:get|have)\s+(?:done|to\s+do)"
    r"|what(?:'s| is)\s+(?:on\s+my\s+(?:plate|list|agenda)|due|still\s+open)"
    r"|what\s+(?:do\s+I|should\s+I)\s+need\s+to\s+(?:do|finish|tackle)"
    r"|(?:my|any)\s+(?:tasks?|todos?|reminders?)\s+(?:for\s+)?(?:today|tonight|this\s+week)"
    r"|how(?:'s| is)\s+my\s+day\s+looking"
    r"|how\s+did\s+my\s+day\s+go"
    r"|help\s+me\s+(?:prioriti[sz]e|plan|wrap\s+up)"
    r"|(?:show|list)\s+(?:me\s+)?(?:my\s+)?(?:tasks?|todos?|reminders?)"
    r"|what\s+(?:should\s+I|can\s+I)\s+(?:tackle|focus\s+on|work\s+on)\s+(?:today|tonight|now)?"
    r"|anything\s+(?:left|open|due)\s+(?:for\s+)?(?:me\s+)?(?:today|tonight)"
    r"|wrap\s+up\s+(?:loose\s+ends|my\s+day)"
    r"|wind\s+down"
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

_QUIZ_ANSWER = re.compile(r"^[A-D]\.?$", re.IGNORECASE)

# Distance / travel from the user's location — venue-agnostic.
_DISTANCE_INTENT = re.compile(
    r"\b("
    r"how\s+far"
    r"|how\s+many\s+(?:miles|kilometers|kilometres|km|minutes|mins)"
    r"|(?:walking|driving|drive|travel|commute)\s+(?:distance|time)"
    r"|distance\s+(?:to|from)"
    r"|how\s+long\s+(?:to\s+get|does\s+it\s+take|is\s+the\s+(?:drive|trip|walk))"
    r"|(?:miles|km|kilometers?|kilometres?|minutes?)\s+(?:away|from\s+(?:me|here))"
    r"|directions?\s+to"
    r")\b",
    re.IGNORECASE,
)

_FROM_USER = re.compile(
    r"\b(?:from\s+(?:me|here|my\s+(?:location|place))|to\s+me|where\s+i\s+am)\b",
    re.IGNORECASE,
)


def distance_between_phrase(text: str) -> bool:
    """True for 'distance … between …' (city A–B), not distance-from-me."""
    low = text.lower()
    i = _find_word(low, "distance")
    if i == -1:
        return False
    rest = low[i + 8 : i + 8 + _GEO_PHRASE_GAP]
    return _find_word(rest, "between") != -1


_QUERY_PREFIX = re.compile(
    r"^\s*(?:"
    r"(?:can\s+you\s+)?(?:please\s+)?"
    r"(?:search(?:\s+the)?\s+web(?:\s+for)?|"
    r"look\s+up(?:\s+online)?(?:\s+for)?|"
    r"google(?:\s+for)?|"
    r"find(?:\s+online)?(?:\s+for)?)"
    r")\s*",
    re.IGNORECASE,
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

_GENERIC_NEWS_QUERY = re.compile(
    r"^(?:"
    r"what(?:'s| is) (?:happening|going on|new)(?: in the world(?: today)?| in the news)?"
    r"|top (?:news|stories|headlines)"
    r"|news (?:today|this week|stories)"
    r"|(?:what(?:'s| is) )?(?:cookin(?:'|g)?(?: in the world)?|in the world(?: today)?)"
    r"|world news|current events"
    r")\s*[.!?]*$",
    re.IGNORECASE,
)

_NUMBERED_VENUE_LINE = re.compile(r"^\s*\d+\.\s+")
