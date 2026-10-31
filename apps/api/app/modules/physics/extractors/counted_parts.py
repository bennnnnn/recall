"""Circuit parts a question counts: "two resistors", "three identical 1.5 V cells".

One value stated for several parts ("two resistors, each 10 Ω", "two 1.5 V cells", "two
capacitors of 10 µF each") is that value in every part. Read as one part, two 10 Ω resistors
in parallel across 5 V drew 0.5 A, not 1 A, and two 1.5 V cells drove half their current
(2026-10-31, the model reader's translated questions read back in English). The resistor
network readers repeat the value; every other solve of a question with a counted part it
cannot account for is refused at the claim check (``accounts_for_counted_parts``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.physics.extractors.unit_patterns import NUMBER
from app.services.number_text import count_word_pattern, number_word_value

_OHMS = r"(?:k|M)?(?:ohms?|Ω)"
_VOLTS = r"(?:k|m)?(?:V|volts?)"
_FARADS = r"(?:m|u|µ|μ|n|p)?(?:F|farads?)|(?:milli|micro|nano|pico)farads?"
_WATTS = r"(?:k)?(?:W|watts?)"
# Each counted noun, the part it is and the unit that part's value is stated in.
_PARTS = {
    "resistors": ("resistor", _OHMS),
    "resistances": ("resistor", _OHMS),
    "cells": ("cell", _VOLTS),
    "batteries": ("cell", _VOLTS),
    "capacitors": ("capacitor", _FARADS),
    "bulbs": ("lamp", _WATTS),
    "lamps": ("lamp", _WATTS),
}
_PART_UNITS = dict(_PARTS.values())
_ANY_UNIT = "|".join(sorted(set(_PART_UNITS.values())))
_NOUNS = "|".join(_PARTS)
_COUNT = rf"{count_word_pattern(low=2, high=12)}|(?<![\d.])(?:[2-9]|1[0-2])(?![\d.])"
_SAME = r"(?:identical|equal|similar)\s+"
# "two resistors", "each of the three resistors", "two identical 6 Ω resistors", "a pair of
# 1.5 V cells", "both capacitors".
_PART_COUNT_RE = re.compile(
    rf"\b(?:(?P<count>{_COUNT})|(?P<pair>a\s+pair\s+of|both(?:\s+the)?))\s+(?P<same>{_SAME})?"
    rf"(?:(?P<value>{NUMBER})\s*-?\s*(?:{_ANY_UNIT})(?![A-Za-z0-9])\s+(?:{_SAME})?)?"
    rf"(?P<noun>{_NOUNS})\b",
    re.IGNORECASE,
)
# A plural part with no count: "resistors of 10 Ω each". How many is not said.
_UNCOUNTED_RE = re.compile(rf"\b(?P<noun>{_NOUNS})\b", re.IGNORECASE)
# "each" before a value in its own clause: "each 10 Ω", "each with a resistance of 10 Ω",
# "each of the two resistors has a resistance of 10 Ω".
_EACH_BEFORE = re.compile(r"\beach\b[^\d.;:?!\n]{0,60}\Z", re.IGNORECASE)
_EACH_AFTER = re.compile(r"\s+each\b", re.IGNORECASE)
# A value written straight after identical parts: "three identical resistors of 6 Ω".
_ATTACHED = r"\s*,?\s*(?:of\s+|with\s+|rated\s+(?:at\s+)?)?"


@dataclass(frozen=True)
class CountedPart:
    """A part the question counts; ``count`` None when it says "each" but not how many."""

    part: str
    count: int | None
    # The one value stated for every part, as written (in its own unit).
    each: float | None


def _values(text: str, unit: str) -> list[re.Match[str]]:
    return list(re.finditer(rf"({NUMBER})\s*-?\s*(?:{unit})(?![A-Za-z0-9])", text, re.IGNORECASE))


def stated_values(text: str, part: str) -> list[float]:
    """Every value written in the part's unit ("10 Ω", "10-ohm", "4.7 kΩ" for a resistor)."""
    return [float(match.group(1)) for match in _values(text, _PART_UNITS[part])]


def _each_values(text: str, unit: str) -> set[float]:
    """The values "each" is said of: "each 10 Ω", "10 Ω each"."""
    return {
        float(match.group(1))
        for match in _values(text, unit)
        if _EACH_BEFORE.search(text[max(0, match.start() - 60) : match.start()])
        or _EACH_AFTER.match(text, match.end())
    }


def _count(match: re.Match[str]) -> int:
    if match.group("pair"):
        return 2
    word = match.group("count")
    return int(word) if word.isdigit() else number_word_value(word) or 0


def _each_value(text: str, match: re.Match[str], unit: str) -> float | None:
    """The value every counted part has, or None when the question does not say one."""
    if match.group("value"):
        return float(match.group("value"))
    each = _each_values(text, unit)
    if len(each) == 1:
        return each.pop()
    if match.group("same"):
        attached = re.match(
            rf"{_ATTACHED}({NUMBER})\s*-?\s*(?:{unit})(?![A-Za-z0-9])",
            text[match.end() :],
            re.IGNORECASE,
        )
        if attached is not None:
            return float(attached.group(1))
    return None


def counted_parts(text: str) -> list[CountedPart]:
    """Every part the question counts, and the value each has when one is stated for all."""
    found: list[CountedPart] = []
    counted_nouns: set[str] = set()
    for match in _PART_COUNT_RE.finditer(text):
        part, unit = _PARTS[match.group("noun").lower()]
        counted_nouns.add(part)
        found.append(CountedPart(part, _count(match), _each_value(text, match, unit)))
    for match in _UNCOUNTED_RE.finditer(text):
        part, unit = _PARTS[match.group("noun").lower()]
        if part not in counted_nouns and _each_values(text, unit):
            counted_nouns.add(part)
            found.append(CountedPart(part, None, None))
    return found


def unread_parts(text: str) -> frozenset[str]:
    """The counted parts a one-value reader would read as one: a value stated for all of
    them, fewer values than parts, or "each" with no count."""
    unread: set[str] = set()
    for counted in counted_parts(text):
        stated = len(stated_values(text, counted.part))
        if counted.count is None or counted.each is not None or 0 < stated < counted.count:
            unread.add(counted.part)
    return frozenset(unread)


# The solves that repeat a counted resistor's value into the network they read.
_NETWORK_OPS = frozenset(
    {
        "series_resistance",
        "parallel_resistance",
        "series_current",
        "parallel_current",
        "series_parallel_resistance",
        "series_parallel_current",
    }
)


def accounts_for_counted_parts(op: str | None, text: str) -> bool:
    """Whether a solve of ``op`` reads every part the question counts.

    Every reader's solve passes here, so "two 60 W bulbs" is never one bulb's energy in
    the law binder either. Only a resistor network repeats a value into its parts.
    """
    unread = unread_parts(text)
    return not unread or (unread == {"resistor"} and op in _NETWORK_OPS)
