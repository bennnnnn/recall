"""A short message with a number, after a reply that listed things, may name an item.

Under a numbered list of ways to learn Python, "1" got "That's just the number 1 … were
you testing me?" and "More on 1" got "were you checking the time or date?"; "4" under five
beginner mistakes got "Option 4 is a small number" (2026-11-06). A rule in the system
prompt, read far from the message, helped half the time: the free plan's model follows the
note closest to the message. So beside a short message that holds a number or a place in a
list, the note names that item of the last reply's list. It is conditional ("if it points
at an item"), because "give me 3 more examples" holds a number too: the model, which reads
the whole message, decides.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

# A list item: "1. …", "2) …", "- …", "* …", "• …" at the line's start, not indented.
_NUMBERED = re.compile(r"^(?P<n>\d{1,2})[.)]\s+(?P<item>\S.*)$")
_BULLET = re.compile(r"^[-*•]\s+(?P<item>\S.*)$")
# A number on its own ("4", "#4", "4?"), never part of a larger one ("4.5", "2024").
_NUMBER = re.compile(r"(?<![\w.,])#?(?P<n>\d{1,2})(?![\w.,]\d)")
_PLACES = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}  # fmt: skip
# "the second one", "the last tip"; "first list" names a list, not an item.
_PLACE = re.compile(rf"\b(?P<word>{'|'.join(_PLACES)}|last)\b(?!\s+lists?\b)", re.IGNORECASE)
_MARKUP = re.compile(r"[*_`]+|\[(?P<text>[^\]]*)\]\([^)]*\)")
# "I said tell me about the first way u listed!" is ten words.
_SHORT_WORDS = 12
# A sum ("what is 2+2", "3 x 4") holds numbers that name no item.
_SUM = re.compile(r"\d\s*[-+*/\u00d7\u00f7^=x]\s*\d")
_ITEM_CHARS = 90
# The replies read for a list, and the lists named, newest first.
_REPLIES = 4
_LISTS = 2
_LIST_NAMES = ("your latest list", "the list before it")


def _items(reply: str) -> list[str]:
    """The last list in ``reply``: its numbered items, else its bullets, in order."""
    numbered: list[str] = []
    bullets: list[str] = []
    for line in reply.split("\n"):
        if (match := _NUMBERED.match(line)) is not None:
            if match["n"] == "1":
                numbered = []
            numbered.append(match["item"])
        elif (match := _BULLET.match(line)) is not None:
            bullets.append(match["item"])
    return numbered or bullets


def _plain(item: str) -> str:
    text = _MARKUP.sub(lambda m: m["text"] or "", item).strip()
    return text if len(text) <= _ITEM_CHARS else f"{text[:_ITEM_CHARS].rstrip()}…"


def _pointed(query: str, count: int) -> list[int]:
    """The item numbers ``query`` may name, 1 to ``count``, in its order."""
    found: list[int] = []
    for match in _NUMBER.finditer(query):
        found.append(int(match["n"]))
    for match in _PLACE.finditer(query):
        word = match["word"].lower()
        found.append(count if word == "last" else _PLACES[word])
    return [n for n in dict.fromkeys(found) if 1 <= n <= count]


def list_reference_hint(query: str, prior: Sequence[tuple[str, str]]) -> str | None:
    """The note naming the items a short message may point at, or None.

    The lists of the last few replies, newest first: "4 from ur first list" got item 5 of
    the newest one, invented, when the reply just before had no list (2026-11-06)."""
    if len(query.split()) > _SHORT_WORDS or _SUM.search(query):
        return None
    replies = [text for role, text in reversed(prior) if role == "assistant"][:_REPLIES]
    lists = [items for items in map(_items, replies) if len(items) >= 2][:_LISTS]
    named: list[str] = []
    for place, items in zip(_LIST_NAMES, lists, strict=False):
        named += [
            f'item {n} of {place} is "{_plain(items[n - 1])}"' for n in _pointed(query, len(items))
        ]
    if not named:
        return None
    return (
        "If this message points at an item of a list you gave, by its number or its place, "
        f"it asks about that item: {'; '.join(named)}. Say more about the one it means, and "
        "never ask what the number means."
    )
