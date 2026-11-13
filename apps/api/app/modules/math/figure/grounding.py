"""Every number in a picture's reading is one the question states, as it states it.

The read copies values; it never works them out. A number the question does not write (a
default it filled in, a value it computed, a slip) means the reading is not the question's,
and nothing is drawn: a picture with an invented size is worse than none. Each value is
matched to a number the question writes with the same sign, unit and role:

- a length with the reading's unit or none ("2 m by 50 cm" states no 2 cm side), never with
  degrees or a square unit;
- an angle in degrees or bare, never a length ("AB = 5 cm" states no 5° angle);
- a coordinate, a bound or a number on a line with its sign: "-3" is no 3, and the 4 of
  "x² - 4" is no -4;
- none of them a coefficient or a term of a formula ("2x + 10" states no 10° angle);
- a polygon's number of sides by its name (a hexagon's six) or as a bare count.

A number counts in digits ("12", "2.54", "5/2", "1 1/2") or in words ("twelve"). The last
message's numbers are the question's; the earlier messages count only when it states none
("now draw it"). A formula's own numbers are held to the formula and an inequality's to the
inequality (``coordinate``), as a whole.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction

from app.modules.math.figure.quads import POLYGON_SIDES
from app.modules.math.figure.request import FigureRequest
from app.services.number_text import number_word_value

_NUMBER = re.compile(
    r"(?P<whole>\d+)\s+(?P<top>\d+)\s*/\s*(?P<bottom>\d+)"
    r"|(?P<over>\d+)\s*/\s*(?P<under>\d+)"
    r"|(?P<plain>\d+(?:\.\d+)?|\.\d+)"
    r"|(?P<word>[a-z]+)"
)
_MINUSES = "-\u2212\u2013"
_OPERATORS = "+*/\u00d7\u00f7^\u00b7"
# What stands before a minus that subtracts ("x² - 4", "3x - 5") rather than negates.
_TERM_ENDS = ")]}²³⁴⁵⁶⁷⁸⁹⁰¹."
_AFTER = re.compile(r"(\s*)(°|º|[a-z]+)?([²³]|\^[23])?")
_LENGTH_UNITS = {
    "mm": "mm", "millimetre": "mm", "millimetres": "mm", "millimeter": "mm", "millimeters": "mm",
    "cm": "cm", "centimetre": "cm", "centimetres": "cm", "centimeter": "cm", "centimeters": "cm",
    "m": "m", "metre": "m", "metres": "m", "meter": "m", "meters": "m",
    "km": "km", "kilometre": "km", "kilometres": "km", "kilometer": "km", "kilometers": "km",
    "inch": "in", "inches": "in", "ft": "ft", "foot": "ft", "feet": "ft",
    "yd": "yd", "yard": "yd", "yards": "yd", "mi": "mi", "mile": "mi", "miles": "mi",
}  # fmt: skip
_DEGREES = frozenset({"°", "º", "degree", "degrees", "deg"})
_SQUARE_WORDS = frozenset({"square", "sq", "cubic", "cu"})
_ORDINAL_ENDS = frozenset({"st", "nd", "rd", "th"})
_ANGLE_WHATS = frozenset({"angle", "apex_angle", "base_angle"})
_TOLERANCE = 1e-9
# "1,200" is twelve hundred; a comma between coordinates stays.
_PAIR = re.compile(r"\(([^()]*[,;][^()]*)\)")
# One number as a reading writes it: "-5/2", "1.5", "2 1/2".
_WRITTEN = re.compile(r"^\s*([+-]?)\s*(\d+(?:\.\d+)?)(?:\s+(\d+)\s*/\s*(\d+)|\s*/\s*(\d+))?\s*$")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")


@dataclass(frozen=True)
class Written:
    """A number as the question writes it: signed, with the unit after it ("" for none,
    "deg", "area" or a length unit), and whether it is a term of a formula."""

    value: Fraction
    unit: str
    in_formula: bool


def unit_name(text: str) -> str:
    """A unit as one name ("centimetres" is "cm"); "" for none or one this does not know."""
    return _LENGTH_UNITS.get(text.strip().lower().rstrip("."), "")


def _minus_before(text: str, start: int) -> tuple[bool, bool]:
    """(negated, subtracted): the minus right before ``start`` negates the number, or
    subtracts it from a term before it."""
    before = text[:start].rstrip()
    if not before or before[-1] not in _MINUSES:
        words = before.split()
        return bool(words) and words[-1] == "negative", False
    rest = before[:-1].rstrip()
    word = re.search(r"[a-z]+$", rest)
    # A number, a closing bracket or a one-letter variable is a term; a word ("for -3",
    # "mark -2.5") is not.
    term = bool(rest) and (
        rest[-1].isdigit()
        or rest[-1] in _TERM_ENDS
        or (word is not None and len(word.group()) == 1)
    )
    return not term, term


def _unit_after(text: str, end: int) -> tuple[str, bool]:
    """The unit written after a number, and whether a letter is glued to it as a variable
    ("2x")."""
    match = _AFTER.match(text, end)
    if match is None or not match.group(2):
        return "", False
    gap, token, power = match.groups()
    if token in _DEGREES:
        return "deg", False
    if token in _SQUARE_WORDS:
        return "area", False
    unit = _LENGTH_UNITS.get(token, "")
    if unit:
        return ("area" if power else unit), False
    glued = not gap and token not in _ORDINAL_ENDS and number_word_value(token) is None
    return "", glued and len(token) <= 2


def _in_formula(text: str, start: int, end: int, subtracted: bool, glued: bool) -> bool:
    before = text[:start].rstrip()
    after = text[end:].lstrip()
    return (
        subtracted
        or glued
        or (bool(before) and before[-1] in _OPERATORS)
        or (bool(after) and after[0] in _OPERATORS)
        or (bool(after) and after[0] in _MINUSES)
    )


def written_numbers(text: str) -> list[Written]:
    lowered = _THOUSANDS.sub("", text.lower())
    found: list[Written] = []
    for match in _NUMBER.finditer(lowered):
        word = match.group("word")
        if word is not None:
            value = number_word_value(word)
            if value is None:
                continue
            number = Fraction(value)
        elif match.group("whole") is not None:
            number = int(match.group("whole")) + Fraction(
                int(match.group("top")), int(match.group("bottom")) or 1
            )
        elif match.group("over") is not None:
            if not int(match.group("under")):
                continue
            number = Fraction(int(match.group("over")), int(match.group("under")))
        else:
            number = Fraction(match.group("plain"))
        negated, subtracted = _minus_before(lowered, match.start())
        unit, glued = _unit_after(lowered, match.end())
        formula = _in_formula(lowered, match.start(), match.end(), subtracted, glued)
        found.append(Written(-number if negated else number, unit, formula))
    return found


def number_value(written: str) -> Fraction | None:
    """'-5/2', '1.5', '2 1/2' as an exact value; None for anything else."""
    match = _WRITTEN.match(written.replace("\u2212", "-").replace("\u2013", "-"))
    if match is None:
        return None
    sign, whole, top, bottom, denominator = match.groups()
    value = Fraction(whole)
    if top is not None and bottom is not None and int(bottom):
        value += Fraction(int(top), int(bottom))
    elif denominator is not None:
        if not int(denominator):
            return None
        value = Fraction(whole) / int(denominator)
    return -value if sign == "-" else value


def _counts(texts: Iterable[str]) -> set[int]:
    """Numbers of sides a polygon's name states ("hexagon": 6)."""
    words = {word for text in texts for word in re.findall(r"[a-z]+", text.lower())}
    return {sides for name, sides in POLYGON_SIDES.items() if name in words}


