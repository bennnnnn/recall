"""Counted items and the value each has (``verified_numbers``)."""

from __future__ import annotations

import re
from collections.abc import Iterator

from app.services.verified_numbers.numbers import Quantity, close, is_read

# Counts: number words to a million, read by a bounded parser ("twenty-one", "a hundred").
_ONES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}  # fmt: skip
_WORD = "|".join(sorted([*_ONES, "hundred", "thousand"], key=len, reverse=True))
_COUNT_WORDS = rf"(?:a\s+(?:hundred|thousand)|{_WORD})(?:[\s-]{{1,3}}(?:and\s+)?(?:{_WORD})){{0,6}}"
_INSIDE = r"(?P<inside>-?\d[\d.,]{0,20}[ \t]{0,3}-?[ \t]{0,3}[^\s\d]{1,12}[ \t]{1,3})?"
_NOUN = r"(?P<noun>[A-Za-z]{3,20})\b"
_DETERMINERS = r"(?:identical|equal|similar|of\s+(?:the|my|these|those|our|your|their))"
# A count, its items and, when written inside the phrase, the value each has: "two
# resistors", "both of my phones", "thirty 60 W bulbs", "3 identical 9 Ω resistors".
COUNT = re.compile(
    rf"(?<![\d.,^\w-])(?P<count>{_COUNT_WORDS}|\d{{1,7}}(?![\d.,])|a\s+(?:pair|couple)\s+of|both|a\s+dozen)"
    rf"[ \t]{{1,3}}(?:{_DETERMINERS}[ \t]{{1,3}})?{_INSIDE}{_NOUN}",
    re.IGNORECASE,
)
VAGUE = re.compile(
    rf"(?<!how\s)(?<!as\s)\b(?P<count>several|many|numerous|multiple|a\s+few|various)"
    rf"[ \t]{{1,3}}{_INSIDE}{_NOUN}",
    re.IGNORECASE,
)
# Words after a count that name no items: prepositions, adverbs, conjunctions, articles
# and comparatives ("two of", "5 away from", "two more", "two times").
_NOT_ITEMS = frozenset(
    "and or but of more less than times plus minus equals to in at on for from by with into "
    "onto over under up down off out away about around after before per each is are was "
    "were be the a an this that these those it its they them their".split()
)
# A determiner then a word or a number: another noun's phrase ("a cart", "a 50 kg box").
_OTHER_NOUN = re.compile(
    r"\b(?:a|an|the|its|their|his|her|another|this|that)\s+(?:\d|(?P<word>[a-z]{1,20}))"
)
# Phrases that name a quantity rather than a thing: "with a force of 400 N".
_QUANTITY_NOUNS = frozenset(
    "force power mass weight resistance voltage emf charge speed velocity current "
    "capacitance rating energy pressure temperature volume".split()
)
_ATTRIBUTIVE = re.compile(
    r"\b(?:a|an|the|its|their|another|this|that)\s+(?:[a-z]{1,20}\s+)?\Z", re.IGNORECASE
)
_TOTAL = re.compile(
    r"\b(?:total|together|combined|altogether|in\s+all|between\s+them|net|joint)\b",
    re.IGNORECASE,
)
_ONE_ITEM = re.compile(r"\b(?:each|one|per|every|either|a\s+single|single)\s+", re.IGNORECASE)
_IRREGULAR = {"people": "person", "men": "man", "women": "woman", "children": "child"}
_CLAUSE_END = re.compile(r"[.,;:?!](?=\s|$)")
_SENTENCE_END = re.compile(r"[.;?!](?=\s|$)")


def count_value(written: str) -> int | None:
    """A count as written, digits or words ("twenty-one", "a hundred"); None for none."""
    lower = written.lower()
    if lower.isdigit():
        return int(lower)
    if lower.startswith(("a pair", "a couple", "both")):
        return 2
    if lower == "a dozen":
        return 12
    total = current = 0
    for word in re.findall(r"[a-z]+", lower):
        if word in _ONES:
            current += _ONES[word]
        elif word == "hundred":
            current = (current or 1) * 100
        elif word == "thousand":
            total += (current or 1) * 1000
            current = 0
    return total + current or None


def _description(plain: str, end: int) -> tuple[int, int]:
    """The words after counted items that may say what each has, to the clause's end; an
    appositive set off by a comma counts ("Two horses, each pulling with 400 N, ...")."""
    leading = re.match(r"[ \t]{0,3},[ \t]{0,3}", plain[end : end + 8])
    start = end + (leading.end() if leading else 0)
    stop = _CLAUSE_END.search(plain, start)
    return start, stop.start() if stop else len(plain)


