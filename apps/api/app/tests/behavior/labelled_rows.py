# ruff: noqa: RUF002, RUF003 -- a reply's maths is quoted glyph by glyph: ×.
"""Whether the units a worked reply prints are right: an independent reading of its rows.

A Substitution row that carries units is read back as Pint quantities, from the text a
student sees, and held to three things:
- its units go together (no metre added to a second);
- the value it states, on its own line or after it, is what its numbers make, in the
  stated unit (``d_b = (10 m/s)²/(2 × 10 m/s) = 5 m`` would make 5 m/s);
- a quantity whose letter has one meaning in school physics ends in that dimension (a
  distance d is a length, a speed v a velocity).
And the first row of each quantity labels only numbers it was given: a value with a unit
there is a given's, a constant's, or one a row above worked out, never the law's own 2.

The reader is deliberately separate from the server's: it parses the LaTeX a reply shows.
A row it cannot read is skipped and counted, never passed as right.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from fractions import Fraction
from typing import Any

from pint import UnitRegistry
from pint.errors import DimensionalityError, PintError

_UREG = UnitRegistry()
_Q = _UREG.Quantity
# A number and the unit after it: "48\,\mathrm{m/s}", "4\,\Omega", "2.5 \times 10^{3}\,\mathrm{J}".
_VALUE = re.compile(
    r"(?P<number>-?\d+(?:\.\d+)?)(?:\s*\\times\s*10\^\{(?P<power>-?\d+)\})?"
    r"\\,(?:\\mathrm\{(?P<unit>[^}]+)\}|\\(?P<omega>Omega))"
)
_ANGLE = re.compile(r"(?P<number>-?\d+(?:\.\d+)?)\^\\circ")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:\s*\\times\s*10\^\{-?\d+\})?")
# A letter whose meaning in a school answer is one dimension.
_LETTERS: dict[str, str] = {
    "d": "[length]",
    "s": "[length]",
    "h": "[length]",
    "x": "[length]",
    "H": "[length]",
    "\\lambda": "[length]",
    "v": "[length] / [time]",
    "u": "[length] / [time]",
    "a": "[length] / [time] ** 2",
    "t": "[time]",
    "F": "[length] * [mass] / [time] ** 2",
    "p": "[length] * [mass] / [time]",
    "\\rho": "[mass] / [length] ** 3",
    "E_k": "[length] ** 2 * [mass] / [time] ** 2",
    "E_p": "[length] ** 2 * [mass] / [time] ** 2",
}
_ANY_NUMBER = re.compile(r"(?P<number>-?\d+(?:\.\d+)?)(?:\s*\\times\s*10\^\{(?P<power>-?\d+)\})?")
# Constants a law writes as numbers: g, G, k_e, c, h, ħ, R, e, mₑ, k_B, ε₀, μ₀, sea level.
_CONSTANTS = (
    9.81, 6.6743e-11, 8.98755e9, 299792458.0, 6.62607e-34, 1.05457e-34, 8.31446,
    1.60218e-19, 9.10938e-31, 1.38065e-23, 8.85419e-12, 1.25664e-6, 101325.0,
)  # fmt: skip
# Units of a value a working looks up rather than is given: a molar mass, Avogadro's number.
_LOOKED_UP = frozenset({"g/mol", "mol⁻¹", "L·atm/(mol·K)", "J/(mol·K)", "C/mol"})


def _unit(spelled: str) -> Any:
    """A unit as a reply writes it, read by Pint; raises when it is no unit."""
    text = spelled.replace("²", "^2").replace("³", "^3").replace("⁻¹", "^-1").replace("·", "*")
    text = text.replace("Ω", "ohm").replace("µ", "u").replace("°C", "degC")
    # A lens's power in dioptres, D: Pint's D is the debye.
    text = re.sub(r"^D$", "1/m", text)
    # A count of particles is a number: 1.2 × 10²⁴ particles is mol × mol⁻¹.
    text = re.sub(r"\b(?:particles?|atoms?|molecules?)\b", "dimensionless", text)
    return _UREG(text).units


def _number(match: re.Match[str]) -> float:
    value = float(match.group("number"))
    return value * 10.0 ** int(match.group("power")) if match.group("power") else value


def _group(text: str, at: int) -> tuple[str, int]:
    """The ``{…}`` group opening at ``at``: its inside and the index past it."""
    depth = 0
    for index in range(at, len(text)):
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        if depth == 0:
            return text[at + 1 : index], index + 1
    raise ValueError("an unclosed group")


def _python(tex: str, values: list[Any]) -> str:
    """The row's right side as a Python expression over ``values`` (its quantities)."""

    def quantity(match: re.Match[str]) -> str:
        unit = _unit("ohm" if match.group("omega") else match.group("unit"))
        values.append(_Q(_number(match), unit))
        return f" _v[{len(values) - 1}] "

    def angle(match: re.Match[str]) -> str:
        values.append(math.radians(float(match.group("number"))))
        return f" _v[{len(values) - 1}] "

    text = _VALUE.sub(quantity, tex)
    text = _ANGLE.sub(angle, text)
    text = re.sub(r"(\d)\s*\\times\s*10\^\{(-?\d+)\}", r"\1e\2", text)
    out: list[str] = []
    at = 0
    while at < len(text):
        if text.startswith("\\frac", at) or text.startswith("\\tfrac", at):
            at = text.index("{", at)
            top, at = _group(text, at)
            bottom, at = _group(text, at)
            out.append(f"(({_python(top, values)})/({_python(bottom, values)}))")
        elif text.startswith("\\sqrt", at):
            inside, at = _group(text, text.index("{", at))
            out.append(f"_sqrt({_python(inside, values)})")
        elif (function := re.match(r"\\(sin|cos|tan)(?:\^\{(\d)\})?", text[at:])) is not None:
            at += function.end()
            inner_end = _closing_bracket(text, at)
            power = f"**{function.group(2)}" if function.group(2) else ""
            inner = _python(text[at + 1 : inner_end], values)
            out.append(f"(_{function.group(1)}({inner}){power})")
            at = inner_end + 1
        elif text.startswith("^{", at):
            inside, at = _group(text, at + 1)
            out.append(f"**({_exponent(_python(inside, values))})")
        elif text[at] == "^":
            out.append("**")
            at += 1
        elif text.startswith("\\times", at) or text.startswith("\\cdot", at):
            out.append("*")
            at += 6 if text.startswith("\\times", at) else 5
        elif text.startswith("\\pi", at):
            out.append(f"{math.pi}")
            at += 3
        elif text.startswith("\\left", at) or text.startswith("\\right", at):
            at += 5 if text.startswith("\\left", at) else 6
        elif text[at] in "{}":
            out.append("(" if text[at] == "{" else ")")
            at += 1
        elif text[at] == "\\":
            raise ValueError(f"an unread command in {tex!r}")
        else:
            out.append(text[at])
            at += 1
    expression = "".join(out)
    # Side by side is a product: ") (", "2 (".
    return re.sub(r"(\)|\d|\])\s*(?=[(_])|(\)|\])\s+(?=\d)", r"\1\2*", expression)


