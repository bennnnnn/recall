"""Whether a question asks about a place the chat already named ("what's the weather there").

The location answer checks it: such a question needs no location of the user's own.
"""

from __future__ import annotations

import re
from typing import Any

from app.modules.web_search.geo_intent import (
    is_distance_query,
    is_proximity_query,
)
from app.modules.web_search.patterns import (
    collapse_ws,
)
from app.modules.web_search.subject import collect_prior_user_messages
from app.modules.web_search.weather import around_the_user

# "From here", "is it raining here": the user's own place, whatever the chat was about.
_HERE = re.compile(r"\bhere\b(?!'s|\s+(?:is|are)\b)", re.IGNORECASE)
# "There" points at a place said earlier; "is there a pharmacy …", "there's a ramen place
# …", "hi there" and "out there" point at none.
_THERE = re.compile(r"\bthere\b", re.IGNORECASE)
_NO_PLACE_THERE = re.compile(
    r"\b(?:(?:is|are|was|were)\s+there|there(?:'s|\s+(?:is|are|was|were))"
    r"|(?:hi|hey|hello|thanks|thank\s+you)\s+there|out\s+there)\b",
    re.IGNORECASE,
)


def points_back_in_chat(text: str, messages: list[dict[str, Any]]) -> bool:
    """``text`` asks about a place the chat named: "whats the weather like there now" after
    talk of a Zanzibar trip asks about Zanzibar, not the user's location.

    "There" must point at a place ("it" names a thing; "is there", "hi there" and "out
    there" name nothing), the chat must have come before it, and the question must need no
    place of the user's own, as their surroundings or a trip ("how long to get there") do
    (reviews of #2305). Which place the chat named is the search's to read: its resolver
    reads the whole chat, where a word list could not tell "zanzibar" from "in December".
    """
    cleaned = collapse_ws(text)
    if _HERE.search(cleaned) or around_the_user(cleaned) or is_proximity_query(cleaned):
        return False
    if is_distance_query(cleaned) or not _THERE.search(_NO_PLACE_THERE.sub(" ", cleaned)):
        return False
    return bool(collect_prior_user_messages(messages, text))
