"""A short message with a number, after a reply that listed things, may name an item.

Under a numbered list of ways to learn Python, "1" got "That's just the number 1 … were
you testing me?" and "More on 1" got "were you checking the time or date?"; "4" under five
beginner mistakes got "Option 4 is a small number" (2026-11-06). A rule in the system
prompt, read far from the message, helped half the time: the free plan's model follows the
note closest to the message. So beside a short message that holds a number or a place in a
list, the note names that item of the last reply's list. It is conditional ("if it points
at an item"), because "give me 3 more examples" holds a number too: the model, which reads
the whole message, decides.

A reply that ends on a question offering choices ("Want to do the periodic table link
properly, or jump to a mixed exam-style set?") is answered by a pick among them: in a long
study chat (2026-11-15) "the first one", "the second one" and "2" all got the numbered list
above that question, on every try, each reply opening "Item 1 is about…". After such a
question the note names the question's choices first and a list's items as the other reading:
"Want me to go deeper on any of these, or suggest a study plan?" is answered by "2" naming
the list's second item, which a note naming only the choices sent to the study plan.
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
# The question a reply ends on, an emoji or two after its mark allowed. It offers choices
# when it joins them with "or" ("…properly, or jump to a mixed set?"); "Which one do you
# want, or should I pick?" asks for an item of the list above it.
_CLOSING_QUESTION = re.compile(r"(?P<question>[^\n.!?]*\?)[^\w\n]*$")
# Only the reply's end is searched: a 32,000-character line with no mark took the search 2 s.
_TAIL_CHARS = 1_000
_ASIDE = re.compile(r"\s*\([^()]*\)")
_WHICH = re.compile(r"\bwhich\b", re.IGNORECASE)
_CHOICE_CHARS = 120
# What any pick asks for: the item itself, no preamble about which number it was.
_GO_ON = (
    "Go straight on with the one it means; never open by naming its number or saying which "
    "one was picked, and never ask what the number means."
)


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


def _offered_choices(reply: str) -> list[str]:
    """The choices the question ``reply`` ends on offers, in its order, or none.

    "Want to do the periodic table link properly (groups, periods and why they matter), or
    jump to a mixed exam-style set?" offers two: an aside in brackets is part of its choice.
    """
    match = _CLOSING_QUESTION.search(reply.rstrip()[-_TAIL_CHARS:])
    if match is None or _WHICH.search(match["question"]):
        return []
    question = _ASIDE.sub("", _MARKUP.sub(lambda m: m["text"] or "", match["question"]))
    head, joined, last = question.rstrip("? ").rpartition(" or ")
    if not joined:
        return []
    choices = [part.strip(" ,") for part in (*head.split(", "), last)]
    if len(choices) < 2 or not all(0 < len(choice) <= _CHOICE_CHARS for choice in choices):
        return []
    return choices


def list_reference_hint(query: str, prior: Sequence[tuple[str, str]]) -> str | None:
    """The note naming the items a short message may point at, or None.

    The lists of the last few replies, newest first: "4 from ur first list" got item 5 of
    the newest one, invented, when the reply just before had no list (2026-11-06). After a
    reply that ends on a question offering choices, a pick picks among them first."""
    if len(query.split()) > _SHORT_WORDS or _SUM.search(query):
        return None
    replies = [text for role, text in reversed(prior) if role == "assistant"][:_REPLIES]
    lists = [items for items in map(_items, replies) if len(items) >= 2][:_LISTS]
    named: list[str] = []
    for place, items in zip(_LIST_NAMES, lists, strict=False):
        named += [
            f'item {n} of {place} is "{_plain(items[n - 1])}"' for n in _pointed(query, len(items))
        ]
    choices = _offered_choices(replies[0]) if replies else []
    picked = _pointed(query, len(choices))
    if picked:
        offered = "; ".join(f'choice {n} is "{choices[n - 1]}"' for n in picked)
        other = (
            " But when one of those choices offers to go on with an item of a list above it, a "
            f"number or place may name that item instead: {'; '.join(named)}. Decide from the "
            "question which it means."
            if named
            else ""
        )
        listed = "; ".join(f"({n}) {choice}" for n, choice in enumerate(choices, 1))
        return (
            f"Your last reply ended on a question offering choices: {listed}. If this message "
            f"picks one by its number or place, it picks that choice: {offered}.{other} {_GO_ON}"
        )
    if not named:
        return None
    return (
        "If this message points at an item of a list you gave, by its number or its place, "
        f"it asks about that item: {'; '.join(named)}. {_GO_ON}"
    )
