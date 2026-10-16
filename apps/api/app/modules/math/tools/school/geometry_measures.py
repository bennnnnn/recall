"""Closed school geometry the shape solvers do not read.

Each rule reads one stated question shape and nothing else, and its solver
returns the worked layout (Given, Find, Formula, Substitution) and the answer:

- circles from their circumference or area; semicircles; hemispheres
- a square from its diagonal; a rhombus from its diagonals; equilateral triangles
- cube and cuboid diagonals
- angle facts: the third angle, isosceles triangles, supplements and complements,
  the number of sides from an angle
- the sine rule; right-triangle trigonometry; a ladder against a wall
- circles, lines and triangles on coordinates

Before this, "the radius of a circle with circumference 31.4" was read as a
circle of radius 31.4, and "the area of a semicircle" was a whole circle's.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from fractions import Fraction

from app.modules.math.schemas import MathIntent
from app.modules.math.solve import triangle as triangle_laws
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.services.workout import Workout, math_line, render_workout

_N = r"(-?\d+(?:\.\d+)?)"
_DEG = r"\s*(?:°|degrees?|deg)?"
_DEGREES = r"\s*(?:°|degrees?|deg)\b"
_IS = r"\s*(?:of\s+|is\s+|=\s*|:\s*)?"
_UNIT = r"(?:\s*(mm|cm|km|m|in|ft))?"
_POINT = rf"\(\s*{_N}\s*,\s*{_N}\s*\)"


@dataclass(frozen=True)
class _Solved:
    given: tuple[str, ...]
    find: tuple[str, ...]
    formula: tuple[str, ...]
    substitution: tuple[str, ...]
    answer: str


def _n(value: float) -> str:
    return f"{value:g}" if abs(value) >= 1e-4 or value == 0 else f"{value:.4g}"


def _approx(value: float, places: int = 2) -> str:
    rounded = round(value, places)
    return _n(rounded) if rounded == round(value, 10) else f"{value:.{places}f}"


def _unit(unit: str | None, power: int = 1) -> str:
    if not unit:
        return ""
    return rf"\ \mathrm{{{unit}}}" + (f"^{{{power}}}" if power > 1 else "")


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


def _degrees(value: float) -> str:
    return rf"{_approx(value, 1) if not float(value).is_integer() else _n(value)}^\circ"


def _surd_answer(square: float, unit: str | None) -> str:
    """``\\sqrt{12} = 2\\sqrt{3} \\approx 3.46`` or a whole number."""
    root = math.sqrt(square)
    if abs(root - round(root)) < 1e-9:
        return f"{round(root)}{_unit(unit)}"
    if float(square).is_integer():
        whole, inside = 1, int(square)
        factor = 2
        while factor * factor <= inside:
            while inside % (factor * factor) == 0:
                inside //= factor * factor
                whole *= factor
            factor += 1
        exact = rf"\sqrt{{{inside}}}" if whole == 1 else rf"{whole}\sqrt{{{inside}}}"
        return rf"{exact} \approx {_approx(root)}{_unit(unit)}"
    return rf"\approx {_approx(root)}{_unit(unit)}"


# --- the rules: (op, pattern), read in order -------------------------------------------

_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "semicircle",
        re.compile(
            rf"\b(area|perimeter|arc\s+length)\b.*?\bsemi-?circle\b.*?\b(radius|diameter){_IS}{_N}{_UNIT}",
            re.I,
        ),
    ),
    (
        "hemisphere",
        re.compile(
            rf"\b(volume|surface\s+area|curved\s+surface\s+area)\b.*?\bhemisphere\b.*?"
            rf"\b(radius|diameter){_IS}{_N}{_UNIT}",
            re.I,
        ),
    ),
    (
        "circle_from_circumference",
        re.compile(
            rf"\b(radius|diameter|area)\b.*?\bcircle\b.*?\bcircumference{_IS}{_N}{_UNIT}", re.I
        ),
    ),
    (
        "circle_from_area",
        re.compile(
            rf"\b(radius|diameter|circumference)\b.*?\bcircle\b.*?\barea{_IS}{_N}{_UNIT}", re.I
        ),
    ),
    (
        "square_from_diagonal",
        re.compile(rf"\b(area|side|perimeter)\b.*?\bsquare\b.*?\bdiagonal{_IS}{_N}{_UNIT}", re.I),
    ),
    (
        "rhombus",
        re.compile(
            rf"\barea\b.*?\b(?:rhombus|kite)\b.*?\bdiagonals?{_IS}{_N}{_UNIT}\s*(?:and|,)\s*{_N}",
            re.I,
        ),
    ),
    (
        "equilateral",
        re.compile(
            rf"\b(area|height|altitude|perimeter)\b.*?\bequilateral\s+triangle\b.*?"
            rf"\bsides?(?:\s+length)?{_IS}{_N}{_UNIT}",
            re.I,
        ),
    ),
    (
        "cube_diagonal",
        re.compile(
            rf"\bdiagonal\b.*?\bcube\b.*?\b(?:side|edge)(?:\s+length)?{_IS}{_N}{_UNIT}", re.I
        ),
    ),
    (
        "cuboid_diagonal",
        re.compile(
            rf"\bdiagonal\b.*?\b(?:cuboid|box|rectangular\s+(?:prism|box|solid))\b.*?"
            rf"{_N}\s*(?:by|x|\u00d7)\s*{_N}\s*(?:by|x|\u00d7)\s*{_N}{_UNIT}",
            re.I,
        ),
    ),
    (
        "extreme_angle",
        re.compile(
            rf"\btriangle\b.*?\bsides?\s+(?:of\s+|are\s+|measuring\s+)?{_N}\s*,\s*{_N}\s*,?\s*(?:and\s+)?{_N}"
            r".*?\b(largest|biggest|greatest|smallest)\s+angle\b",
            re.I,
        ),
    ),
    (
        "third_angle",
        re.compile(
            rf"\btriangle\b.*?{_N}{_DEG}\s*(?:and|,)\s*{_N}{_DEG}.*?\b(?:third|remaining|missing|other)\s+angle",
            re.I,
        ),
    ),
    (
        "isosceles",
        re.compile(
            rf"\bisosceles\b.*?\b(base|apex|vertex|top)\s+angles?{_IS}{_N}{_DEG}.*?"
            r"\b(apex|vertex|top|base)\s+angles?\b",
            re.I,
        ),
    ),
    # An angle only: "the complement of 0.3" is a probability.
    (
        "supplement",
        re.compile(rf"\bsupplement(?:ary\s+angle)?\s+(?:of|to|for)\s+{_N}{_DEGREES}", re.I),
    ),
    (
        "complement",
        re.compile(rf"\bcomplement(?:ary\s+angle)?\s+(?:of|to|for)\s+{_N}{_DEGREES}", re.I),
    ),
    (
        "polygon_sides",
        re.compile(
            rf"\bhow\s+many\s+sides\b.*?\b(interior|exterior)\s+angles?\s*(?:is|are|of|=|measures?)?"
            rf"\s*{_N}{_DEG}",
            re.I,
        ),
    ),
    (
        "polygon_sides",
        re.compile(
            rf"\b(interior|exterior)\s+angles?\s*(?:is|are|of|=|measures?)?\s*{_N}{_DEG}.*?"
            r"\bhow\s+many\s+sides\b",
            re.I,
        ),
    ),
    (
        "ladder",
        re.compile(
            rf"{_N}\s*(m|ft|metres?|meters?|feet)?\s*(?:long\s+)?ladder\b.*?"
            rf"\b(?:foot|base|bottom)\b.*?{_N}\s*(?:m|ft|metres?|meters?|feet)?\s*(?:away\s+)?from\s+the\s+wall"
            r".*?\b(?:how\s+high|height|how\s+far\s+up|reach)\b",
            re.I,
        ),
    ),
    (
        "circle_equation",
        re.compile(
            rf"\bequation\s+of\s+(?:a|the)\s+circle\b.*?\bcent(?:er|re)\s*(?:at\s+|of\s+)?{_POINT}"
            rf".*?\bradius{_IS}{_N}",
            re.I,
        ),
    ),
    (
        "circle_centre_radius",
        re.compile(
            r"\bcent(?:er|re)\s+and\s+(?:the\s+)?radius\s+of\s+(?:the\s+circle\s+)?(.+=.+)$", re.I
        ),
    ),
    (
        "triangle_vertices",
        re.compile(
            rf"\barea\s+of\s+(?:a|the)\s+triangle\s+(?:with\s+)?(?:vertices|corners|points)\s+(?:at\s+)?"
            rf"{_POINT}\s*,?\s*{_POINT}\s*,?\s*(?:and\s+)?{_POINT}",
            re.I,
        ),
    ),
    (
        "perpendicular_gradient",
        re.compile(
            r"\b(?:gradient|slope)\s+of\s+(?:a|the|any)\s+line\s+(perpendicular|parallel)\s+to\s+"
            r"(?:the\s+line\s+)?y\s*=\s*([^,;?]+)",
            re.I,
        ),
    ),
    (
        "perpendicular_bisector",
        re.compile(
            rf"\bperpendicular\s+bisector\s+of\s+(?:the\s+(?:line\s+)?(?:segment\s+)?"
            rf"(?:joining|between|from)\s+)?{_POINT}\s*(?:and|to)\s*{_POINT}",
            re.I,
        ),
    ),
)

# Two angles and a side, a side asked: "A = 40 degrees, B = 60 degrees, a = 10, find b".
_ANGLE_GIVEN = re.compile(rf"\b([A-C])\s*=\s*{_N}{_DEG}")
_SIDE_GIVEN = re.compile(rf"\b([a-c])\s*=\s*{_N}")
_SIDE_ASKED = re.compile(r"\b(?:find|calculate|what\s+is|work\s+out)\s+(?:side\s+)?([a-c])\b")

# Right-triangle trigonometry.
_RIGHT = re.compile(r"\bright(?:[- ]angled?)?\s+triangle\b", re.I)
_SIDE_NAMED = re.compile(rf"\b(opposite|adjacent|hypotenuse)(?:\s+side)?{_IS}{_N}", re.I)
_ANGLE_NAMED = re.compile(rf"\b(?:an?\s+)?angle\s*(?:of\s+|is\s+|=\s*)?{_N}{_DEG}", re.I)
_ASKED_NAMED = re.compile(
    r"\b(?:find|calculate|what\s+is|work\s+out)\s+(?:the\s+)?(?:length\s+of\s+the\s+)?"
    r"(angle|opposite|adjacent|hypotenuse)\b",
    re.I,
)


# A measure the rule did not read to its end: ``10π``, ``10/3``, ``10*2``.
_PI_AFTER = re.compile(r"\s*(?:\u03c0|\\pi\b|pi\b)(?:\s*(mm|cm|km|m|in|ft)\b)?", re.I)
_MORE_AFTER = re.compile(r"\s*(?:[*/^\u00d7\u00b7]|\d|sqrt|\u221a)", re.I)
_PI_OPS = {"circle_from_circumference", "circle_from_area"}


def extract_geometry_measure_intent(cleaned: str) -> MathIntent | None:
    body = " ".join(cleaned.split()).strip().rstrip("?.!")
    if not body or len(body) > 300:
        return None
    for op, pattern in _RULES:
        found = pattern.search(body)
        if found is None:
            continue
        tail = body[found.end() :]
        pi = _PI_AFTER.match(tail)
        if pi is not None:
            # "circumference 10π" is 10π, not 10; the π was once dropped.
            return _pi_intent(op, found, pi.group(1)) if op in _PI_OPS else None
        if _MORE_AFTER.match(tail):
            return None
        return _intent(op, found)
    return _sine_rule_intent(body) or _right_trig_intent(body)


def _pi_intent(op: str, found: re.Match[str], unit: str | None) -> MathIntent | None:
    """A circle measure given as a multiple of π: ``C = 10π``, ``A = 16π``."""
    asked, number, _unit_before_pi = found.groups()
    if found.group(3) is not None:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op=f"geometry_measure:{op}_pi",
        stats_numbers=[float(number)],
        trial_outcome="|".join(word for word in (asked.lower(), unit) if word),
        operation="solve",
    )


# The group that holds an expression, not a number or a word, for the rules that have one.
_EXPRESSION_GROUP = {"circle_centre_radius": 1, "perpendicular_gradient": 2}


def _intent(op: str, found: re.Match[str]) -> MathIntent | None:
    expression_group = _EXPRESSION_GROUP.get(op)
    numbers: list[float] = []
    words: list[str] = []
    for index, group in enumerate(found.groups(), start=1):
        if group is None or index == expression_group:
            continue
        try:
            numbers.append(float(group))
        except ValueError:
            words.append(group.lower())
    joined = "|".join(words)
    if len(joined) > 24:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op=f"geometry_measure:{op}",
        stats_numbers=numbers,
        trial_outcome=joined or None,
        expr=found.group(expression_group) if expression_group else None,
        operation="solve",
    )


def _sine_rule_intent(body: str) -> MathIntent | None:
    angles = {match.group(1): float(match.group(2)) for match in _ANGLE_GIVEN.finditer(body)}
    sides = {match.group(1): float(match.group(2)) for match in _SIDE_GIVEN.finditer(body)}
    asked = _SIDE_ASKED.search(body)
    if asked is None or len(angles) != 2 or len(sides) != 1:
        return None
    (known_side, known_value), target = next(iter(sides.items())), asked.group(1)
    if known_side.upper() not in angles or target.upper() not in angles or known_side == target:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="geometry_measure:sine_rule",
        stats_numbers=[known_value, angles[known_side.upper()], angles[target.upper()]],
        trial_outcome=f"{known_side}|{target}",
        operation="solve",
    )


def _right_trig_intent(body: str) -> MathIntent | None:
    if not _RIGHT.search(body):
        return None
    asked = _ASKED_NAMED.search(body)
    if asked is None:
        return None
    target = asked.group(1).lower()
    sides = {
        match.group(1).lower(): float(match.group(2))
        for match in _SIDE_NAMED.finditer(body[: asked.start()] + body[asked.end() :])
    }
    angle = _ANGLE_NAMED.search(body)
    if target == "angle":
        if len(sides) != 2:
            return None
        first, second = sorted(sides)
        return MathIntent(
            kind="arithmetic",
            school_op="geometry_measure:right_angle_from_sides",
            stats_numbers=[sides[first], sides[second]],
            trial_outcome=f"{first}|{second}",
            operation="solve",
        )
    if angle is None or len(sides) != 1 or target in sides:
        return None
    (known, value) = next(iter(sides.items()))
    return MathIntent(
        kind="arithmetic",
        school_op="geometry_measure:right_side_from_angle",
        stats_numbers=[float(angle.group(1)), value],
        trial_outcome=f"{known}|{target}",
        operation="solve",
    )


# --- the solvers -----------------------------------------------------------------------


def _radius(kind: str, value: float) -> tuple[float, str]:
    """The radius, and its Given line, from a radius or a diameter."""
    if kind == "diameter":
        return value / 2, math_line(f"d = {_n(value)}", "diameter")
    return value, math_line(f"r = {_n(value)}", "radius")


def _semicircle(numbers: list[float], words: list[str]) -> _Solved | None:
    quantity, kind = words[0], words[1]
    unit = words[2] if len(words) > 2 else None
    r, given = _radius(kind, numbers[0])
    radius_row = (
        (math_line(rf"r = \frac{{{_n(numbers[0])}}}{{2}} = {_n(r)}"),) if kind == "diameter" else ()
    )
    if quantity == "area":
        return _Solved(
            (given,),
            (math_line("A", "area of the semicircle"),),
            (math_line(r"A = \frac{1}{2}\pi r^2", "Semicircle area"),),
            (*radius_row, math_line(rf"A = \frac{{1}}{{2}}\pi({_n(r)})^2")),
            _pi_answer(r * r / 2, unit, 2),
        )
    if quantity.startswith("arc"):
        return _Solved(
            (given,),
            (math_line("L", "the curved edge"),),
            (math_line(r"L = \pi r", "Half the circumference"),),
            (*radius_row, math_line(rf"L = \pi({_n(r)})")),
            _pi_answer(r, unit, 1),
        )
    value = math.pi * r + 2 * r
    return _Solved(
        (given,),
        (math_line("P", "perimeter of the semicircle"),),
        (math_line(r"P = \pi r + 2r", "Curved edge plus the diameter"),),
        (*radius_row, math_line(rf"P = \pi({_n(r)}) + 2({_n(r)})")),
        rf"{_n(r)}\pi + {_n(2 * r)} \approx {_approx(value)}{_unit(unit)}",
    )


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


def _fraction_tex(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    sign = "-" if value < 0 else ""
    return rf"{sign}\frac{{{abs(value.numerator)}}}{{{value.denominator}}}"


def _circle_from_circumference_pi(numbers: list[float], words: list[str]) -> _Solved | None:
    """``C = 10π``: r = 5 exactly, and the area is 25π."""
    asked = words[0]
    unit = words[1] if len(words) > 1 else None
    k = Fraction(numbers[0]).limit_denominator(1000)
    if k <= 0 or abs(float(k) - numbers[0]) > 1e-9:
        return None
    r = k / 2
    rows = [
        math_line(rf"r = \frac{{C}}{{2\pi}} = \frac{{{_pi_times(k)}}}{{2\pi}} = {_fraction_tex(r)}")
    ]
    if asked == "radius":
        answer = f"{_fraction_tex(r)}{_unit(unit)}"
    elif asked == "diameter":
        rows.append(math_line(rf"d = 2r = {_fraction_tex(k)}"))
        answer = f"{_fraction_tex(k)}{_unit(unit)}"
    else:
        rows.append(
            math_line(rf"A = \pi r^2 = \pi\left({_fraction_tex(r)}\right)^2 = {_pi_times(r * r)}")
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
            rf" = {_fraction_tex(r)}"
        )
    ]
    if asked == "radius":
        answer = f"{_fraction_tex(r)}{_unit(unit)}"
    elif asked == "diameter":
        rows.append(math_line(rf"d = 2r = {_fraction_tex(2 * r)}"))
        answer = f"{_fraction_tex(2 * r)}{_unit(unit)}"
    else:
        rows.append(
            math_line(rf"C = 2\pi r = 2\pi\left({_fraction_tex(r)}\right) = {_pi_times(2 * r)}")
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


def _square_from_diagonal(numbers: list[float], words: list[str]) -> _Solved | None:
    asked = words[0]
    unit = words[1] if len(words) > 1 else None
    d = numbers[0]
    given = (math_line(f"d = {_n(d)}", "diagonal"),)
    if asked == "area":
        return _Solved(
            given,
            (math_line("A", "area"),),
            (math_line(r"A = \frac{d^2}{2}", "A square's diagonal is s\\sqrt{2}"),),
            (math_line(rf"A = \frac{{{_n(d)}^2}}{{2}} = \frac{{{_n(d * d)}}}{{2}}"),),
            f"{_n(d * d / 2)}{_unit(unit, 2)}",
        )
    side = d / math.sqrt(2)
    if asked == "side":
        return _Solved(
            given,
            (math_line("s", "side"),),
            (math_line(r"d = s\sqrt{2}", "Pythagorean theorem on half the square"),),
            (math_line(rf"s = \frac{{{_n(d)}}}{{\sqrt{{2}}}}"),),
            _surd_answer(d * d / 2, unit),
        )
    return _Solved(
        given,
        (math_line("P", "perimeter"),),
        (math_line(r"P = 4s, \quad s = \frac{d}{\sqrt{2}}"),),
        (math_line(rf"P = 4 \times \frac{{{_n(d)}}}{{\sqrt{{2}}}} = {_n(2 * d)}\sqrt{{2}}"),),
        rf"{_n(2 * d)}\sqrt{{2}} \approx {_approx(4 * side)}{_unit(unit)}",
    )


def _rhombus(numbers: list[float], words: list[str]) -> _Solved | None:
    p, q = numbers[0], numbers[1]
    unit = words[0] if words else None
    return _Solved(
        (math_line(f"d_1 = {_n(p)}"), math_line(f"d_2 = {_n(q)}")),
        (math_line("A", "area"),),
        (math_line(r"A = \frac{d_1 d_2}{2}", "Rhombus or kite area"),),
        (math_line(rf"A = \frac{{{_n(p)} \times {_n(q)}}}{{2}} = \frac{{{_n(p * q)}}}{{2}}"),),
        f"{_n(p * q / 2)}{_unit(unit, 2)}",
    )


def _equilateral(numbers: list[float], words: list[str]) -> _Solved | None:
    asked = words[0]
    unit = words[1] if len(words) > 1 else None
    s = numbers[0]
    given = (math_line(f"s = {_n(s)}", "side"),)
    if asked == "perimeter":
        return _Solved(
            given,
            (math_line("P"),),
            (math_line("P = 3s"),),
            (math_line(f"P = 3({_n(s)})"),),
            f"{_n(3 * s)}{_unit(unit)}",
        )
    if asked in {"height", "altitude"}:
        exact = rf"{_n(s / 2)}\sqrt{{3}}" if s % 2 == 0 else rf"\frac{{{_n(s)}\sqrt{{3}}}}{{2}}"
        return _Solved(
            given,
            (math_line("h", "height"),),
            (math_line(r"h = \frac{\sqrt{3}}{2}s", "Pythagorean theorem on half the triangle"),),
            (math_line(rf"h = \frac{{\sqrt{{3}}}}{{2}}({_n(s)})"),),
            rf"{exact} \approx {_approx(math.sqrt(3) / 2 * s)}{_unit(unit)}",
        )
    coefficient = Fraction(s * s).limit_denominator(100) / 4
    exact = (
        rf"{coefficient.numerator}\sqrt{{3}}"
        if coefficient.denominator == 1
        else rf"\frac{{{coefficient.numerator}\sqrt{{3}}}}{{{coefficient.denominator}}}"
    )
    return _Solved(
        given,
        (math_line("A", "area"),),
        (math_line(r"A = \frac{\sqrt{3}}{4}s^2", "Equilateral triangle area"),),
        (math_line(rf"A = \frac{{\sqrt{{3}}}}{{4}}({_n(s)})^2"),),
        rf"{exact} \approx {_approx(math.sqrt(3) / 4 * s * s)}{_unit(unit, 2)}",
    )


def _cube_diagonal(numbers: list[float], words: list[str]) -> _Solved | None:
    s = numbers[0]
    unit = words[0] if words else None
    return _Solved(
        (math_line(f"s = {_n(s)}", "edge"),),
        (math_line("d", "space diagonal"),),
        (math_line(r"d = \sqrt{s^2 + s^2 + s^2} = s\sqrt{3}", "Pythagorean theorem in 3D"),),
        (math_line(rf"d = {_n(s)}\sqrt{{3}}"),),
        rf"{_n(s)}\sqrt{{3}} \approx {_approx(s * math.sqrt(3))}{_unit(unit)}",
    )


def _cuboid_diagonal(numbers: list[float], words: list[str]) -> _Solved | None:
    length, width, height = numbers
    unit = words[0] if words else None
    square = length**2 + width**2 + height**2
    return _Solved(
        (
            math_line(f"l = {_n(length)}"),
            math_line(f"w = {_n(width)}"),
            math_line(f"h = {_n(height)}"),
        ),
        (math_line("d", "space diagonal"),),
        (math_line(r"d = \sqrt{l^2 + w^2 + h^2}", "Pythagorean theorem in 3D"),),
        (
            math_line(
                rf"d = \sqrt{{{_n(length)}^2 + {_n(width)}^2 + {_n(height)}^2}}"
                rf" = \sqrt{{{_n(square)}}}"
            ),
        ),
        _surd_answer(square, unit),
    )


def _extreme_angle(numbers: list[float], words: list[str]) -> _Solved | None:
    """The largest angle is opposite the longest side: ``\\cos C = (a^2 + b^2 - c^2) / 2ab``."""
    largest = words[0] != "smallest"
    sides = sorted(numbers)
    if not triangle_laws.triangle_valid(*sides):
        return None
    a, b, c = sides if largest else (sides[1], sides[2], sides[0])
    angle = triangle_laws.cosine_rule_angle(a, b, c)
    top = a * a + b * b - c * c
    bottom = 2 * a * b
    ratio = Fraction(str(triangle_laws.cosine_rule_cosine(a, b, c)))
    which = "largest" if largest else "smallest"
    return _Solved(
        (math_line(f"a = {_n(a)}"), math_line(f"b = {_n(b)}"), math_line(f"c = {_n(c)}")),
        (
            math_line(
                "C",
                f"the {which} angle, opposite the "
                f"{'longest' if largest else 'shortest'} side {_n(c)}",
            ),
        ),
        (math_line(r"\cos C = \frac{a^2 + b^2 - c^2}{2ab}", "Cosine rule"),),
        (
            math_line(
                rf"\cos C = \frac{{{_n(a)}^2 + {_n(b)}^2 - {_n(c)}^2}}{{2({_n(a)})({_n(b)})}}"
                rf" = \frac{{{_n(top)}}}{{{_n(bottom)}}}"
            ),
            math_line(
                rf"C = \cos^{{-1}}\left(\frac{{{ratio.numerator}}}{{{ratio.denominator}}}\right)"
            ),
        ),
        ("" if angle.is_Rational else r"\approx ") + _degrees(float(angle)),
    )


def _third_angle(numbers: list[float], words: list[str]) -> _Solved | None:
    a, b = numbers
    if a + b >= 180 or min(a, b) <= 0:
        return None
    return _Solved(
        (math_line(f"{_degrees(a)},\\ {_degrees(b)}", "two angles"),),
        (math_line("x", "the third angle"),),
        (math_line(r"\text{angles in a triangle} = 180^\circ"),),
        (math_line(rf"x = 180^\circ - {_degrees(a)} - {_degrees(b)}"),),
        _degrees(180 - a - b),
    )


def _isosceles(numbers: list[float], words: list[str]) -> _Solved | None:
    given_kind, asked_kind = words[0], words[1]
    angle = numbers[0]
    if given_kind == "base" and asked_kind != "base":
        if not 0 < angle < 90:
            return None
        return _Solved(
            (math_line(_degrees(angle), "each base angle"),),
            (math_line("x", "the apex angle"),),
            (math_line(r"x + 2(\text{base angle}) = 180^\circ", "The base angles are equal"),),
            (math_line(rf"x = 180^\circ - 2({_degrees(angle)})"),),
            _degrees(180 - 2 * angle),
        )
    if given_kind != "base" and asked_kind == "base":
        if not 0 < angle < 180:
            return None
        return _Solved(
            (math_line(_degrees(angle), "the apex angle"),),
            (math_line("x", "each base angle"),),
            (math_line(r"2x + \text{apex angle} = 180^\circ", "The base angles are equal"),),
            (math_line(rf"x = \frac{{180^\circ - {_degrees(angle)}}}{{2}}"),),
            _degrees((180 - angle) / 2),
        )
    return None


def _supplement(numbers: list[float], words: list[str]) -> _Solved | None:
    angle = numbers[0]
    if not 0 < angle < 180:
        return None
    return _Solved(
        (math_line(_degrees(angle)),),
        (math_line("x", "its supplement"),),
        (math_line(r"x + \text{angle} = 180^\circ", "Supplementary angles"),),
        (math_line(rf"x = 180^\circ - {_degrees(angle)}"),),
        _degrees(180 - angle),
    )


def _complement(numbers: list[float], words: list[str]) -> _Solved | None:
    angle = numbers[0]
    if not 0 < angle < 90:
        return None
    return _Solved(
        (math_line(_degrees(angle)),),
        (math_line("x", "its complement"),),
        (math_line(r"x + \text{angle} = 90^\circ", "Complementary angles"),),
        (math_line(rf"x = 90^\circ - {_degrees(angle)}"),),
        _degrees(90 - angle),
    )


def _polygon_sides(numbers: list[float], words: list[str]) -> _Solved | None:
    kind, angle = words[0], numbers[0]
    exterior = angle if kind == "exterior" else 180 - angle
    if not 0 < exterior < 180:
        return None
    sides = 360 / exterior
    if abs(sides - round(sides)) > 1e-9:
        return None
    rows = []
    if kind == "interior":
        rows.append(
            math_line(
                rf"\text{{exterior angle}} = 180^\circ - {_degrees(angle)} = {_degrees(exterior)}"
            )
        )
    rows.append(math_line(rf"n = \frac{{360^\circ}}{{{_degrees(exterior)}}}"))
    return _Solved(
        (math_line(_degrees(angle), f"each {kind} angle"),),
        (math_line("n", "the number of sides"),),
        (math_line(r"n = \frac{360^\circ}{\text{exterior angle}}", "Exterior angles add to 360°"),),
        tuple(rows),
        str(round(sides)),
    )


def _ladder(numbers: list[float], words: list[str]) -> _Solved | None:
    length, foot = numbers
    unit = {"metre": "m", "metres": "m", "meter": "m", "meters": "m", "feet": "ft"}.get(
        words[0] if words else "", words[0] if words else None
    )
    if not 0 < foot < length:
        return None
    square = length * length - foot * foot
    return _Solved(
        (
            math_line(f"L = {_n(length)}", "the ladder, the hypotenuse"),
            math_line(f"d = {_n(foot)}", "foot of the ladder to the wall"),
        ),
        (math_line("h", "height up the wall"),),
        (math_line(r"h^2 + d^2 = L^2", "Pythagorean theorem"),),
        (
            math_line(
                rf"h = \sqrt{{{_n(length)}^2 - {_n(foot)}^2}} = \sqrt{{{_n(length * length)} - "
                rf"{_n(foot * foot)}}} = \sqrt{{{_n(square)}}}"
            ),
        ),
        _surd_answer(square, unit),
    )


def _signed(value: float, name: str) -> str:
    """``(x - 2)``, ``(y + 3)``, ``x``."""
    if value == 0:
        return name
    return rf"\left({name} {'-' if value > 0 else '+'} {_n(abs(value))}\right)"


def _circle_equation(numbers: list[float], words: list[str]) -> _Solved | None:
    h, k, r = numbers
    if r <= 0:
        return None
    answer = f"{_signed(h, 'x')}^2 + {_signed(k, 'y')}^2 = {_n(r * r)}"
    return _Solved(
        (math_line(rf"\text{{centre }} ({_n(h)}, {_n(k)})"), math_line(f"r = {_n(r)}")),
        (math_line(r"\text{the equation of the circle}"),),
        (math_line(r"(x - a)^2 + (y - b)^2 = r^2", "Circle with centre (a, b)"),),
        (math_line(rf"(x - ({_n(h)}))^2 + (y - ({_n(k)}))^2 = {_n(r)}^2"),),
        answer,
    )


def _circle_centre_radius(intent: MathIntent) -> _Solved | None:
    from sympy import Poly, Symbol, expand, latex, sqrt

    from app.modules.math import solve as math_solve

    x, y = Symbol("x"), Symbol("y")
    equation = intent.expr or ""
    left, _, right = equation.partition("=")
    try:
        lhs = math_solve._parse_expression(left, ["x", "y"])
        rhs = math_solve._parse_expression(right, ["x", "y"])
        poly = Poly(expand(lhs - rhs), x, y)
    except Exception:
        return None
    coefficient = poly.coeff_monomial(x**2)
    if (
        coefficient == 0
        or poly.coeff_monomial(y**2) != coefficient
        or poly.coeff_monomial(x * y) != 0
    ):
        return None
    if poly.total_degree() != 2:
        return None
    d = poly.coeff_monomial(x) / coefficient
    e = poly.coeff_monomial(y) / coefficient
    f = poly.coeff_monomial(1) / coefficient
    a, b = -d / 2, -e / 2
    square = a**2 + b**2 - f
    if square <= 0:
        return None
    radius = sqrt(square)
    return _Solved(
        (math_line(latex(lhs) + " = " + latex(rhs)),),
        (math_line(r"\text{centre and radius}"),),
        (math_line(r"(x - a)^2 + (y - b)^2 = r^2", "Complete the square in x and in y"),),
        (
            math_line(
                rf"{_signed(float(a), 'x')}^2 - {latex(a**2)} + "
                rf"{_signed(float(b), 'y')}^2 - {latex(b**2)}"
                rf" + {latex(f)} = 0".replace("+ -", "- ")
            ),
            math_line(
                rf"{_signed(float(a), 'x')}^2 + {_signed(float(b), 'y')}^2 = {latex(square)}"
            ),
        ),
        rf"\text{{centre }} ({latex(a)}, {latex(b)}),\ r = {latex(radius)}",
    )


def _triangle_vertices(numbers: list[float], words: list[str]) -> _Solved | None:
    x1, y1, x2, y2, x3, y3 = numbers
    twice = x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)
    if twice == 0:
        return None
    points = rf"({_n(x1)}, {_n(y1)}),\ ({_n(x2)}, {_n(y2)}),\ ({_n(x3)}, {_n(y3)})"
    return _Solved(
        (math_line(points, "vertices"),),
        (math_line("A", "area"),),
        (
            math_line(
                r"A = \frac{1}{2}\left|x_1(y_2 - y_3) + x_2(y_3 - y_1) + x_3(y_1 - y_2)\right|",
                "Shoelace formula",
            ),
        ),
        (
            math_line(
                rf"A = \frac{{1}}{{2}}\left|{_n(x1)}({_n(y2)} - {_n(y3)})"
                rf" + {_n(x2)}({_n(y3)} - {_n(y1)}) + {_n(x3)}({_n(y1)} - {_n(y2)})\right|"
                rf" = \frac{{1}}{{2}}\left|{_n(twice)}\right|"
            ),
        ),
        _n(abs(twice) / 2),
    )


def _perpendicular_gradient(intent: MathIntent, words: list[str]) -> _Solved | None:
    from sympy import Poly, Rational, Symbol, latex, nsimplify

    from app.modules.math import solve as math_solve

    x = Symbol("x")
    try:
        line = math_solve._parse_expression((intent.expr or "").strip(), ["x"])
        poly = Poly(line, x)
    except Exception:
        return None
    if poly.degree() != 1:
        return None
    m = nsimplify(poly.coeff_monomial(x))
    if words[0] == "parallel":
        return _Solved(
            (math_line(f"y = {latex(line)}"),),
            (math_line("m", "gradient of a parallel line"),),
            (math_line(r"m_{\parallel} = m", "Parallel lines have equal gradients"),),
            (math_line(f"m = {latex(m)}"),),
            latex(m),
        )
    if m == 0:
        return None
    perpendicular = -Rational(1) / m
    return _Solved(
        (math_line(f"y = {latex(line)}"),),
        (math_line(r"m_{\perp}", "gradient of a perpendicular line"),),
        (math_line(r"m_{\perp} = -\frac{1}{m}", "Perpendicular gradients multiply to -1"),),
        (math_line(rf"m = {latex(m)}, \quad m_{{\perp}} = -\frac{{1}}{{{latex(m)}}}"),),
        latex(perpendicular),
    )


def _perpendicular_bisector(numbers: list[float], words: list[str]) -> _Solved | None:
    from sympy import Rational, latex, nsimplify

    x1, y1, x2, y2 = (nsimplify(value) for value in numbers)
    if (x1, y1) == (x2, y2):
        return None
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    rows = [math_line(rf"M = \left({latex(mx)}, {latex(my)}\right)", "midpoint")]
    if y1 == y2:
        rows.append(math_line("the segment is horizontal, so the bisector is vertical"))
        answer = f"x = {latex(mx)}"
    elif x1 == x2:
        rows.append(math_line("the segment is vertical, so the bisector is horizontal"))
        answer = f"y = {latex(my)}"
    else:
        slope = (y2 - y1) / (x2 - x1)
        perpendicular = -Rational(1) / slope
        rows.append(
            math_line(
                rf"m = \frac{{{latex(y2)} - {latex(y1)}}}{{{latex(x2)} - {latex(x1)}}}"
                rf" = {latex(slope)},"
                rf" \quad m_{{\perp}} = {latex(perpendicular)}"
            )
        )
        rows.append(
            math_line(rf"y - {latex(my)} = {latex(perpendicular)}\left(x - {latex(mx)}\right)")
        )
        from app.modules.math.tools.school.curve_points import _line_tex

        answer = _line_tex(perpendicular, my - perpendicular * mx, "x")
    return _Solved(
        (math_line(rf"({latex(x1)}, {latex(y1)}),\ ({latex(x2)}, {latex(y2)})"),),
        (math_line(r"\text{the perpendicular bisector}"),),
        (math_line(r"y - y_M = m_{\perp}(x - x_M)", "Through the midpoint, perpendicular"),),
        tuple(rows),
        answer,
    )


def _sine_rule(numbers: list[float], words: list[str]) -> _Solved | None:
    known, known_angle, target_angle = numbers
    known_name, target_name = words
    value = triangle_laws.sine_rule_side(known, known_angle, target_angle)
    k, t = known_name, target_name
    return _Solved(
        (
            math_line(f"{k} = {_n(known)}"),
            math_line(f"{k.upper()} = {_degrees(known_angle)}"),
            math_line(f"{t.upper()} = {_degrees(target_angle)}"),
        ),
        (math_line(t),),
        (
            math_line(
                rf"\frac{{{t}}}{{\sin {t.upper()}}} = \frac{{{k}}}{{\sin {k.upper()}}}", "Sine rule"
            ),
        ),
        (
            math_line(
                rf"{t} = \frac{{{_n(known)} \sin {_degrees(target_angle)}}}"
                rf"{{\sin {_degrees(known_angle)}}}"
            ),
        ),
        # At exact angles a surd whose square is whole (4\sqrt{2}); otherwise the decimal.
        rf"\approx {_approx(float(value))}"
        if value.is_Float
        else _surd_answer(float(value**2), None),
    )


_RATIO_NAME = {"sin": "Sine ratio", "cos": "Cosine ratio", "tan": "Tangent ratio"}
# The two sides each ratio uses, read from the pair the question gave.
_RATIO = {
    ("hypotenuse", "opposite"): "sin",
    ("adjacent", "hypotenuse"): "cos",
    ("adjacent", "opposite"): "tan",
}


def _right_angle_from_sides(numbers: list[float], words: list[str]) -> _Solved | None:
    first, second = words
    pair = (first, second)
    if pair not in _RATIO:
        return None
    function = _RATIO[pair]
    values = dict(zip(words, numbers, strict=True))
    if function == "sin":
        top, bottom = values["opposite"], values["hypotenuse"]
    elif function == "cos":
        top, bottom = values["adjacent"], values["hypotenuse"]
    else:
        top, bottom = values["opposite"], values["adjacent"]
    value = top / bottom
    if function != "tan" and not 0 < value < 1:
        return None
    angle = math.degrees({"sin": math.asin, "cos": math.acos, "tan": math.atan}[function](value))
    names = {
        "sin": ("opposite", "hypotenuse"),
        "cos": ("adjacent", "hypotenuse"),
        "tan": ("opposite", "adjacent"),
    }
    over = names[function]
    return _Solved(
        tuple(math_line(rf"\text{{{name}}} = {_n(values[name])}") for name in over),
        (math_line(r"\theta", "the angle"),),
        (
            math_line(
                rf"\{function}\theta = \frac{{\text{{{over[0]}}}}}{{\text{{{over[1]}}}}}",
                _RATIO_NAME[function],
            ),
        ),
        (
            math_line(rf"\{function}\theta = \frac{{{_n(top)}}}{{{_n(bottom)}}}"),
            math_line(
                rf"\theta = \{function}^{{-1}}\left(\frac{{{_n(top)}}}{{{_n(bottom)}}}\right)"
            ),
        ),
        _degrees(round(angle, 1)) if abs(angle - round(angle)) > 1e-9 else _degrees(round(angle)),
    )


def _right_side_from_angle(numbers: list[float], words: list[str]) -> _Solved | None:
    angle, value = numbers
    known, target = words
    if not 0 < angle < 90:
        return None
    radians = math.radians(angle)
    rules = {
        ("hypotenuse", "opposite"): ("sin", lambda: value * math.sin(radians)),
        ("hypotenuse", "adjacent"): ("cos", lambda: value * math.cos(radians)),
        ("adjacent", "opposite"): ("tan", lambda: value * math.tan(radians)),
        ("opposite", "adjacent"): ("tan", lambda: value / math.tan(radians)),
        ("opposite", "hypotenuse"): ("sin", lambda: value / math.sin(radians)),
        ("adjacent", "hypotenuse"): ("cos", lambda: value / math.cos(radians)),
    }
    rule = rules.get((known, target))
    if rule is None:
        return None
    function, compute = rule
    result = compute()
    multiply = (known, target) in {
        ("hypotenuse", "opposite"),
        ("hypotenuse", "adjacent"),
        ("adjacent", "opposite"),
    }
    substitution = (
        rf"\text{{{target}}} = {_n(value)}\{function} {_degrees(angle)}"
        if multiply
        else rf"\text{{{target}}} = \frac{{{_n(value)}}}{{\{function} {_degrees(angle)}}}"
    )
    over = {
        "sin": ("opposite", "hypotenuse"),
        "cos": ("adjacent", "hypotenuse"),
        "tan": ("opposite", "adjacent"),
    }[function]
    return _Solved(
        (math_line(rf"\theta = {_degrees(angle)}"), math_line(rf"\text{{{known}}} = {_n(value)}")),
        (math_line(rf"\text{{{target}}}"),),
        (
            math_line(
                rf"\{function}\theta = \frac{{\text{{{over[0]}}}}}{{\text{{{over[1]}}}}}",
                _RATIO_NAME[function],
            ),
        ),
        (math_line(substitution),),
        _n(round(result, 10))
        if abs(result - round(result)) < 1e-9
        else rf"\approx {_approx(result)}",
    )


_SOLVERS: dict[str, Callable[[list[float], list[str]], _Solved | None]] = {
    "semicircle": _semicircle,
    "hemisphere": _hemisphere,
    "circle_from_circumference": _circle_from_circumference,
    "circle_from_area": _circle_from_area,
    "circle_from_circumference_pi": _circle_from_circumference_pi,
    "circle_from_area_pi": _circle_from_area_pi,
    "square_from_diagonal": _square_from_diagonal,
    "rhombus": _rhombus,
    "equilateral": _equilateral,
    "cube_diagonal": _cube_diagonal,
    "cuboid_diagonal": _cuboid_diagonal,
    "extreme_angle": _extreme_angle,
    "third_angle": _third_angle,
    "isosceles": _isosceles,
    "supplement": _supplement,
    "complement": _complement,
    "polygon_sides": _polygon_sides,
    "ladder": _ladder,
    "circle_equation": _circle_equation,
    "triangle_vertices": _triangle_vertices,
    "perpendicular_bisector": _perpendicular_bisector,
    "sine_rule": _sine_rule,
    "right_angle_from_sides": _right_angle_from_sides,
    "right_side_from_angle": _right_side_from_angle,
}


def is_geometry_measure(school_op: str | None) -> bool:
    return bool(school_op and school_op.startswith("geometry_measure:"))


def geometry_measure_block(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    op = (intent.school_op or "").partition(":")[2]
    numbers = list(intent.stats_numbers or [])
    words = [word for word in (intent.trial_outcome or "").split("|") if word]
    try:
        if op == "circle_centre_radius":
            solved = _circle_centre_radius(intent)
        elif op == "perpendicular_gradient":
            solved = _perpendicular_gradient(intent, words)
        else:
            solver = _SOLVERS.get(op)
            solved = solver(numbers, words) if solver is not None else None
    except (ValueError, ZeroDivisionError, IndexError):
        return None
    if solved is None:
        return None
    lines.extend(row.split(" — ")[0] for row in solved.substitution)
    block = _finish_with_answer(lines, solved.answer)
    working = render_workout(
        Workout(
            given=solved.given,
            find=solved.find,
            formula=solved.formula,
            substitution=solved.substitution,
        ),
        solved.answer,
    )
    return replace(block, worked_reply=working)