def own_texts(texts: Sequence[str]) -> list[str]:
    """The texts a reading's values may come from: the last message, or the earlier ones
    when it writes no number."""
    if not texts:
        return []
    return [texts[0]] if written_numbers(texts[0]) else list(texts[1:])


def _same(written: Fraction, value: float) -> bool:
    return abs(float(written) - value) <= _TOLERANCE * max(1.0, abs(value))


def _length(found: list[Written], value: float, unit: str) -> bool:
    return any(not w.in_formula and w.unit in {"", unit} and _same(w.value, value) for w in found)


def _angle(found: list[Written], value: float) -> bool:
    return any(not w.in_formula and w.unit in {"", "deg"} and _same(w.value, value) for w in found)


def _signed(found: list[Written], value: float) -> bool:
    return any(not w.in_formula and w.unit != "area" and _same(w.value, value) for w in found)


def _implied_right(request: FigureRequest) -> bool:
    """A right angle a picture's kind states without digits: a right triangle's, a square's,
    a rectangle's, two perpendicular lines'."""
    return request.shape.startswith(("right", "perpendicular")) or request.shape in {
        "square",
        "rectangle",
    }


def _measures_hold(request: FigureRequest, found: list[Written]) -> bool:
    unit = unit_name(request.unit) or request.unit.strip().lower()
    for measure in request.measures:
        if measure.what in _ANGLE_WHATS:
            if abs(measure.value - 90) < _TOLERANCE and _implied_right(request):
                continue
            if not _angle(found, measure.value):
                return False
        elif not _length(found, measure.value, unit):
            return False
    return True


