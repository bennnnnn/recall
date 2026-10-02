# ruff: noqa: RUF001, RUF002, RUF003 -- the point of this module is ×, ·, Ω and superscripts.
"""How physics shows a number and a unit: one formatter for every answer.

A verified answer has three significant figures, never calculator notation,
and upright units. Scientific notation is used outside [10⁻³, 10⁵). A given
is echoed with the figures the user typed (up to six), never rounded to the
answer's precision.

Two spellings of the same value: plain text with Unicode symbols for guards,
logs and the web reader (``3.31 × 10⁻¹⁹ J``), and LaTeX for the answer card
and the working (``3.31 \\times 10^{-19}\\,\\mathrm{J}``).
"""

from __future__ import annotations

import math
import re

ANSWER_FIGURES = 3
GIVEN_FIGURES = 6
_SCIENTIFIC_BELOW = 1e-3
_SCIENTIFIC_FROM = 1e5

_SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def _trim(text: str) -> str:
    return text.rstrip("0").rstrip(".") if "." in text else text


def _parts(value: float, figures: int) -> tuple[str, int | None]:
    """(mantissa, exponent) after rounding, exponent None for plain form.

    Rounding comes first, so 99999.7 is 1 × 10⁵ rather than 100000, and the
    plain form is fixed-point, so 22620 at three figures is 22600.
    """
    mantissa, exponent_text = f"{value:.{figures - 1}e}".split("e")
    exponent = int(exponent_text)
    rounded = float(f"{mantissa}e{exponent}")
    if rounded != 0 and not _SCIENTIFIC_BELOW <= abs(rounded) < _SCIENTIFIC_FROM:
        return _trim(mantissa), exponent
    decimals = max(figures - 1 - exponent, 0)
    shown = _trim(f"{rounded:.{decimals}f}")
    return ("0" if shown in {"-0", "+0"} else shown), None


def plain_number(value: float, figures: int = ANSWER_FIGURES) -> str:
    """``39.6``, ``0.216``, ``3.31 × 10⁻¹⁹``."""
    if not math.isfinite(value):
        return str(value)
    mantissa, exponent = _parts(value, figures)
    if exponent is None:
        return mantissa
    return f"{mantissa} × 10{str(exponent).translate(_SUPERSCRIPT)}"


def latex_given(value: float) -> str:
    """A given or a working value with the figures the user wrote, up to six."""
    return latex_number(value, GIVEN_FIGURES)


def latex_number(value: float, figures: int = ANSWER_FIGURES) -> str:
    """``39.6``, ``3.31 \\times 10^{-19}``."""
    if not math.isfinite(value):
        return str(value)
    mantissa, exponent = _parts(value, figures)
    if exponent is None:
        return mantissa
    return rf"{mantissa} \times 10^{{{exponent}}}"


# Spelled-out units a question may carry, as the symbol a textbook prints.
_SPELLED = {
    "seconds": "s",
    "second": "s",
    "secs": "s",
    "sec": "s",
    "minutes": "min",
    "minute": "min",
    "mins": "min",
    "hours": "h",
    "hour": "h",
    "hrs": "h",
    "hr": "h",
    "meters": "m",
    "metres": "m",
    "meter": "m",
    "metre": "m",
    "kilometers": "km",
    "kilometres": "km",
    "centimeters": "cm",
    "centimetres": "cm",
    "kilograms": "kg",
    "kilogram": "kg",
    "grams": "g",
    "gram": "g",
    "newtons": "N",
    "newton": "N",
    "joules": "J",
    "joule": "J",
    "watts": "W",
    "watt": "W",
    "volts": "V",
    "volt": "V",
    "amps": "A",
    "amperes": "A",
    "ampere": "A",
    "ohms": "ohm",
    "degrees": "deg",
    "degree": "deg",
    "°": "deg",
    "uC": "µC",
    "uF": "µF",
    "um": "µm",
    "micrometers": "µm",
}
# Solver unit spellings with a symbol of their own.
_PLAIN_SYMBOLS = {"deg": "°", "ohm": "Ω", "degC": "°C", "D": "D", "": ""}
_LATEX_SYMBOLS = {
    "deg": r"^\circ",
    "ohm": r"\,\Omega",
    "degC": r"\,^\circ\mathrm{C}",
    "%": r"\,\%",
    "": "",
}
_POWER = re.compile(r"\^\{?(-?\d+)\}?")

# A unit written in words, by the unit it means: "miles per hour" is mph, and
# "ohm m" is Ω·m. Spelling it back out would print "miles·per·hour".
_WORD_UNIT_SYMBOLS = {
    "pascal * second": "Pa·s",
    "degC": "°C",
    "joule / kilogram / kelvin": "J/(kg·K)",
    "kilogram * meter / second": "kg·m/s",
    "kilogram * meter ** 2": "kg·m²",
    "meter / second ** 2": "m/s²",
    "mile / hour": "mph",
    "newton * meter": "N·m",
    "newton * second": "N·s",
    "ohm * meter": "Ω·m",
    "1 / kelvin": "K⁻¹",
}


