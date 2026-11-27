# ruff: noqa: RUF003 -- the module reads × · ² as replies write them.
"""The units a line of working writes, read by Pint: a given's conversion held to its value
and a value carried into another unit of its kind.

A working writes its units in TeX ("\\mathrm{m/s^2}", "\\,\\text{km/h}", "m²", "W/(m·K)");
``quantity_unit`` turns one into a Pint unit, or None when Pint cannot read it. A count of
turns ("rev", "rpm", "cycles") is a count, never 2π radians: "ω = 2πN" with N in rev/min
already holds its 2π. A temperature in degrees has an offset no product carries and an angle
is no physical size of a quantity, so neither is read.

Pure: no IO. The Pint registry is the app's one (``services.units``).
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from tokenize import TokenError

from pint import Unit
from pint.errors import PintError

from app.modules.chat.tex_arithmetic import evaluate, plain_arithmetic
from app.services.units import get_unit_registry

# A unit group as the working writes one after a number, its power with it.
UNIT_TEX = re.compile(
    r"(?:\\[,; !]|\\ |\s|~)*\\(?:mathrm|text|textrm|rm)\s*\{(?P<inner>[^{}]*)\}"
    r"(?P<power>\s*\^\s*(?:\{[^{}]*\}|-?\d))?"
)
# A count of turns: a number of them per minute is a rate, with no 2π in it.
_TURNS = re.compile(r"\b(?:rev(?:olution)?s?|cycles?|turns?|rotations?)\b")
_RPM = re.compile(r"\brpm\b")
# What Pint never reads as the size of a quantity: a temperature with its offset, an angle.
_NOT_A_SIZE = re.compile(r"°|\\circ|deg|degC|degF|celsius|fahrenheit|\brad\b(?!/)")
_SUPERSCRIPTS = {"²": "**2", "³": "**3", "⁻¹": "**-1", "⁻²": "**-2", "⁻³": "**-3"}
# A unit's own words a working writes that Pint names otherwise.
_SPELLED = {"Ω": "ohm", "µ": "u", "μ": "u", "hr": "hour", "min": "minute", "sec": "second"}
_MAX_UNIT_LENGTH = 40


def unit_after(tex: str) -> str:
    """The unit TeX written at the end of a side ("\\,\\mathrm{m/s^2}"), as Pint text, or ""."""
    groups = list(UNIT_TEX.finditer(tex))
    if not groups:
        return ""
    last = groups[-1]
    if tex[last.end() :].strip() or _DEGREE_BEFORE.search(tex[: last.start()]):
        return ""
    return _pint_text(last.group("inner"), last.group("power") or "")


# "100\,^\circ\mathrm{C}": a temperature's degree sign before its letter.
_DEGREE_BEFORE = re.compile(r"(?:\\circ|°)\s*\}?\s*$")


def _pint_text(inner: str, power: str) -> str:
    text = inner.strip().replace("\\Omega", "Ω").replace("\\mu ", "µ").replace("\\mu", "µ")
    for glyph, written in _SUPERSCRIPTS.items():
        text = text.replace(glyph, written)
    text = text.replace("·", "*").replace("⋅", "*").replace("\\cdot", "*").replace("^", "**")
    text = text.replace("{", "(").replace("}", ")")
    text = re.sub(r"\s*\*\s*", "*", text)
    # "\\text{m/s}^2" is drawn m/s²: the power is its last symbol's.
    exponent = re.sub(r"[\s^{}]", "", power)
    return f"{text}**{exponent}" if exponent else text


@lru_cache(maxsize=512)
def quantity_unit(text: str) -> Unit | None:
    """``text`` (``unit_after``'s) as a Pint unit; None when it is empty, an angle, a
    temperature or anything Pint cannot read."""
    if not text or len(text) > _MAX_UNIT_LENGTH or _NOT_A_SIZE.search(text) or "\\" in text:
        return None
    words = _RPM.sub("1/minute", _TURNS.sub("1", text))
    for written, name in _SPELLED.items():
        words = re.sub(rf"(?<![A-Za-z]){re.escape(written)}(?![A-Za-z])", name, words)
    try:
        parsed = get_unit_registry().parse_units(words.replace(" ", "*"))
    except (PintError, AttributeError, TypeError, ValueError, SyntaxError, TokenError):
        return None
    return parsed if isinstance(parsed, Unit) else None


def converted(value: float, from_unit: Unit, to_unit: Unit) -> float | None:
    """``value`` in ``from_unit`` written in ``to_unit``; None when they are no one kind."""
    registry = get_unit_registry()
    try:
        result = registry.Quantity(value, from_unit).to(to_unit).magnitude
    except (PintError, ValueError, TypeError):
        return None
    number = float(result)
    return number if math.isfinite(number) else None


def same_unit(first: Unit, second: Unit) -> bool:
    """The two units are one size: "m/s^2" and "m s^-2", "N·m" and "J"."""
    factor = converted(1.0, first, second)
    return factor is not None and math.isclose(factor, 1.0, rel_tol=1e-12)


def conversions(values: list[str]) -> list[float | None]:
    """Each value a given's statement writes after its first, worked from the first in its
    own unit: "9.00\\,\\mathrm{cm}" then "0.09\\,\\mathrm{m}" is [0.09]; None where a unit
    cannot be read or the two are no one kind."""
    first = plain_arithmetic(values[0]) if values else None
    number = evaluate(first) if first is not None else None
    source = quantity_unit(unit_after(values[0])) if values else None
    found: list[float | None] = []
    for later in values[1:]:
        target = quantity_unit(unit_after(later))
        if number is None or source is None or target is None:
            found.append(None)
            continue
        found.append(converted(number, source, target))
    return found
