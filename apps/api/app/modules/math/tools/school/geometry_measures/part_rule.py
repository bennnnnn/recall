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
from fractions import Fraction

from app.modules.math.match.circle_parts import circle_parts, other_piece_of_circle
from app.modules.math.match.stated_pi import stated_pi
from app.modules.math.schemas import MathIntent
from app.services.number_text import count_word_pattern, number_word_value

_N = r"(\d+(?:\.\d+)?)"
_ASKED = re.compile(r"\b(area|perimeter|circumference|arc\s+length)\b", re.I)
_SIZE = re.compile(
    rf"\b(radius|diameter)\s*(?:of\s+|is\s+|=\s*|:\s*)?{_N}(?:\s*(mm|cm|km|m|in|ft)\b)?", re.I
)
_CIRCLE = re.compile(r"\bcircle\b", re.I)
_SECTOR = re.compile(r"\bsectors?\b", re.I)
_DEGREES = re.compile(rf"{_N}\s*(?:\u00b0|\^\s*\\circ|degrees?\b)", re.I)
_COUNT = count_word_pattern(low=1, high=12)
# "to three significant digits", "correct to 2 decimal places", "to the nearest tenth".
_ROUNDING = re.compile(
    rf"\b(?:to|in|correct\s+to)\s+(?:(?P<count>\d+|{_COUNT})\s+(?:(?P<figures>significant"
    r"\s+(?:figures?|digits?)|s\.?\s?f\.?)|(?P<places>decimal\s+places?|d\.?\s?p\.?))"
    r"|the\s+nearest\s+(?P<nearest>whole\s+number|integer|tenth|hundredth|thousandth))\b",
    re.I,
)
_NEAREST = {"whole number": 0, "integer": 0, "tenth": 1, "hundredth": 2, "thousandth": 3}
# A count or a number the rule has not read: a second shape, a second part, a total.
_UNREAD = re.compile(rf"\d|\b(?:{count_word_pattern(low=0, high=90)})\b|\bcircles\b", re.I)
# A measure the rule did not read to its end: "radius 10π", "radius 3/2", "radius 2*3".
_MORE_AFTER = re.compile(r"\s*(?:[*/^\u00d7\u00b7\u03c0]|\d|pi\b|sqrt|\u221a)", re.I)


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
    angle = Fraction(angles[0].group(1))
    if not 0 < angle < 360:
        return None
    return angle / 360, float(angle), (angles[0].start(), angles[0].end())


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
    sector = None if parts else _sector_part(text, pi is not None)
    if sector is None and _SECTOR.search(text):
        return None  # a sector this rule cannot size is the sector solver's, or no one's
    if not parts and sector is None and (pi is None or _CIRCLE.search(text) is None):
        return None
    asked = {" ".join(found.lower().split()) for found in _ASKED.findall(text)}
    sizes = list(_SIZE.finditer(text))
    if len(asked) != 1 or len(sizes) != 1:
        return None
    quantity = asked.pop()
    whole = not parts and sector is None
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
    fraction = parts[0].fraction if parts else (sector[0] if sector else Fraction(1))
    stated = pi.value if pi is not None and pi.value is not None else Fraction(0)
    numbers = [
        float(size.group(2)),
        *(float(n) for n in (fraction.numerator, fraction.denominator)),
        *(float(n) for n in (stated.numerator, stated.denominator if stated else 0)),
        float(figures),
        float(places),
        sector[1] if sector else 0.0,
    ]
    # A whole circle's perimeter is its circumference; the arc is a part's curved edge.
    measure = {"circumference": "perimeter", "arc length": "arc"}.get(quantity, quantity)
    words = [measure, size.group(1).lower(), *([size.group(3).lower()] if size.group(3) else [])]
    return MathIntent(
        kind="arithmetic",
        school_op="geometry_measure:circle_part",
        stats_numbers=numbers,
        trial_outcome="|".join(words),
        operation="solve",
    )
