"""The rule for a part of a circle, or a circle worked with the π its question gives.

It reads one measure (area, perimeter, circumference or arc length), the one radius or
diameter it is of, the part (a semicircle, a quarter circle, a quadrant, or a sector's
angle when π is stated), the π and the rounding the question asks for. Every number and
count the question holds must be one of those: a semicircle on a rectangle is a composite
shape, and two semicircles are not one, so neither is read.

The intent carries the reading in ``stats_numbers`` (``circles.Reading`` reads it
back) and the measure, radius or diameter and unit in ``trial_outcome``.
"""

from __future__ import annotations

import re
import unicodedata
from fractions import Fraction

from app.modules.math.match.circle_parts import (
    VULGAR_FRACTIONS,
    CirclePart,
    circle_parts,
    fraction_named,
    named_sector_angle,
    other_piece_of_circle,
)
from app.modules.math.match.measure_relations import another_shape_named
from app.modules.math.match.stated_pi import stated_pi
from app.modules.math.schemas import MathIntent
from app.services.number_text import count_word_pattern, number_word_value
from app.services.unit_text import LENGTH_UNITS

_N = r"(\d+(?:\.\d+)?)"
_ASKED = re.compile(r"\b(area|perimeter|circumference|arc\s+length)\b", re.I)
# "radius 3½ cm": a mixed number is read whole. "in" is a unit only where no word follows:
# "radius 7 in the figure" has no inches.
_SIZE = re.compile(
    r"\b(?P<kind>radius|diameter)\s*(?:of\s+(?:(?:a|an|the|this|its)\s+)?"
    r"(?:circle|semi-?circle|quadrant|sector)\s+)?(?:of\s+|is\s+|=\s*|:\s*)?"
    rf"(?P<whole>\d+(?:\.\d+)?)(?P<part>[{VULGAR_FRACTIONS}])?(?:\s*(?P<unit>mm|cm|km|m|ft"
    r"|in(?![ \t]*[a-z])|(?:milli|centi|kilo)?met(?:er|re)s?|inch(?:es)?|f(?:oo|ee)t)\b)?",
    re.I,
)
# An answer asked in a unit: "in square metres", "in mm".
_ASKED_UNIT = re.compile(r"\bin\s+(?:(?:square|sq\.?|cubic)\s+)?([a-z]+)", re.I)
# The perimeter of the curved part is the arc; one "excluding the diameter" is narrowed in
# words this rule does not read, and a chord or a segment bounds another region.
_CURVED = re.compile(r"\bcurved\b", re.I)
_NARROWED = re.compile(
    r"\b(?:excluding|excludes?|without|except|not\s+including|apart\s+from|other\s+than"
    r"|chords?|segments?|between)\b",
    re.I,
)
_CIRCLE = re.compile(r"\bcircle\b", re.I)
_CIRCLES = re.compile(r"\bcircles?\b", re.I)
# "a sector of a circle", "a quadrant of the circle": the circle the part is cut from.
_OWN_CIRCLE = re.compile(r"\b(?:sectors?|quadrants?)\s+of\s+(?:(?:a|an|the|this|that)\s+)?$", re.I)
# What is left of a figure when the part is gone: another region than the part.
_REMAINDER = re.compile(
    r"\b(?:left|remain\w*|rest|still|missing|loses?|lost|eaten|outside"
    r"|not\s+(?:covered|in|inside|shaded|painted)|un[a-z]+ed)\b",
    re.I,
)
_SECTOR = re.compile(r"\bsectors?\b", re.I)
_DEGREES = re.compile(rf"{_N}\s*(?:\u00b0|\^\s*\\circ|degrees?\b)", re.I)
_COUNT = count_word_pattern(low=1, high=12)
# "to three significant digits", "correct to 2 decimal places", "to the nearest tenth".
_ROUNDING = re.compile(
    rf"\b(?:to|in|correct\s+to)\s+(?:(?P<count>\d+|{_COUNT})\s+(?:(?P<figures>significant"
    r"\s+(?:figures?|digits?)|s\.?\s?f\.?)|(?P<places>decimal\s+places?|d\.?\s?p\.?))"
    r"|the\s+nearest\s+(?P<nearest>whole\s+number|integer|tenth|hundredth|thousandth))(?![a-z])",
    re.I,
)
_NEAREST = {"whole number": 0, "integer": 0, "tenth": 1, "hundredth": 2, "thousandth": 3}
# A count or a number the rule has not read: a second shape, a second part, a total.
_UNREAD = re.compile(rf"\d|\b(?:{count_word_pattern(low=0, high=90)})\b|\bcircles\b", re.I)
# A measure the rule did not read to its end: "radius 10π", "radius 3/2", "radius 3 1/2".
_MORE_AFTER = re.compile(
    rf"\s*(?:[*/^\u00d7\u00b7\u03c0{VULGAR_FRACTIONS}]|\d|pi\b|sqrt|\u221a)", re.I
)


def _rounding(text: str) -> tuple[int, int, tuple[int, int] | None]:
    """(significant figures, decimal places, the span that asks) — 0, -1 for neither."""
    found = _ROUNDING.search(text)
    if found is None:
        return 0, -1, None
    span = (found.start(), found.end())
    if found.group("nearest"):
        return 0, _NEAREST[" ".join(found.group("nearest").lower().split())], span
    said = found.group("count").lower()
    count = int(said) if said.isdigit() else number_word_value(said) or 0
    return (count, -1, span) if found.group("figures") else (0, count, span)


