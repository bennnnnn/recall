"""Whether a search is about how things stand now.

"What's the newest iPhone" searched those words, and the engine ranked 2018 and 2025
articles: the reply named last year's phone as the newest. The query then took the
user's year ("newest iphone 2026"), which went wrong another way: "latest iOS version
2026" ranked the iOS 26 pages over iOS 27 (2026-11-05). An ask about now keeps the user's
words and asks the search for pages from the last year instead
(``search_cache.run_cached_search``, ``dated``). No product list: the recency words decide.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

# "Newest", "latest", "most recent", "brand new", "just released", or "the new
# X". Bare "new" is not enough: "I'm new to Python", "a new way to learn".
_RECENCY = re.compile(
    r"\b(?:newest|latest|most\s+recent|brand[- ]new|just\s+(?:released|launched|announced)"
    r"|the\s+new(?!\s+(?:year|years|moon)\b))\b",
    re.IGNORECASE,
)
# A year the message names ("who won in 2025", "the 2026 model").
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def asks_for_newest(text: str) -> bool:
    """True for "what's the newest iPhone", "the latest Django release"."""
    return _RECENCY.search(text) is not None


# Words that ask how things stand now: a result, a score, the news, "so far", "this
# season". With these the answer depends on when each page was written.
_NOW_WORDS = re.compile(
    r"\b(?:who won|who(?:'s| is) (?:winning|leading|ahead|in the lead|in the (?:final|series"
    r"|playoffs|world series))|final score|what(?:'s| is| was) the score|the score (?:of|in)"
    r"|scores? (?:today|tonight|last night|yesterday)|standings|breaking news|latest news"
    r"|in the news|(?:news|headlines?) (?:today|this (?:morning|week))|today'?s (?:news|headlines?)"
    r"|(?:election|game|match|race|week \d+) results|results? (?:of|from) (?:the|last|this)"
    r"|today|tonight|last night|right now|at the moment|so far|currently"
    r"|this (?:week|weekend|month|season)|out yet|still (?:shut down|closed|open|going|on))\b",
    re.IGNORECASE,
)
# How something stands: "is the world series over?", "has the election been called?",
# "is the iphone 18 out", "did the dodgers win?", "when is game 3?".
_STATUS = re.compile(
    r"\b(?:is|are|has|have|did|was)\s+(?:it|they|the\s+[\w'-]+(?:\s+[\w'-]+){0,2})\s+"
    r"(?:already\s+|been\s+)?(?:over|done|finished|started|ended|begun|out|called|happening)\b"
    r"|\balready\s+(?:over|out|started|finished|ended|happened|begun|released)\b"
    r"|\bdid\s+(?:the\s+)?[\w'-]+(?:\s+[\w'-]+)?\s+win\b|\bgame\s+\d\b",
    re.IGNORECASE,
)
# A question about the past: "who won the 1998 world series", "the first super bowl".
_HISTORY = re.compile(r"\b(?:first|ever|all[- ]time|in history)\b", re.IGNORECASE)


def wants_dated_results(text: str | None) -> bool:
    """A search whose pages must say when they were written: a result, a score, the
    latest, how something stands now, or this year by name. A question about an earlier
    year, the first or the all-time is history, and a search for places near the user
    lists places."""
    from app.modules.web_search.geo_intent import is_geo_query
    from app.modules.web_search.patterns import collapse_ws

    cleaned = collapse_ws(text or "")
    if not cleaned or is_geo_query(cleaned):
        return False
    years = {int(year) for year in _YEAR.findall(cleaned)}
    this_year = datetime.now(UTC).year
    if (years and max(years) < this_year) or _HISTORY.search(cleaned):
        return False
    if this_year in years:
        return True
    return bool(_NOW_WORDS.search(cleaned) or _STATUS.search(cleaned) or asks_for_newest(cleaned))
