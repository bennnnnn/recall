"""Circles from their circumference or area, hemispheres, and a part of a circle (a
semicircle, a quarter circle, a quadrant, a sector), or a circle worked with the π its
question gives.

A part's area and curved edge are that fraction of the circle's; its perimeter is the
curved edge plus the two radii that bound it (a semicircle's make its diameter). The
figure is the part itself, drawn as the sector it is and labelled with the part's own
measure: the quarter circle of radius 8 cm was drawn as the whole circle and labelled
201.06 cm² (2026-11-13).

With a stated π ("use 3.14", "π = 22/7") every number is worked with that value, exactly,
and the card shows the book's answer: a quarter of 3.14 times 8² is 50.24, not π's 50.27.
A rounding the question asks for ("to three significant digits") is the card's rounding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from app.modules.math.schemas import CircleGeometryBlockSpec, SectorGeometryBlockSpec
from app.modules.math.tex_numbers import fraction_tex
from app.modules.math.tools.school.geometry_measures.working import _approx, _n, _Solved, _unit
from app.services.asked_value import QUANTITY_NAMES
from app.services.number_text import NUMBER_WORDS
from app.services.school_rounding import format_places, round_figures, trim_zeros
from app.services.workout import math_line


def _pi_times(coefficient: Fraction) -> str:
    """``8\\pi``, ``\\frac{9}{2}\\pi``."""
    if coefficient == 1:
        return r"\pi"
    if coefficient.denominator == 1:
        return rf"{coefficient.numerator}\pi"
    return rf"\frac{{{coefficient.numerator}}}{{{coefficient.denominator}}}\pi"


def _pi_answer(coefficient: float, unit: str | None, power: int) -> str:
    """Exactly ``8\\pi`` when the coefficient is a short fraction, always with its decimal."""
    exact = Fraction(coefficient).limit_denominator(12)
    value = coefficient * math.pi
    decimal = rf"{_approx(value)}{_unit(unit, power)}"
    if abs(float(exact) - coefficient) < 1e-9:
        return rf"{_pi_times(exact)} \approx {decimal}"
    return rf"\approx {decimal}"


def _radius(kind: str, value: float) -> tuple[float, str]:
    """The radius, and its Given line, from a radius or a diameter."""
    if kind == "diameter":
        return value / 2, math_line(f"d = {_n(value)}", "diameter")
    return value, math_line(f"r = {_n(value)}", "radius")


def _hemisphere(numbers: list[float], words: list[str]) -> _Solved | None:
    quantity, kind = words[0], words[1]
    unit = words[2] if len(words) > 2 else None
    r, given = _radius(kind, numbers[0])
    if quantity == "volume":
        return _Solved(
            (given,),
            (math_line("V", "volume of the hemisphere"),),
            (math_line(r"V = \frac{2}{3}\pi r^3", "Half a sphere"),),
            (math_line(rf"V = \frac{{2}}{{3}}\pi({_n(r)})^3"),),
            _pi_answer(2 * r**3 / 3, unit, 3),
        )
    curved = quantity.startswith("curved")
    return _Solved(
        (given,),
        (math_line("S", "curved surface" if curved else "surface area, flat face included"),),
        (
            math_line(r"S = 2\pi r^2", "Half a sphere's surface")
            if curved
            else math_line(
                r"S = 2\pi r^2 + \pi r^2 = 3\pi r^2", "Curved surface plus the flat circle"
            ),
        ),
        (math_line(rf"S = {'2' if curved else '3'}\pi({_n(r)})^2"),),
        _pi_answer((2 if curved else 3) * r * r, unit, 2),
    )


def _circle_from_circumference(numbers: list[float], words: list[str]) -> _Solved | None:
    asked = words[0]
    unit = words[1] if len(words) > 1 else None
    c = numbers[0]
    r = c / (2 * math.pi)
    rows = [math_line(rf"r = \frac{{C}}{{2\pi}} = \frac{{{_n(c)}}}{{2\pi}} \approx {_approx(r)}")]
    if asked == "radius":
        answer = rf"\approx {_approx(r)}{_unit(unit)}"
    elif asked == "diameter":
        rows.append(math_line(rf"d = 2r \approx {_approx(2 * r)}"))
        answer = rf"\approx {_approx(c / math.pi)}{_unit(unit)}"
    else:
        rows.append(math_line(rf"A = \pi r^2 \approx \pi({_approx(r)})^2"))
        answer = rf"\approx {_approx(c * c / (4 * math.pi))}{_unit(unit, 2)}"
    return _Solved(
        (math_line(f"C = {_n(c)}", "circumference"),),
        (math_line(asked[0] if asked != "area" else "A", asked),),
        (math_line(r"C = 2\pi r", "Circumference"),),
        tuple(rows),
        answer,
    )


def _circle_from_circumference_pi(numbers: list[float], words: list[str]) -> _Solved | None:
    """``C = 10π``: r = 5 exactly, and the area is 25π."""
    asked = words[0]
    unit = words[1] if len(words) > 1 else None
    k = Fraction(numbers[0]).limit_denominator(1000)
    if k <= 0 or abs(float(k) - numbers[0]) > 1e-9:
        return None
    r = k / 2
    rows = [
        math_line(rf"r = \frac{{C}}{{2\pi}} = \frac{{{_pi_times(k)}}}{{2\pi}} = {fraction_tex(r)}")
    ]
    if asked == "radius":
        answer = f"{fraction_tex(r)}{_unit(unit)}"
    elif asked == "diameter":
        rows.append(math_line(rf"d = 2r = {fraction_tex(k)}"))
        answer = f"{fraction_tex(k)}{_unit(unit)}"
    else:
        rows.append(
            math_line(rf"A = \pi r^2 = \pi\left({fraction_tex(r)}\right)^2 = {_pi_times(r * r)}")
        )
        answer = _pi_answer(float(r * r), unit, 2)
    return _Solved(
        (math_line(f"C = {_pi_times(k)}", "circumference"),),
        (math_line(asked[0] if asked != "area" else "A", asked),),
        (math_line(r"C = 2\pi r", "Circumference"),),
        tuple(rows),
        answer,
    )


def _circle_from_area_pi(numbers: list[float], words: list[str]) -> _Solved | None:
    """``A = 16π``: r = 4 exactly, and the circumference is 8π."""
    asked = words[0]
    unit = words[1] if len(words) > 1 else None
    k = Fraction(numbers[0]).limit_denominator(1000)
    if k <= 0 or abs(float(k) - numbers[0]) > 1e-9:
        return None
    root_num, root_den = math.isqrt(k.numerator), math.isqrt(k.denominator)
    if root_num * root_num != k.numerator or root_den * root_den != k.denominator:
        # r = √k is not a whole or a fraction: the decimal rules already cover it.
        return _circle_from_area([numbers[0] * math.pi], words)
    r = Fraction(root_num, root_den)
    rows = [
        math_line(
            rf"r = \sqrt{{\frac{{A}}{{\pi}}}} = \sqrt{{\frac{{{_pi_times(k)}}}{{\pi}}}}"
            rf" = {fraction_tex(r)}"
        )
    ]
    if asked == "radius":
        answer = f"{fraction_tex(r)}{_unit(unit)}"
    elif asked == "diameter":
        rows.append(math_line(rf"d = 2r = {fraction_tex(2 * r)}"))
        answer = f"{fraction_tex(2 * r)}{_unit(unit)}"
    else:
        rows.append(
            math_line(rf"C = 2\pi r = 2\pi\left({fraction_tex(r)}\right) = {_pi_times(2 * r)}")
        )
        answer = _pi_answer(float(2 * r), unit, 1)
    return _Solved(
        (math_line(f"A = {_pi_times(k)}", "area"),),
        (math_line("C" if asked == "circumference" else asked[0], asked),),
        (math_line(r"A = \pi r^2", "Circle area"),),
        tuple(rows),
        answer,
    )


def _circle_from_area(numbers: list[float], words: list[str]) -> _Solved | None:
    asked = words[0]
    unit = words[1] if len(words) > 1 else None
    a = numbers[0]
    if a <= 0:
        return None
    r = math.sqrt(a / math.pi)
    rows = [
        math_line(
            rf"r = \sqrt{{\frac{{A}}{{\pi}}}} = \sqrt{{\frac{{{_n(a)}}}{{\pi}}}}"
            rf" \approx {_approx(r)}"
        )
    ]
    if asked == "radius":
        answer = rf"\approx {_approx(r)}{_unit(unit)}"
    elif asked == "diameter":
        rows.append(math_line(rf"d = 2r \approx 2({_approx(r)})"))
        answer = rf"\approx {_approx(2 * r)}{_unit(unit)}"
    else:
        rows.append(math_line(rf"C = 2\pi r \approx 2\pi({_approx(r)})"))
        answer = rf"\approx {_approx(2 * math.pi * r)}{_unit(unit)}"
    return _Solved(
        (math_line(f"A = {_n(a)}", "area"),),
        (math_line("C" if asked == "circumference" else asked[0], asked),),
        (math_line(r"A = \pi r^2", "Circle area"),),
        tuple(rows),
        answer,
    )


_COUNT_NAMES = {value: word for word, value in NUMBER_WORDS.items()}
_SHARE_NAMES = {2: "half", 3: "third", 4: "quarter", 5: "fifth", 6: "sixth", 8: "eighth"}
_PART_NAMES = {
    Fraction(1): "circle",
    Fraction(1, 2): "semicircle",
    Fraction(1, 4): "quarter circle",
    Fraction(3, 4): "three-quarter circle",
}
# A value worked with a stated π is shown in full to this many places (3.14 x 6.25 = 19.625);
# past it (3.1416 x 64 = 201.0624), as ≈ to two places.
_DECIMAL_PLACES = 3
# A fraction too long to read at a glance is left to its decimal.
_SHORT_DIGITS = 6
_THETA = r"\frac{\theta}{360^\circ}"


@dataclass(frozen=True)
class Reading:
    """What ``part_rule`` read, from the intent's numbers."""

    size: float
    part: Fraction
    pi: Fraction | None
    figures: int
    places: int
    angle: float  # a sector's angle in degrees; 0 for a part named in words

    @classmethod
    def of(cls, numbers: list[float]) -> Reading | None:
        if len(numbers) != 8 or not numbers[2]:
            return None
        size, top, bottom, pi_top, pi_bottom, figures, places, angle = numbers
        pi = Fraction(int(pi_top), int(pi_bottom)) if pi_bottom else None
        part = Fraction(int(top), int(bottom))
        return cls(size, part, pi, int(figures), int(places), angle)

    def decimal(self, value: float | Fraction) -> str:
        """The value as the card shows it: to the rounding asked, else two places."""
        if self.figures:
            mantissa, exponent = round_figures(value, self.figures)
            return format(mantissa.scaleb(exponent), "f")
        if self.places >= 0:
            return format_places(value, self.places)
        # Two places, a 5 rounded up as a class rounds it (19.625 is 19.63), no zero added
        # to a value that ends sooner (19.6), one kept where the rounding put it (37.70).
        shown = format_places(value, 2)
        return trim_zeros(shown) if Fraction(shown) == Fraction(value) else shown