def _sentence(plain: str, at: int) -> tuple[int, int]:
    ends = [0, *(found.end() for found in _SENTENCE_END.finditer(plain)), len(plain)]
    return max(edge for edge in ends if edge <= at), min(edge for edge in ends if edge > at)


def each_value(plain: str, match: re.Match[str], stated: list[Quantity]) -> Quantity | None:
    """The value each counted item has, or None: the count holds the card only then.

    Written inside the count ("thirty 60 W bulbs"); said with "each" ("each pulling with
    400 N", "10 Ω each"); or the items' own attribute or rate, with no other noun before it
    ("both of my phones charge at 20 W", "the bulbs are rated 60 W"). Not a value of
    another noun ("pull a cart with 400 N", "lift a 60 kg crate 2 m"), one the sentence
    calls a total, or a gap between the items ("two plates 2 cm apart")."""
    if match.group("inside"):
        inside = match.start("inside")
        return next((item for item in stated if item.start == inside), None)
    sentence = _sentence(plain, match.start())
    if _TOTAL.search(plain, sentence[0], sentence[1]):
        return None
    start, stop = _description(plain, match.end())
    candidates = [
        item
        for item in stated
        if start <= item.start < stop
        and not _ATTRIBUTIVE.search(plain[max(0, item.start - 30) : item.start])
    ]
    if not candidates:
        return None
    first = candidates[0]
    if re.match(r"[ \t]{0,3}\S{1,12}[ \t]{1,3}apart\b", plain[first.end : first.end + 24]):
        return None
    between = plain[start : first.start].lower()
    after = plain[first.end : first.end + 24].lower()
    if re.search(r"\beach\b", between) or re.match(r"[ \t]{0,3}\S{0,12}[ \t]{0,3}each\b", after):
        return first
    for other in _OTHER_NOUN.finditer(between):
        if other.group("word") not in _QUANTITY_NOUNS:
            return None
    return first


def asks_one_item(plain: str, noun: str) -> bool:
    """Whether the question asks about one of the counted items ("the energy used by each
    bulb", "how much does one phone use"): then the count is no input."""
    lower = noun.lower()
    one = _IRREGULAR.get(lower) or re.sub(r"(?:es|s)$", "", lower)
    ask = plain[_sentence(plain, max(0, len(plain) - 1))[0] :].lower()
    if re.search(r"\beach\s+(?:one|of\s+them)\b|\b(?:by|for|of)\s+each\b", ask):
        return True
    return any(
        re.match(
            rf"(?:of\s+(?:the|them|these)\s+)?(?:[a-z]{{1,20}}\s+)?{re.escape(one)}",
            ask[m.end() :],
        )
        for m in _ONE_ITEM.finditer(ask)
    )


def count_read(
    plain: str, match: re.Match[str], count: int, stated: list[Quantity], read: list[Quantity]
) -> bool:
    """Whether a count is read: no value each, a question about one item, the value bound
    once per item, that many values of its kind listed and read, or the count an input."""
    each = each_value(plain, match, stated)
    if each is None or each.dimension is None or asks_one_item(plain, match.group("noun")):
        return True
    bound = sum(
        1
        for other in read
        if other.dimension == each.dimension and close(other.si or 0.0, each.si or 0.0)
    )
    # "Three resistors of 4 Ω, 6 Ω and 10 Ω": a list of the kind, one value per item.
    sentence = _sentence(plain, match.start())
    listed = [
        item
        for item in stated
        if match.end() <= item.start < sentence[1]
        and item.dimension == each.dimension
        and is_read(item, read)
    ]
    if bound >= count or len(listed) >= count:
        return True
    # "Seven notebooks at $2 each": the count read as an input itself, compared exactly.
    unitless = [other for other in read if other.dimension is None]
    written = sum(
        1
        for item in stated
        if item.dimension is None and item.value == count and item.start != match.start("count")
    )
    return sum(1 for other in unitless if other.value == count) > written


def items(plain: str, pattern: re.Pattern[str]) -> Iterator[re.Match[str]]:
    """Counts whose items are things: not "two of", "two hours" (a unit), "two more"."""
    from app.modules.physics.givens import PHYSICS_UNITS

    for match in pattern.finditer(plain):
        noun = match.group("noun").lower()
        if noun in _NOT_ITEMS or PHYSICS_UNITS.at(plain, match.start("noun") - 1) is not None:
            continue
        yield match
