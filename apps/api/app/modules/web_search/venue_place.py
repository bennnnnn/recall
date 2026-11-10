"""The place that replaces the user's own in a places question, read from the sentence.

"What are the best restaurants in Addis Ababa?" is searched there, never near the phone. Only
three shapes replace the user's place (review of the named-place rule, 2026-11-09):

- "in" and a name with no article, in the clause that asks for the venues: "the best
  restaurants in Addis Ababa", "coffee near me in Bole", "coffee shops in Bole nearby";
- a sentence that opens with it: "In Rome, where should we eat?";
- the user saying where they are: "We're in Rome", "I'm staying in Bole".

"at", "near", "to" and "in the" before a name are a venue or a neighbourhood the user's
city still places, so the turn keeps that city: "We're at the Hilton, any restaurants
nearby?", "where can I park at the Apple Store", "best tacos near me in the Mission". And "in"
followed by a time names no place: a month, a weekday, a part of the day or a holiday ("where
should we eat in January"). In another clause it is not about the venues at all ("coffee
shops nearby, answer in Spanish"). ``docs/fixtures/geo_intent_cases.json`` holds the phone's
twin (``lib/places/venuePlace.ts``) to the same answers.
"""

from __future__ import annotations

import re

from app.modules.web_search.patterns import IMPLICIT_LOCAL, NEARBY_INTENT, best_near_phrase

# A capitalised name, as ``names_its_place`` reads one: a capital that starts a word of
# more than one letter ("Addis Ababa", "JFK", "SF"), never "I" or "A".
_NAME = r"[A-Z](?![\s'\u2019])[\w'\u2019.&-]*(?:\s+[A-Z][\w'\u2019.&-]*)*"
# "in" and a name with no article: the shape that replaces the user's place.
_IN_NAME = rf"\b(?i:in)\s+(?!(?i:the)\s)(?P<name>{_NAME})"
_PLACED = re.compile(_IN_NAME)
_SENTENCE_END = re.compile(r"[.?!\n]")
_CLAUSE_END = re.compile(r"[.?!;,:\n]")
# After a comma, a list that goes on ("restaurants, cafes and bars in Rome") is still the
# ask's clause; anything else ("…nearby, answer in Spanish") starts another.
_LIST_GOES_ON = re.compile(r",\s*(?:[\w'-]+\s+){0,3}?(?:and|or|&)\s", re.IGNORECASE)
# A sentence that opens with the place: "In Rome, where should we eat?"
_OPENS_WITH_PLACE = re.compile(rf"\s*{_IN_NAME}")
# The user saying where they are: "We're in Rome", "I'm staying in Bole".
_USER_IS_IN = re.compile(
    r"\b(?:I(?:'m|\u2019m|\s+am)|[Ww]e(?:'re|\u2019re|\s+are))\s+"
    r"(?:(?:now|currently|staying|based|living|here)\s+)?"
    rf"{_IN_NAME}"
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


def _in_clause(text: str, ask: int) -> str | None:
    """The place the ask's own clause names, before or after the ask."""
    start = max((found.end() for found in _CLAUSE_END.finditer(text, 0, ask)), default=0)
    for found in _PLACED.finditer(text[start : _clause_end(text, ask)]):
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
        place = _in_clause(text, start) or _opening_place(text, start)
        if place:
            return place
    for found in _USER_IS_IN.finditer(text):
        place = _a_place(found.group("name"))
        if place:
            return place
    return None
