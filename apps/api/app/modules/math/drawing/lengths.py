"""Exact lengths in a scene in space: coordinates as fractions, and a length as shown.

A scene keeps its coordinates exact (a right angle is marked only where a dot product is
0); a length the server works out from them is shown as a root it can write ("√34"), a
whole number, or to two places.
"""

from __future__ import annotations

import math
from fractions import Fraction

from app.modules.math.drawing.question import Question, Triple
from app.modules.math.drawing.shapes import worked_value

# A value the reply gives a letter is rounded ("d = 10.44" for √109): one in a hundred.
ROUNDED = 0.01


def exact(values: tuple[float, ...]) -> Triple:
    x, y, z = (Fraction(value).limit_denominator(10_000) for value in values)
    return (x, y, z)


def minus(a: Triple, b: Triple) -> Triple:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a: Triple, b: Triple) -> Fraction:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def states_size(question: Question, value: Fraction) -> str | None:
    """The unit a stated length is written with ("" for none), or None when it is unstated
    (a rate, a size at one moment of a changing shape)."""
    if value in question.changing:
        return None
    for written in question.numbers:
        if written.in_formula or written.unit in {"deg", "area", "other"}:
            continue
        if written.value == value:
            return written.unit
    return None


def worked_length(squared: Fraction) -> tuple[str, float]:
    """A length the server works out from stated points, as shown ("√34", "5", "10.44") and
    as a number."""
    length = math.sqrt(float(squared))
    root = Fraction(round(length * 1_000_000), 1_000_000)
    if root * root == squared:
        return worked_value(float(root))[0], length
    if squared.denominator == 1 and squared.numerator < 10_000:
        return f"\u221a{squared.numerator}", length
    return worked_value(length)[0], length
