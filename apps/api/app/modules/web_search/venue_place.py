"""The place a places question names for its venues, read from how the sentence is built.

"What are the best restaurants in Addis Ababa?" names Addis Ababa: it is searched there,
never near the phone. A capital after "in" or "to" anywhere in the message is not that
place (review of the named-place rule, 2026-11-09):

- the place belongs to the clause that asks for the venues: "coffee shops nearby, answer
  in Spanish" and "nearest hospital? I'm visiting from Canada" name none;
- it comes after the ask, before any purpose: in "the nearest train station to get to
  Boston" Boston is the trip's, not the station's;
- "from" gives where someone comes from, never where the venue is;
- a time is no place: a month, a weekday, a part of the day or a holiday ("where should
  we eat in January", "where to eat at Thanksgiving").

A sentence that opens with the place ("In Rome, where should we eat?") names it too, and
so does the user saying where they are ("We're in Rome", "I'm staying in Bole").
``docs/fixtures/geo_intent_cases.json`` holds the phone's twin (``lib/places/venuePlace.ts``)
to the same answers.
"""

from __future__ import annotations

import re

from app.modules.web_search.patterns import IMPLICIT_LOCAL, NEARBY_INTENT, best_near_phrase

# A capitalised name, as ``names_its_place`` reads one: a capital that starts a word of
# more than one letter ("Addis Ababa", "JFK", "SF"), never "I" or "A".
_NAME = r"[A-Z](?![\s'\u2019])[\w'\u2019.&-]*(?:\s+[A-Z][\w'\u2019.&-]*)*"
# Where a venue is: in, near, around or at a place, or the nearest one to it.
_PLACED = re.compile(rf"\b(?i:in|near|around|at|to)\s+(?:the\s+)?(?P<name>{_NAME})")
# A purpose ends the venue's phrase: "to get to Boston", "to watch the game". "To me",
# "to my hotel" and "to the station" are still where the venue is.
_PURPOSE = re.compile(
    r"\b(?i:to)\s+(?!(?i:me|my|our|your|us|the|a|an|this|that|here|there|where)\b)[a-z]"
)
_SENTENCE_END = re.compile(r"[.?!\n]")
_CLAUSE_END = re.compile(r"[.?!;,:\n]")
# After a comma, a list that goes on ("restaurants, cafes and bars in Rome") is still the
# ask's clause; anything else ("…nearby, answer in Spanish") starts another.
_LIST_GOES_ON = re.compile(r",\s*(?:[\w'-]+\s+){0,3}?(?:and|or|&)\s", re.IGNORECASE)
# A sentence that opens with the place: "In Rome, where should we eat?"
_OPENS_WITH_PLACE = re.compile(rf"\s*(?i:in|at|near|around)\s+(?:the\s+)?(?P<name>{_NAME})")
# The user saying where they are: "We're in Rome", "I'm staying in Bole", "I am at JFK".
_USER_IS_AT = re.compile(
    r"\b(?:I(?:'m|\u2019m|\s+am)|[Ww]e(?:'re|\u2019re|\s+are))\s+"
    r"(?:(?:now|currently|staying|based|living|here)\s+)?(?i:in|at)\s+(?:the\s+)?"
    rf"(?P<name>{_NAME})"
)
# Times written with a capital: the calendar's months and weekdays, the parts of a day,
# and the holidays a meal or an outing is planned around.
_TIME = re.compile(
    r"(?:January|February|March|April|May|June|July|August|September|October|November"
    r"|December|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Morning|Afternoon"
    r"|Evening|Night|Tonight|Today|Tomorrow|Weekend|Christmas|Easter|Thanksgiving|Halloween"
    r"|Ramadan|Eid|Diwali|Hanukkah|Passover|Lent|Valentine|New\s+Year|Meskel|Timkat|Genna)\b"
)


def _a_place(name: str) -> str | None:
    return None if _TIME.match(name) else name.strip()


def _ask_start(text: str) -> int | None:
    """Where the places ask starts: "near me", "nearest", "where should we eat", "best"."""
    starts = [
        found.start()
        for found in (NEARBY_INTENT.search(text), IMPLICIT_LOCAL.search(text))
        if found
    ]
    best = re.search(r"\bbest\b", text, re.IGNORECASE)
    if best and best_near_phrase(text):
        starts.append(best.start())
    return min(starts, default=None)


def _clause_end(text: str, start: int) -> int:
    """Where the clause holding ``start`` ends: its punctuation, past a list that goes on."""
    end = _CLAUSE_END.search(text, start)
    while end and end.group() == "," and _LIST_GOES_ON.match(text, end.start()):
        end = _CLAUSE_END.search(text, end.end())
    return end.start() if end else len(text)


def _placed_after(text: str, start: int) -> str | None:
    """The first place the ask's own clause gives its venues, after ``start``."""
    clause = text[start : _clause_end(text, start)]
    purpose = _PURPOSE.search(clause)
    if purpose:
        clause = clause[: purpose.start()]
    for found in _PLACED.finditer(clause):
        place = _a_place(found.group("name"))
        if place:
            return place
    return None


def _opening_place(text: str, start: int) -> str | None:
    """A place the ask's sentence opens with, before the ask."""
    sentence_start = max(
        (found.end() for found in _SENTENCE_END.finditer(text, 0, start)), default=0
    )
    found = _OPENS_WITH_PLACE.match(text, sentence_start, start)
    return _a_place(found.group("name")) if found else None


def venue_place(text: str) -> str | None:
    """The place a places question names for its venues, or None: the user's own place."""
    start = _ask_start(text)
    if start is not None:
        place = _placed_after(text, start) or _opening_place(text, start)
        if place:
            return place
    for found in _USER_IS_AT.finditer(text):
        place = _a_place(found.group("name"))
        if place:
            return place
    return None
