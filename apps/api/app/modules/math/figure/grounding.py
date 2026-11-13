"""Every number in a picture's reading is one the question states.

The read copies values; it never works them out. A number the question does not write (a
default it filled in, a value it computed, a slip) means the reading is not the question's,
and nothing is drawn: a picture with an invented size is worse than none. A number counts
as stated in digits ("12", "2.54", "5/2", "1 1/2"), in words ("twelve"), or by a polygon's
name (a hexagon's six sides); its sign may be read from the words around it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from fractions import Fraction

from app.modules.math.figure.quads import POLYGON_SIDES
from app.modules.math.figure.request import FigureRequest
from app.services.number_text import number_word_value

_NUMBER = re.compile(r"\d+(?:\.\d+)?|\.\d+")
_FRACTION = re.compile(r"(\d+)\s*/\s*(\d+)")
_MIXED = re.compile(r"(\d+)\s+(\d+)\s*/\s*(\d+)")
_WORD = re.compile(r"[a-z]+")
_TOLERANCE = 1e-9
# "x²" writes the 2 of x^2.
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def stated_numbers(texts: Iterable[str]) -> set[Fraction]:
    stated: set[Fraction] = set()
    for text in texts:
        lowered = text.lower().replace(",", "").translate(_SUPERSCRIPTS)
        stated |= {Fraction(found) for found in _NUMBER.findall(lowered)}
        for top, bottom in _FRACTION.findall(lowered):
            if int(bottom):
                stated.add(Fraction(int(top), int(bottom)))
        for whole, top, bottom in _MIXED.findall(lowered):
            if int(bottom):
                stated.add(int(whole) + Fraction(int(top), int(bottom)))
        for word in _WORD.findall(lowered):
            value = number_word_value(word)
            if value is not None:
                stated.add(Fraction(value))
            if word in POLYGON_SIDES:
                stated.add(Fraction(POLYGON_SIDES[word]))
    return stated


def _is_stated(value: float, stated: set[Fraction]) -> bool:
    size = abs(value)
    return any(abs(float(known) - size) <= _TOLERANCE * max(1.0, size) for known in stated)


def _expression_numbers(expr: str) -> list[float]:
    return [float(found) for found in _NUMBER.findall(expr)]


def _values(request: FigureRequest) -> list[float]:
    values = [measure.value for measure in request.measures]
    if request.sides is not None:
        values.append(float(request.sides))
    for point in request.points:
        values += [point.x, point.y]
    values += [v for v in (request.x_min, request.x_max) if v is not None]
    values += _expression_numbers(request.expr)
    values += _expression_numbers(request.inequality)
    for written in request.numbers:
        values += _expression_numbers(written)
    return values


def _implied(value: float, request: FigureRequest) -> bool:
    """A number a picture's kind states without digits: a graph's origin, the right angle of
    a right triangle, a square or a rectangle."""
    if value == 0:
        return request.kind in {"function", "points"}
    if value == 90:
        return request.shape.startswith(("right", "perpendicular")) or request.shape in {
            "square",
            "rectangle",
        }
    return False


def grounded(request: FigureRequest, texts: Iterable[str]) -> bool:
    """Every number the reading holds is one the question (or the message it continues)
    writes."""
    stated = stated_numbers(texts)
    return all(_implied(value, request) or _is_stated(value, stated) for value in _values(request))