def _symbol(unit: str) -> str:
    return _SPELLED.get(unit, _SPELLED.get(unit.lower(), unit)) if unit else unit


def _written_in_words(unit: str) -> str | None:
    """The symbol for a unit written as words ("miles per hour"), if it is one."""
    if " " not in unit.strip():
        return None
    from app.modules.physics.givens import unit_expression

    expression = unit_expression(unit.strip())
    return None if expression is None else _WORD_UNIT_SYMBOLS.get(expression)


def plain_unit(unit: str) -> str:
    """``m/s²``, ``kg·m²``, ``J/(kg·K)``, ``°``, ``Ω``."""
    unit = _symbol(unit)
    if unit in _PLAIN_SYMBOLS:
        return _PLAIN_SYMBOLS[unit]
    words = _written_in_words(unit)
    if words is not None:
        return words
    spelled = _grouped_denominator(unit).replace("*", "·").replace(" ", "·")
    return _POWER.sub(lambda match: match.group(1).translate(_SUPERSCRIPT), spelled)


def latex_unit(unit: str) -> str:
    """The unit as it follows a number in LaTeX, leading space included.

    The unit is an upright text run holding the plain spelling (``m/s²``,
    ``µC``): MathText draws a ``\\mathrm`` group as written, so a nested
    command or brace inside it would show raw.
    """
    unit = _symbol(unit)
    if unit in _LATEX_SYMBOLS:
        return _LATEX_SYMBOLS[unit]
    return rf"\,\mathrm{{{plain_unit(unit)}}}"


def _grouped_denominator(unit: str) -> str:
    """``J/kg/K`` reads as ``J/(kg·K)``: a second slash would divide by K twice."""
    head, *rest = unit.split("/")
    if len(rest) < 2:
        return unit
    return f"{head}/({'*'.join(rest)})"


# Pint unit names in catalog dimensions, as their SI symbols.
_SI_SYMBOLS = {
    "meter": "m",
    "second": "s",
    "kilogram": "kg",
    "newton": "N",
    "joule": "J",
    "watt": "W",
    "pascal": "Pa",
    "kelvin": "K",
    "ampere": "A",
    "coulomb": "C",
    "volt": "V",
    "ohm": "ohm",
    "farad": "F",
    "henry": "H",
    "tesla": "T",
    "weber": "Wb",
    "hertz": "Hz",
    "mole": "mol",
    "radian": "rad",
}
# The one catalog dimension that is not SI: a value in rpm is solved in rad/s.
_NON_SI = {"revolution / minute": "radian / second"}


def si_symbol(dimension: str) -> str:
    """``joule / kilogram / kelvin`` as ``J/kg/K``: the SI unit a solver works in."""
    expression = _NON_SI.get(dimension, dimension)
    for name, symbol in _SI_SYMBOLS.items():
        expression = re.sub(rf"\b{name}\b", symbol, expression)
    return expression.replace(" ** ", "^").replace(" / ", "/").replace(" * ", "*")


def plain_quantity(value: float, unit: str, figures: int = ANSWER_FIGURES) -> str:
    shown_unit = plain_unit(unit)
    if not shown_unit:
        return plain_number(value, figures)
    gap = "" if shown_unit == "°" else " "
    return f"{plain_number(value, figures)}{gap}{shown_unit}"


def latex_quantity(value: float, unit: str, figures: int = ANSWER_FIGURES) -> str:
    return f"{latex_number(value, figures)}{latex_unit(unit)}"


_NUMBER_IN_TEXT = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\w.])")


def plain_numbers_in(text: str) -> str:
    """A note or a scene label with its numbers at answer precision."""
    return _NUMBER_IN_TEXT.sub(lambda match: plain_number(float(match.group())), text)


_E_NOTATION = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)[eE]([-+]?\d+)(?![\w.])")
_LONG_DECIMAL = re.compile(r"(?<![\w.])(-?\d+\.\d{7,})(?![\w.])")


def typeset_numbers(row: str) -> str:
    """A LaTeX row without calculator notation or float noise.

    ``6.6261e-34`` becomes ``6.6261 \\times 10^{-34}``; a decimal that floating
    point stretched past six figures (``0.30000000000000004``) is cut back.
    Integers and the user's own decimals are left as written. A number raised
    to a power keeps its brackets once it is a product: ``7e+06^3`` is
    ``(7 \\times 10^{6})^3``, not a double superscript.
    """

    def scientific(match: re.Match[str]) -> str:
        shown = latex_number(float(match.group(0)), GIVEN_FIGURES)
        raised = match.string.startswith("^", match.end())
        return f"({shown})" if raised and r"\times" in shown else shown

    row = _E_NOTATION.sub(scientific, row)
    return _LONG_DECIMAL.sub(lambda match: latex_number(float(match.group(1)), GIVEN_FIGURES), row)