def _exponent(text: str) -> str:
    """A printed exponent as the fraction it rounds (0.333333 is 1/3), so a cube root's
    unit is a whole power."""
    try:
        value = float(text)
    except ValueError:
        return text
    fraction = Fraction(value).limit_denominator(12)
    return f"{fraction.numerator}/{fraction.denominator}" if abs(fraction - value) < 1e-4 else text


def _closing_bracket(text: str, at: int) -> int:
    depth = 0
    for index in range(at, len(text)):
        depth += {"(": 1, ")": -1}.get(text[index], 0)
        if depth == 0:
            return index
    raise ValueError("an unclosed bracket")


def _evaluate(tex: str) -> Any:
    values: list[Any] = []
    expression = _python(tex, values)
    functions: dict[str, Callable[..., Any]] = {
        "_sqrt": lambda value: value**0.5,
        "_sin": lambda value: math.sin(float(value)),
        "_cos": lambda value: math.cos(float(value)),
        "_tan": lambda value: math.tan(float(value)),
    }
    return eval(expression, {"__builtins__": {}}, {"_v": values, **functions})  # noqa: S307


def _letter(symbol: str) -> str:
    plain = re.sub(r"_\{([A-Za-z0-9])\}", r"_\1", "".join(symbol.split()))
    if plain in _LETTERS:
        return plain
    return plain.removeprefix("\\Delta").split("_", 1)[0].split("'", 1)[0]