def _share(part: Fraction) -> str:
    """``half``, ``a quarter``, ``three quarters``, ``two thirds``."""
    name = _SHARE_NAMES.get(part.denominator)
    if name is None:
        return f"${fraction_tex(part)}$"
    if part.numerator == 1:
        return name if name == "half" else f"a {name}"
    count = _COUNT_NAMES.get(part.numerator, str(part.numerator))
    return f"{count} {'halves' if name == 'half' else name + 's'}"


def _name(reading: Reading) -> str:
    if reading.angle:
        return "sector"
    return _PART_NAMES.get(reading.part) or f"part of the circle ({_share(reading.part)})"


def _times(coefficient: Fraction) -> str:
    """``\\frac{1}{4}`` in front of π, nothing for a whole."""
    return "" if coefficient == 1 else fraction_tex(coefficient)


def _short(value: Fraction) -> bool:
    return max(len(str(value.numerator)), len(str(value.denominator))) <= _SHORT_DIGITS


def _terminating(value: Fraction) -> bool:
    denominator = value.denominator
    for prime in (2, 5):
        while denominator % prime == 0:
            denominator //= prime
    return denominator == 1


def _pi_text(pi: Fraction) -> str:
    """π as the question gave it: ``3.14``, or ``\\frac{22}{7}``."""
    return _n(float(pi)) if _terminating(pi) else fraction_tex(pi)