def _numbers_hold(request: FigureRequest, found: list[Written]) -> bool:
    for written in request.numbers:
        value = number_value(written)
        if value is None or not _signed(found, float(value)):
            return False
    return True


def grounded(request: FigureRequest, texts: Sequence[str]) -> bool:
    """Every value the reading holds is one the question writes, in its role, sign and
    unit (a formula's and an inequality's numbers are checked with them)."""
    own = own_texts(texts)
    found = [w for text in own for w in written_numbers(text)]
    if not _measures_hold(request, found) or not _numbers_hold(request, found):
        return False
    if (
        request.sides is not None
        and request.sides not in _counts([*texts[:1], *own])
        and not any(
            not w.in_formula and w.unit == "" and _same(w.value, request.sides) for w in found
        )
    ):
        return False
    origin = request.kind in {"function", "points"}
    bounds = [v for v in (request.x_min, request.x_max) if v is not None]
    if not all((origin and v == 0) or _signed(found, v) for v in bounds):
        return False
    pairs = [pair for text in own for pair in _pairs(text)]
    for point in request.points:
        if pairs and not any(_same(x, point.x) and _same(y, point.y) for x, y in pairs):
            return False  # C(-3, -2) is no (3, -2), though A(2, 3) writes a 3
        if not pairs and not (_signed(found, point.x) and _signed(found, point.y)):
            return False
    return True


def _pairs(text: str) -> list[tuple[Fraction, Fraction]]:
    """The coordinate pairs a text writes, "(2, 3)" and "(-3, -2)", each with its signs."""
    found: list[tuple[Fraction, Fraction]] = []
    for inside in _PAIR.findall(text):
        parts = [written_numbers(part) for part in re.split(r"[,;]", inside)]
        if len(parts) == 2 and all(len(part) == 1 for part in parts):
            found.append((parts[0][0].value, parts[1][0].value))
    return found


def with_unit(request: FigureRequest, texts: Sequence[str]) -> FigureRequest:
    """A reading that left out the unit takes the one every stated length is written with
    ("PQ = 6 cm, PR = 10 cm": cm); lengths in two units, or none, leave it out."""
    lengths = [m.value for m in request.measures if m.what not in _ANGLE_WHATS]
    if request.unit.strip() or not lengths:
        return request
    found = [w for text in own_texts(texts) for w in written_numbers(text)]
    common: set[str] | None = None
    for value in lengths:
        units = {
            w.unit
            for w in found
            if not w.in_formula and w.unit not in {"", "deg", "area"} and _same(w.value, value)
        }
        common = units if common is None else common & units
    return (
        request.model_copy(update={"unit": common.pop()})
        if common and len(common) == 1
        else request
    )


def stated_in(value: float, texts: Sequence[str]) -> bool:
    """``value`` is a number the question writes, whatever its role: a word problem's
    amounts ("144 m deep, falling 4 m a week") for a formula it describes in words."""
    return any(
        _same(abs(w.value), abs(value)) for text in own_texts(texts) for w in written_numbers(text)
    )