def _agrees(made: float, stated: float) -> bool:
    """Equal to the stated value's own figures (chemistry states 34 g for 33.79 g)."""
    if math.isclose(made, stated, rel_tol=5e-3):
        return True
    digits = len(f"{stated:g}".replace(".", "").replace("-", "").lstrip("0")) or 1
    return math.isclose(float(f"{made:.{digits}g}"), stated, rel_tol=1e-9)


def _stated(text: str) -> Any | None:
    match = _VALUE.fullmatch(text.strip())
    if match is None:
        return None
    try:
        unit = _unit("ohm" if match.group("omega") else match.group("unit"))
    except PintError:
        return None
    return _Q(_number(match), unit)


def _first_row_problem(row: str, rhs: str, reply: str) -> str | None:
    """A first row's labelled number that is no given's, constant's or earlier row's."""
    above = reply.split(row, 1)[0]
    # Any number written above: a given, a conversion, a value a row worked out.
    known = [abs(_number(match)) for match in _ANY_NUMBER.finditer(above)]
    for match in _VALUE.finditer(rhs):
        value = abs(_number(match))
        if (match.group("unit") or "") in _LOOKED_UP:
            continue
        try:
            if _unit(match.group("unit") or "ohm").dimensionless:
                continue  # A conversion factor: × (1000 mL/L).
        except PintError:
            continue
        if not any(math.isclose(value, other, rel_tol=1e-3) for other in (*known, *_CONSTANTS)):
            return f"{row}: {match.group(0)} is no given's or constant's value"
    return None


def row_problems(reply: str) -> tuple[list[str], int]:
    """Each wrong unit in ``reply``'s Substitution, and how many labelled rows were unread."""
    if "**Substitution**" not in reply:
        return [], 0
    section = reply.split("**Substitution**", 1)[1].split("**Answer", 1)[0]
    rows = [line.strip().strip("$").strip() for line in section.splitlines()]
    rows = [row for row in rows if row and "=" in row]
    problems: list[str] = []
    unread = 0
    seen: set[str] = set()
    for at, row in enumerate(rows):
        sides = [side.strip() for side in row.split("=")]
        lhs = sides[0]
        # The first row of a quantity is its first in the working, labelled or not: the
        # value a closing row reaches (t = 7.23 × 10¹¹ s after its sum) is no given's.
        first = lhs not in seen
        seen.add(lhs)
        if not _VALUE.search("=".join(sides[1:])) or len(sides) < 2:
            continue
        rhs = sides[1]
        if _stated(rhs) is not None and len(sides) == 2:
            continue
        try:
            made = _evaluate(rhs)
        except DimensionalityError:
            problems.append(f"{row}: its units do not go together")
            continue
        except (PintError, ValueError, SyntaxError, TypeError, NameError, ZeroDivisionError):
            unread += 1
            continue
        if first:
            problem = _first_row_problem(row, rhs, reply)
            if problem:
                problems.append(problem)
        stated = _stated(sides[2]) if len(sides) > 2 else None
        if stated is None and at + 1 < len(rows):
            following = [side.strip() for side in rows[at + 1].split("=")]
            if following[0] == lhs and len(following) == 2:
                stated = _stated(following[1])
        quantity = made if hasattr(made, "dimensionality") else _Q(made, "")
        if stated is not None:
            try:
                made_value = float(quantity.to(stated.units).magnitude)
                if not _agrees(made_value, float(stated.magnitude)):
                    problems.append(f"{row}: makes {quantity:~}, states {stated:~}")
            except PintError:
                problems.append(f"{row}: makes {quantity.units:~}, states {stated.units:~}")
        letter = _letter(lhs)
        expected = _UREG.get_dimensionality(_LETTERS[letter]) if letter in _LETTERS else None
        if expected is not None and quantity.dimensionality != expected:
            problems.append(
                f"{row}: {lhs} is {_LETTERS[letter]}, the row is {quantity.dimensionality}"
            )
    return problems, unread