@dataclass(frozen=True)
class _Measure:
    """``value = coefficient * π + constant``, and how the working names it."""

    symbol: str
    asked: str
    formula: str
    note: str
    coefficient: Fraction
    constant: Fraction
    power: int

    def value(self, pi: Fraction | None) -> float:
        times = math.pi if pi is None else float(pi)
        return float(self.coefficient) * times + float(self.constant)

    def answer(self, reading: Reading, unit: str | None) -> str:
        shown = _unit(unit, self.power)
        pi = reading.pi
        exact = None if pi is None else self.coefficient * pi + self.constant
        rounded = reading.decimal(self.value(None) if exact is None else exact)
        if exact is not None and (reading.figures or reading.places >= 0):
            same = Fraction(rounded) == exact
            return f"{rounded}{shown}" if same else rf"\approx {rounded}{shown}"
        if exact is not None:
            if _terminating(exact) and round(exact, _DECIMAL_PLACES) == exact:
                return f"{trim_zeros(format_places(exact, _DECIMAL_PLACES))}{shown}"
            if _short(exact) and not _terminating(exact):  # 352/7: a fraction, then ≈
                return rf"{fraction_tex(exact)} \approx {rounded}{shown}"
            return rf"\approx {rounded}{shown}"
        if not _short(self.coefficient):
            return rf"\approx {rounded}{shown}"
        constant = f" + {fraction_tex(self.constant)}" if self.constant else ""
        return rf"{_pi_times(self.coefficient)}{constant} \approx {rounded}{shown}"


