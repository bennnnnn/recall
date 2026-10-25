"""A search for the newest or latest of something names this year.

"What's the newest iPhone" searched those words, and the engine ranked 2018 and
2025 articles: the reply named last year's phone as the newest. A message that
asks what is newest now adds the user's current year to the query, as the photo
search does (``images.lookup_intent.dated_lookup_query``). No product list: the
recency words decide.
"""

from __future__ import annotations

import re
from datetime import datetime

from app.services import time_context as time_context_service

# "Newest", "latest", "most recent", "brand new", "just released", or "the new
# X". Bare "new" is not enough: "I'm new to Python", "a new way to learn".
_RECENCY = re.compile(
    r"\b(?:newest|latest|most\s+recent|brand[- ]new|just\s+(?:released|launched|announced)"
    r"|the\s+new(?!\s+(?:year|years|moon)\b))\b",
    re.IGNORECASE,
)
# A year the query already names ("iPhone 17 2026", "the 2025 model").
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def asks_for_newest(text: str) -> bool:
    """True for "what's the newest iPhone", "the latest Django release"."""
    return _RECENCY.search(text) is not None


def anchor_recency_to_year(query: str, user_text: str, user_timezone: str | None) -> str:
    """``newest iphone`` becomes ``newest iphone 2026`` when the user asked for the newest."""
    if not asks_for_newest(user_text) or _YEAR.search(query):
        return query
    tz = time_context_service.resolve_timezone(user_timezone)
    return f"{query.strip()} {datetime.now(tz).year}"


# Words that ask how things stand now: "is it over already?", "who's winning so far",
# "has the season started yet". With ``has_recency`` ("who won", "score", "today",
# "latest") they mark a search whose answer depends on when each page was written.
_STATUS_NOW = re.compile(
    r"\b(?:already|yet|so far|right now|at the moment|currently|still (?:on|going|running|"
    r"happening|open|playing)|this (?:year|season|week|month|weekend)|tonight|last night"
    r"|(?:is|has|did|was) (?:it|the \w+) (?:over|done|finished|started|ended|begun)"
    r"|just (?:started|ended|finished|happened|came out))\b",
    re.IGNORECASE,
)


def wants_dated_results(text: str | None) -> bool:
    """A search whose pages must say when they were written: a result, a score, the
    latest, how something stands now."""
    from app.modules.web_search.patterns import collapse_ws, has_recency

    cleaned = collapse_ws(text or "")
    if not cleaned:
        return False
    return has_recency(cleaned) or asks_for_newest(cleaned) or bool(_STATUS_NOW.search(cleaned))
