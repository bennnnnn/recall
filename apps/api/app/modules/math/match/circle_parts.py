"""The part of a circle a question measures, and a fraction said of any measure.

"The area of the quarter circle of radius 8 cm" is a quarter of that circle: the circle
reader took the radius and answered the whole circle, 201.06 cm² for 50.24 (2026-11-13).
A part is a fraction said of the circle, before it ("quarter circle", "three-quarter
circle", "1/4 circle", "semicircle") or as what is taken of it ("a quarter of a circle",
"two thirds of the circle"), and a quadrant is a quarter. Any other piece named of a
circle ("a segment of a circle", "an arc of the circle") is a region the circle readers
do not measure. A fraction taken of anything else ("a quarter of the area", "a third of
its length") states a measure through another, which no shape reader reads as printed.

A fraction is read as English writes one: digits (1/4), a fraction sign (¾), or words
(a quarter, three-quarter, two thirds); the words are the number grammar, not a phrase
list.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from fractions import Fraction

from app.services.number_text import count_word_pattern, number_word_value

# The denominators English names: "a third", "three quarters", "one eighth".
_DENOMINATOR_WORDS: dict[str, int] = {
    "half": 2, "halves": 2, "third": 3, "quarter": 4, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
}  # fmt: skip
_ORDINALS = sorted((w for w in _DENOMINATOR_WORDS if w not in {"half", "halves"}), key=len)
_DENOMINATOR = rf"(?P<den>halves|half|(?:{'|'.join(reversed(_ORDINALS))})s?)"
_NUMERATOR = rf"(?:(?P<num>a|an|{count_word_pattern(low=1, high=12)}|\d+)[\s-]+)?"
# The fraction signs a keyboard types: ½, ¾, ⅓, ⅛ …
VULGAR_FRACTIONS = "".join(chr(c) for c in (0xBC, 0xBD, 0xBE, *range(0x2150, 0x215F)))
_FRACTION = (
    rf"(?:(?P<top>\d+)\s*/\s*(?P<bottom>\d+)|(?P<glyph>[{VULGAR_FRACTIONS}])"
    rf"|\b{_NUMERATOR}{_DENOMINATOR})"
)
_DETERMINER = r"(?:(?:a|an|the|this|that|one|its|each|given)\s+)?"
# "quarter circle", "three-quarter-circle", "¾ circle", "semicircle", "semi-circle".
_BEFORE = re.compile(rf"{_FRACTION}[\s-]*(?=circles?\b)|\bsemi[\s-]*(?=circles?\b)", re.I)
# "a quarter of a circle", "two thirds of the circle", "1/4 of a circle", "half a circle".
_OF_CIRCLE = re.compile(
    rf"{_FRACTION}\s+of\s+{_DETERMINER}(?=circles?\b)|\bhalf\s+(?:a|an|the)\s+(?=circle\b)", re.I
)
# A quadrant is the circle's quarter.
_QUADRANT = re.compile(r"\bquadrants?\b(?:\s+of\s+(?:a|an|the|this|that)?\s*(?=circles?\b))?", re.I)
# "a quarter of the area", "a third of its length": a fraction taken of a measure; "to the
# nearest tenth of a centimetre" is a rounding.
_FRACTION_OF = re.compile(rf"(?<!nearest ){_FRACTION}\s+of\b", re.I)
# The piece a question names "of" the circle: "the area of a circle", "an arc of the circle".
_PIECE_OF_CIRCLE = re.compile(rf"\b(?P<piece>[a-z]+)\s+of\s+{_DETERMINER}circles?\b", re.I)
# What the circle readers measure of a whole circle; anything else named of it is another region.
_CIRCLE_MEASURES = frozenset(
    "area circumference perimeter radius radii diameter centre center chord equation length"
    " measure measures size".split()
)


@dataclass(frozen=True)
class CirclePart:
    """A fraction of a circle, and the words that say it (taken out of the question
    before another reader looks for a "half" it would read as a relation)."""

    fraction: Fraction
    start: int
    end: int


def _fraction(match: re.Match[str]) -> Fraction | None:
    groups = match.groupdict()
    if groups.get("top") is not None:
        bottom = int(groups["bottom"])
        return Fraction(int(groups["top"]), bottom) if bottom else None
    if groups.get("glyph") is not None:
        return Fraction(unicodedata.numeric(groups["glyph"])).limit_denominator(12)
    if groups.get("den") is None:
        return Fraction(1, 2)  # "semi"
    word = groups["den"].lower()
    bottom = _DENOMINATOR_WORDS.get(word) or _DENOMINATOR_WORDS[word.removesuffix("s")]
    said = (groups.get("num") or "a").lower()
    top = 1 if said in {"a", "an"} else (number_word_value(said) or int(said))
    return Fraction(top, bottom)


def circle_part(text: str) -> CirclePart | None:
    """The fraction of a circle the question names, when it names one below a whole.

    A question naming two different parts ("a semicircle on a quarter circle") is no one
    part; it comes back as the first, and ``circle_parts`` lets a reader tell.
    """
    parts = circle_parts(text)
    return parts[0] if parts else None


def _ordinal(match: re.Match[str]) -> bool:
    """ "A third circle" before its noun is the circle after the second; only a half and a
    quarter, or a fraction with its count ("two-thirds"), name a part there."""
    word = (match.groupdict().get("den") or "").lower().removesuffix("s")
    said = (match.groupdict().get("num") or "a").lower()
    return word not in {"", "half", "halve", "quarter"} and said in {"a", "an"}


def circle_parts(text: str) -> list[CirclePart]:
    """Every part of a circle the question names, in order."""
    found: list[CirclePart] = []
    for pattern in (_OF_CIRCLE, _BEFORE):
        for match in pattern.finditer(text):
            if any(part.start <= match.start() < part.end for part in found):
                continue
            if pattern is _BEFORE and _ordinal(match):
                continue
            fraction = _fraction(match)
            if fraction is not None and 0 < fraction < 1:
                found.append(CirclePart(fraction, match.start(), match.end()))
    for match in _QUADRANT.finditer(text):
        found.append(CirclePart(Fraction(1, 4), match.start(), match.end()))
    return sorted(found, key=lambda part: part.start)


def other_piece_of_circle(text: str) -> bool:
    """A region named of a circle that is neither the circle nor a fraction of it:
    "the area of a segment of a circle", "the length of an arc of the circle"."""
    parted = circle_parts(text)
    for match in _PIECE_OF_CIRCLE.finditer(text):
        if any(part.start <= match.start() < part.end for part in parted):
            continue
        if match.group("piece").lower() not in _CIRCLE_MEASURES:
            return True
    return False


# Any fraction a question says, attached to the circle or not: "a circle's quarter", "with a
# quarter missing", "50% of", "a semicircle".
_ANY_FRACTION = re.compile(rf"{_FRACTION}|\bsemi|\bquadrants?\b|%|\bper\s*cent\b", re.I)


def fraction_named(text: str) -> bool:
    """The question says a fraction somewhere."""
    return _ANY_FRACTION.search(text) is not None


def fraction_taken_of(text: str) -> bool:
    """A fraction taken of something ("a quarter of the area", "1/2 of its base")."""
    return _FRACTION_OF.search(text) is not None


# The side of a sector or an arc a question names: the major one goes round the rest of the
# circle from the angle it states, the minor one is that angle's.
_MAJOR = re.compile(r"\b(?:major|larger|bigger|greater)\s+(?:sectors?|arcs?)\b", re.I)
_MINOR = re.compile(r"\b(?:minor|smaller|lesser)\s+(?:sectors?|arcs?)\b", re.I)


def named_sector_angle(text: str, angle: float | None) -> float | None:
    """The angle of the sector the question measures: "the major sector" of a 60° angle is
    the 300° one (its card was the 60° sector's 25.67 cm² for 128.33, 2026-11-13). Naming
    both sides is no one sector."""
    major, minor = _MAJOR.search(text) is not None, _MINOR.search(text) is not None
    if angle is None or (major and minor):
        return None
    if (major and angle < 180) or (minor and angle > 180):
        return 360 - angle
    return angle


def without_circle_part(text: str, part: CirclePart) -> str:
    return f"{text[: part.start]} {text[part.end :]}"