def _measure(quantity: str, reading: Reading, r: Fraction) -> _Measure:
    part, name = reading.part, _name(reading)
    share = _THETA if reading.angle else _times(part)
    if quantity == "area":
        note = f"{name[0].upper()}{name[1:]} area"
        formula = rf"A = {share}\pi r^2"
        return _Measure("A", f"area of the {name}", formula, note, part * r * r, Fraction(0), 2)
    if part == 1:
        return _Measure(
            "C", "circumference", r"C = 2\pi r", "Circle circumference", 2 * r, Fraction(0), 1
        )
    edge = rf"{_THETA}(2\pi r)" if reading.angle else rf"{_times(2 * part)}\pi r"
    if quantity == "arc":
        if reading.angle:
            note = "Arc length"
        elif part == Fraction(1, 2):
            note = "Half the circumference"
        else:
            note = f"{_share(part).capitalize()} of the circumference"
        return _Measure("L", "the curved edge", f"L = {edge}", note, 2 * part * r, Fraction(0), 1)
    note = (
        "Curved edge plus the diameter" if part == Fraction(1, 2) else "Curved edge plus two radii"
    )
    formula = f"P = {edge} + 2r"
    return _Measure("P", f"perimeter of the {name}", formula, note, 2 * part * r, 2 * r, 1)


