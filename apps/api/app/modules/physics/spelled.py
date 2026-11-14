"""A quantity written in words is never read: the question declines.

A reader that sees only digits skips "ten metres" and binds whatever value of that kind it
can see: "A ball is dropped from ten metres onto a 1 m table" fell 1 m. Reading words as
numbers went wrong in more ways than it went right ("1.5 thousand metres" was 1000 m,
"two point five metres" 5 m, "one second later" a time of the fall), so a number in words,
a scale word or a fraction word beside a unit or a quantity marks the question unread, and
it is left to the model.

Not a quantity: an ordinal or a pronoun ("a second ball", "the one on the left"), a count
of turns or cycles ("one turn every 2 s"), which measures nothing.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from app.services.number_text import NUMBER_WORDS
from app.services.text_match import after_spaces

_NUMBER_WORD = "|".join(
    sorted((*NUMBER_WORDS, "hundred", "thousand", "million", "billion"), key=len, reverse=True)
)
_FRACTION_WORD = r"half|quarters?|thirds?|few|several|couple"
# A spelled amount: "ten", "twenty-five", "two point five", "one and a half", "half a",
# "three quarters of a", and a digit with a scale word ("1.5 thousand").
_SPELLED = re.compile(
    rf"(?<![\w-])(?:(?:{_NUMBER_WORD}|{_FRACTION_WORD})(?![\w])"
    rf"|(?<![\d.])\d+(?:\.\d+)?\s*(?:hundred|thousand|million|billion)(?![\w]))"
    rf"(?:(?:\s+|-)(?:and|point|of|an?|{_NUMBER_WORD}|{_FRACTION_WORD})(?![\w]))*",
    re.IGNORECASE,
)
# What a spelled amount may measure besides a unit the table reads: "half a lap", "half the
# distance".
# "half the time and 60 km/h for the other half" is a trip's shape, not an amount; "half the
# distance of 100 m" is one.
# Each is read after a hyphen or after the spaces before it (``_quantity_words``), so neither
# starts with a run of spaces (CodeQL py/polynomial-redos).
_QUANTITY_WORDS = re.compile(r"(?:(?:of\s+)?an?\s+)?(?:laps?|metres?|meters?|seconds?)\b", re.I)
_SHARE_OF_QUANTITY = re.compile(
    r"(?:of\s+)?(?:the|its|his|her|their)\s+(?:distance|way|journey|trip|length|height"
    r"|time|mass|volume)\s+(?:of\s+)?\d",
    re.IGNORECASE,
)
# "the one on the left", "one of the", "no one": "one" names a thing here.
_PRONOUN_ONE = re.compile(r"(?<![\w-])one\s+(?:of|on|in|at|with|that|which|who|is|and|or)\b", re.I)


def _quantity_words(text: str, end: int) -> bool:
    """ "-lap", " a lap", " of the distance of 100": a quantity a spelled amount measures."""
    if text.startswith("-", end):
        return _QUANTITY_WORDS.match(text, end + 1) is not None
    start = after_spaces(text, end)
    if start == end:
        return False
    return bool(_QUANTITY_WORDS.match(text, start) or _SHARE_OF_QUANTITY.match(text, start))


def has_unread_quantity(text: str, unit_at: Callable[[str, int], object | None]) -> bool:
    """A number in words, a scale word or a fraction word stands beside a unit."""
    for match in _SPELLED.finditer(text):
        end = match.end()
        if match.group()[0].isdigit():
            return True  # "1.2 million": a scale word on a digit is never read
        if _PRONOUN_ONE.match(text, match.start()):
            continue
        following = end + 1 if text.startswith(("-", " "), end) else end
        if unit_at(text, following) is not None or _quantity_words(text, end):
            return True
    return False
