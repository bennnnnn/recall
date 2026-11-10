"""Which search results a reply used: only those become its source chips.

Every hit used to be a chip. "Can i wolk?" showed a Kentucky charity PDF and an Idaho
emigrant-trails paper, and "Where is the nearest one" a UPS Store and an Apple jobs page
(2026-11-09). Words shared with the reply cannot tell which pages it used, not across a
paraphrase or another language, so the claim check's model call, which already reads the
reply beside the pages, names them too. On 46 searched turns it showed 16 unused chips where
every hit showed 112, and missed 1 of 69 used pages.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator

# The checker's instruction for the ``used`` field of its verdict.
SOURCES_USED_RULE = (
    "used lists the number of each web result the reply took something from: a fact, "
    "figure, name, place or piece of advice the reply states that the result gives, in any "
    "wording or language. Name a result only when you can point to such a statement in "
    "the reply; when the reply credits a source by name, that is the result it used. A "
    "result about another place, person, product or subject is not used, even when it "
    "shares words with the question. A reply that only asks the user something, or "
    "answers without anything the results say, used none: an empty list."
)

# Where a checker that wrote a page as an object put its number.
_PAGE_KEYS = ("id", "number", "result", "index", "n")


def _page_numbers(value: object) -> list[int] | None:
    """The page numbers however the checker wrote them. It sometimes wrote each page as
    {"id": 1, "claims": [...]}, and an item that did not read failed the whole verdict, its
    cuts too. A list with nothing readable in it says nothing, which is not "no pages"."""
    if not isinstance(value, list):
        return None
    numbers: list[int] = []
    for item in value:
        if isinstance(item, dict):
            item = next((item[key] for key in _PAGE_KEYS if key in item), None)
        if isinstance(item, str) and item.strip("[] ").isdigit():
            item = int(item.strip("[] "))
        if isinstance(item, int) and not isinstance(item, bool):
            numbers.append(item)
    return numbers if numbers or not value else None


# A verdict's ``used``: None when the checker did not say, and then every page stays a chip.
PagesUsed = Annotated[list[int] | None, BeforeValidator(_page_numbers)]


def pages_used(used: list[int] | None, seen: int) -> list[int] | None:
    """Indexes of the pages the reply used, in search order; None when not known. A page
    past the ``seen`` the checker read is one it cannot vouch for."""
    if used is None:
        return None
    return sorted({number - 1 for number in used if 1 <= number <= seen})