def _sector_part(text: str, has_pi: bool) -> tuple[Fraction, float, tuple[int, int]] | None:
    """A sector's share of its circle from its one angle; only with a stated π, since
    the sector solver works a sector with π itself."""
    angles = list(_DEGREES.finditer(text))
    if not has_pi or not _SECTOR.search(text) or len(angles) != 1:
        return None
    stated = Fraction(angles[0].group(1))
    named = named_sector_angle(text, float(stated))  # "the major sector" goes round the rest
    if named is None or not 0 < named < 360:
        return None
    angle = stated if named == float(stated) else 360 - stated
    return angle / 360, float(angle), (angles[0].start(), angles[0].end())


def _second_figure(text: str, parts: list[CirclePart]) -> bool:
    """A circle named as a figure of its own beside the part: "a quadrant is cut from a
    circle of radius 14 cm" is two figures (a checked 154 for the 462 left, 2026-11-13).
    The part's own circle is the one its words govern: "quarter circle", "a quarter of a
    circle", "a sector of a circle"."""
    for found in _CIRCLES.finditer(text):
        if any(part.start <= found.start() <= part.end for part in parts):
            continue
        if _OWN_CIRCLE.search(text[: found.start()]) is None:
            return True
    return False


def _size(found: re.Match[str]) -> float:
    """``3½`` is 3.5."""
    glyph = found.group("part")
    return float(found.group("whole")) + (unicodedata.numeric(glyph) if glyph else 0.0)


def _asked_in_another_unit(rest: str, unit: str | None) -> bool:
    """An answer asked in a unit the size is not in: "in square metres" for 7 cm."""
    given = LENGTH_UNITS.get((unit or "").lower())
    for found in _ASKED_UNIT.finditer(rest):
        asked = LENGTH_UNITS.get(found.group(1).lower())
        if asked is not None and asked != given:
            return True
    return False


def circle_part_intent(body: str) -> MathIntent | None:
    """A part of a circle, or a circle with the π the question gives, read whole."""
    pi = stated_pi(body)
    if pi is not None and pi.value is None:
        return None  # π set to a value no solver here works with
    text = body if pi is None else f"{body[: pi.start]} {body[pi.end :]}"
    parts = circle_parts(text)
    pieces = text if _SECTOR.search(text) is None else _SECTOR.sub("circle", text)
    if len({part.fraction for part in parts}) > 1 or other_piece_of_circle(pieces):
        return None
    if another_shape_named(text, "circle") or _NARROWED.search(text):
        return None  # a square beside the semicircle, a perimeter "excluding the diameter"
    sector = None if parts else _sector_part(text, pi is not None)
    if sector is None and _SECTOR.search(text):
        return None  # a sector this rule cannot size is the sector solver's, or no one's
    if (parts or sector) and (_second_figure(text, parts) or _REMAINDER.search(text)):
        return None  # the part is not the only figure, or what is asked is what is left
    if not parts and sector is None and (pi is None or _CIRCLE.search(text) is None):
        return None
    # One measure asked once: "the area of the semicircle and the area of the full circle"
    # asks two, and one card is no answer to both.
    asked = [" ".join(found.lower().split()) for found in _ASKED.findall(text)]
    sizes = list(_SIZE.finditer(text))
    if len(asked) != 1 or len(sizes) != 1:
        return None
    quantity = asked[0]
    whole = not parts and sector is None
    if _CURVED.search(text):
        if whole or quantity == "area":
            return None  # a curved surface, or a whole circle's "curved" edge
        quantity = "arc length"  # "the perimeter of the curved part" is the arc
    if (quantity == "circumference" and not whole) or (quantity == "arc length" and whole):
        return None  # a semicircle's "circumference": its curved edge, or all of it?
    size = sizes[0]
    figures, places, asks_rounding = _rounding(text)
    read = [(size.start(), size.end()), *((part.start, part.end) for part in parts)]
    read += [span for span in (asks_rounding, sector[2] if sector else None) if span]
    rest = "".join(
        " " if any(start <= at < end for start, end in read) else char
        for at, char in enumerate(text)
    )
    if _UNREAD.search(rest) or _MORE_AFTER.match(text[size.end() :]):
        return None
    if whole and (
        fraction_named(rest) or _REMAINDER.search(rest) or len(_CIRCLES.findall(rest)) > 1
    ):
        # A whole circle only when the question says no fraction of it, nothing left of it
        # and no second circle: "a circle's quarter" was a checked 200.96 for 50.24.
        return None
    if _asked_in_another_unit(rest, size.group("unit")):
        return None
    fraction = parts[0].fraction if parts else (sector[0] if sector else Fraction(1))
    stated = pi.value if pi is not None and pi.value is not None else Fraction(0)
    numbers = [
        _size(size),
        *(float(n) for n in (fraction.numerator, fraction.denominator)),
        *(float(n) for n in (stated.numerator, stated.denominator if stated else 0)),
        float(figures),
        float(places),
        sector[1] if sector else 0.0,
    ]
    # A whole circle's perimeter is its circumference; the arc is a part's curved edge.
    measure = {"circumference": "perimeter", "arc length": "arc"}.get(quantity, quantity)
    unit = LENGTH_UNITS.get((size.group("unit") or "").lower())  # "metres" is m
    words = [measure, size.group("kind").lower(), *([unit] if unit else [])]
    return MathIntent(
        kind="arithmetic",
        school_op="geometry_measure:circle_part",
        stats_numbers=numbers,
        trial_outcome="|".join(words),
        operation="solve",
    )
