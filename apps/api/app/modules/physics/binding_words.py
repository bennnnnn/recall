"""The words around a stated value, which say which input of a law it fills.

The binder reads a question's values by dimension; these helpers read the
words: the phrase before a value ("from 10 m/s", "reaches 18 m/s"), the
phrase after it ("100 turns on the primary"), the asked phrase, and words
that state a value without a number ("from rest").
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.modules.physics.catalog.spec import Binding, VariableSpec

_SENTENCE_BREAK = re.compile(r"[.;?!](?:\s|$)")
# An asked phrase followed by its own value labels a given: "an acceleration of 2".
_LABELLED = re.compile(r"\s*(?:of|=|is|:|was)?\s*[-+]?\.?\d")


@lru_cache(maxsize=1024)
def word_pattern(phrase: str) -> re.Pattern[str]:
    # A leading word boundary only: "climb" names "climbs", "accelerat" both forms.
    return re.compile(rf"(?<![\w]){re.escape(phrase)}")


def last_said(window: str, words: tuple[str, ...]) -> int:
    """Where the last of these words ends in the window; -1 when none is there."""
    ends = [match.end() for word in words for match in word_pattern(word).finditer(window)]
    return max(ends, default=-1)


def first_said(window: str, words: tuple[str, ...]) -> int:
    """Where the first of these words starts in the window; -1 when none is there."""
    starts = [match.start() for word in words for match in word_pattern(word).finditer(window)]
    return min(starts, default=-1)


def words_before(lower: str, start: int, end: int) -> str:
    """The words before a value, back to the previous value or sentence."""
    breaks = [match.end() for match in _SENTENCE_BREAK.finditer(lower, start, end)]
    return lower[max([start, *breaks]) : end]


def words_after(lower: str, start: int, end: int) -> str:
    """The words after a value, up to the next value or the end of its sentence."""
    stop = _SENTENCE_BREAK.search(lower, start, end)
    return lower[start : stop.start() if stop is not None else end]


def ask_strength(clause: str, asks: tuple[str, ...]) -> int:
    """The longest asked phrase this clause names, not counting a given's label."""
    strength = 0
    for phrase in asks:
        for match in word_pattern(phrase).finditer(clause):
            if not _LABELLED.match(clause, match.end()):
                strength = max(strength, len(phrase))
    return strength


def choose(
    options: list[VariableSpec],
    before: str,
    after: str,
    binding: Binding,
    is_result_kind: bool,
    *,
    listed: bool = False,
) -> VariableSpec | None:
    """The input this value fills, or None when the words do not say.

    The words just before a value name it ("from 10 m/s"); when none do, the
    words just after it can ("100 turns on the primary"). In a list read
    "respectively", the words before the first value name every value, so
    only inputs the law fills in stated order can take them.
    """
    ordered = all(
        option.name in (*binding.descending, *binding.interchangeable) for option in options
    )
    if listed and len(options) > 1:
        return options[0] if ordered else None
    said = [(last_said(before, option.words), option) for option in options]
    latest = max(position for position, _ in said)
    if is_result_kind and last_said(before, binding.result_words) > latest:
        # "reaches 18 m/s" while the final speed is asked: that is the answer.
        return None
    if latest >= 0:
        named = [option for position, option in said if position == latest]
        return named[0] if len(named) == 1 else None
    if len(options) > 1:
        later = [(first_said(after, option.words), option) for option in options]
        found = [(position, option) for position, option in later if position >= 0]
        if found:
            nearest = min(position for position, _ in found)
            named = [option for position, option in found if position == nearest]
            return named[0] if len(named) == 1 else None
    if len(options) == 1 or ordered:
        return options[0]
    return None


def implied_value(variable: VariableSpec, lower: str) -> float | None:
    """A value the words state without a number: "from rest", "horizontally"."""
    for phrase, value in variable.implied:
        if word_pattern(phrase).search(lower):
            return value
    return None