def _substitution(measure: _Measure, reading: Reading, r: float) -> str:
    """``A = \\frac{1}{4}\\pi(8)^2``, or with a stated π
    ``A = \\frac{1}{4} \\times 3.14 \\times (8)^2``."""
    area = measure.power == 2
    if reading.angle:
        share = rf"\frac{{{_n(reading.angle)}^\circ}}{{360^\circ}}"
        before = share if area else rf"{share} \times 2"
    elif area:
        before = _times(reading.part)
    else:
        before = _times(2 * reading.part if reading.part < 1 else Fraction(2))
    radius = f"({_n(r)})^2" if area else f"({_n(r)})"
    if reading.pi is None:
        body = rf"{before}\pi{radius}"
    else:
        lead = rf"{before} \times " if before else ""
        body = rf"{lead}{_pi_text(reading.pi)} \times {radius}"
    tail = f" + 2({_n(r)})" if measure.constant else ""
    return f"{measure.symbol} = {body}{tail}"


def _figure(
    r: float, reading: Reading, unit: str | None, field: str, shown: str
) -> dict[str, object]:
    """The part drawn as itself, labelled with the card's measure and nothing else."""
    shown_unit = unit or "units"
    square = "²" if field == "area" else ""
    labels = {"radius": f"{r:g} {shown_unit}", field: f"{shown} {shown_unit}{square}"}
    measures: dict[str, object] = {"radius": r, "unit": shown_unit, field: float(shown)}
    if reading.part == 1:
        given_diameter = reading.size != r
        if given_diameter:
            labels["diameter"] = f"{reading.size:g} {shown_unit}"
            measures["diameter"] = reading.size
        circle = {
            **measures,
            "show_diameter": given_diameter,
            "show_area": field == "area",
            "show_circumference": field == "circumference",
            "labels": labels,
        }
        return CircleGeometryBlockSpec.model_validate(circle).model_dump(exclude_none=True)
    degrees = float(reading.part * 360)
    sector = {**measures, "angle_deg": degrees, "labels": {**labels, "angle": f"{degrees:g}°"}}
    return SectorGeometryBlockSpec.model_validate(sector).model_dump(exclude_none=True)


_FIGURE_FIELDS = {"A": "area", "C": "circumference", "L": "arc_length", "P": "perimeter"}


def circle_part(numbers: list[float], words: list[str]) -> _Solved | None:
    """``numbers`` as ``Reading`` reads them; ``words``: the measure asked (``area``,
    ``perimeter`` or ``arc``), ``radius`` or ``diameter``, and the unit."""
    reading = Reading.of(numbers)
    if reading is None or not 0 < reading.part <= 1 or (reading.part == 1 and not reading.pi):
        return None  # a whole circle worked with π itself is the circle solver's
    quantity, kind = words[0], words[1]
    unit = words[2] if len(words) > 2 else None
    r, given = _radius(kind, reading.size)
    measure = _measure(quantity, reading, Fraction(_n(r)))
    givens = [given]
    if reading.angle:
        givens.append(math_line(rf"\theta = {_n(reading.angle)}^\circ", "central angle"))
    if reading.pi is not None:
        givens.append(math_line(rf"\pi = {_pi_text(reading.pi)}"))
    radius_row = (
        (math_line(rf"r = \frac{{{_n(reading.size)}}}{{2}} = {_n(r)}"),)
        if kind == "diameter"
        else ()
    )
    pi = reading.pi
    shown = reading.decimal(
        measure.value(None) if pi is None else measure.coefficient * pi + measure.constant
    )
    return _Solved(
        tuple(givens),
        (math_line(measure.symbol, measure.asked),),
        (math_line(measure.formula, measure.note),),
        (*radius_row, math_line(_substitution(measure, reading, r))),
        measure.answer(reading, unit),
        figure=_figure(r, reading, unit, _FIGURE_FIELDS[measure.symbol], shown),
        asked=QUANTITY_NAMES[_FIGURE_FIELDS[measure.symbol]],
    )
