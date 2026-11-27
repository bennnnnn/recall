# ruff: noqa: RUF003 -- the module reads × · ² as replies write them.
"""The units a line of working writes, read by Pint only where the reading is certain.

A working writes its units in TeX ("\\mathrm{m/s^2}", "\\,\\text{km/h}", "m²", "W/(m·K)",
"\\mathrm{km}\\,\\mathrm{h}^{-1}"). ``unit_after`` reads the whole run of unit groups at the
end of a side as one unit, and tells three cases apart: no unit written (""), a unit Pint
reads, and a unit written that is not read for certain (``UNREAD``, its text after it).

Not read for certain, so never converted and never held to another unit:
- an angle or a count of turns (rad, °, rev, rpm, cycles): Pint gives a radian no size, and
  whether a 2π belongs to the formula or the unit is the working's meaning, not its units
  (250 rev/min is 26.18 rad/s, though rev/min and rad/s are both "per second" to Pint);
- a temperature in degrees (°C, °F): an offset, not a size (400 K is 126.85 °C);
- a percentage, and anything Pint cannot parse.

The checks act only on what is certain: two units that are not both read are compared as
written, or not at all. Pure: no IO. The Pint registry is the app's one (``services.units``).
"""

from __future__ import annotations

import ast
import math
import re
from functools import lru_cache
from tokenize import TokenError
from typing import Any

from pint import Unit
from pint.errors import PintError

from app.modules.chat.tex_arithmetic import evaluate, plain_arithmetic
from app.services.units import get_unit_registry

# A unit written but not read for certain: its text follows, so two such units still differ.
UNREAD = "?"
# A unit group as the working writes one, its power with it ("\\mathrm{h}^{-1}").
_GROUP = re.compile(
    r"\\(?:mathrm|text|textrm|rm)\s*\{(?P<inner>[^{}]*)\}(?P<power>\s*\^\s*(?:\{[^{}]*\}|-?\d))?"
)
# What may stand between two groups of one unit: TeX spacing or a product sign.
_BETWEEN = re.compile(r"(?:\\[,;: !]|\s|~|\\cdot|\\times|·)*")
# A degree sign: of an angle or of a temperature's scale.
_DEGREE = re.compile(r"\^\s*\{?\s*\\circ\s*\}?|°|\\degree\b")
# Angles and counts of turns, percentages: a size Pint cannot hold for certain.
_NOT_SURE = re.compile(
    r"\b(?:rad|radians?|sr|deg|degrees?|rev|revolutions?|rpm|cycles?|turns?|rotations?)\b|%|°"
)
_SUPERSCRIPTS = {"²": "**2", "³": "**3", "⁻¹": "**-1", "⁻²": "**-2", "⁻³": "**-3"}
# A unit's own words a working writes that Pint names otherwise.
_SPELLED = {"Ω": "ohm", "µ": "u", "μ": "u", "hr": "hour", "min": "minute", "sec": "second"}
_MAX_UNIT_LENGTH = 40


def unit_after(tex: str) -> str:
    """The unit written at the end of a side, as Pint text; "" when none is written, and
    ``UNREAD`` with the unit's text when one is written that is not read for certain."""
    body = tex.rstrip()
    if re.search(r"(?:%|\\%)$", body):
        return f"{UNREAD}%"
    run: list[re.Match[str]] = []
    end = len(body)
    for match in reversed(list(_GROUP.finditer(body))):
        if _BETWEEN.fullmatch(body[match.end() : end]) is None:
            break
        run.insert(0, match)
        end = match.start()
    before = body[:end]
    if not run:
        degree = _DEGREE.search(body[-12:])
        return f"{UNREAD}°" if degree else ""
    text = "*".join(_pint_text(match["inner"], match["power"] or "") for match in run)
    if _DEGREE.search(before[-8:]) or quantity_unit(text) is None:
        return f"{UNREAD}{body[end:].strip()}"
    return text


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
    """``text`` (``unit_after``'s) as a Pint unit; None when it is empty, not read for
    certain (the module docstring) or anything Pint cannot read."""
    if not text or text.startswith(UNREAD) or len(text) > _MAX_UNIT_LENGTH:
        return None
    if _NOT_SURE.search(text) or "\\" in text:
        return None
    words = text
    for written, name in _SPELLED.items():
        words = re.sub(rf"(?<![A-Za-z]){re.escape(written)}(?![A-Za-z])", name, words)
    try:
        parsed = get_unit_registry().parse_units(words.replace(" ", "*"))
    except (PintError, AttributeError, TypeError, ValueError, SyntaxError, TokenError):
        return None
    return parsed if isinstance(parsed, Unit) else None


def read_for_certain(text: str) -> bool:
    """No unit written, or one Pint reads for certain."""
    return not text or quantity_unit(text) is not None


def converted(value: float, from_unit: Unit, to_unit: Unit) -> float | None:
    """``value`` in ``from_unit`` written in ``to_unit``; None when they are no one kind."""
    registry = get_unit_registry()
    try:
        result = registry.Quantity(value, from_unit).to(to_unit).magnitude
    except (PintError, ValueError, TypeError):
        return None
    number = float(result)
    return number if math.isfinite(number) else None


def in_base_units(value: float, unit: str) -> float | None:
    """``value`` in ``unit`` written in SI base units (632.8 nm is 6.328e-7); the value
    itself for no unit; None for a unit not read for certain."""
    if not unit:
        return value
    parsed = quantity_unit(unit)
    if parsed is None:
        return None
    registry = get_unit_registry()
    try:
        return float(registry.Quantity(value, parsed).to_base_units().magnitude)
    except (PintError, ValueError, TypeError):
        return None


def same_unit(first: Unit, second: Unit) -> bool:
    """The two units are one size: "m/s^2" and "m s^-2", "N·m" and "J"."""
    factor = converted(1.0, first, second)
    return factor is not None and math.isclose(factor, 1.0, rel_tol=1e-12)


def conversions(values: list[str]) -> list[float | None]:
    """Each value a given's statement writes after its first, worked from the first in its
    own unit: "9.00\\,\\mathrm{cm}" then "0.09\\,\\mathrm{m}" is [0.09]; None where a unit
    is not read for certain or the two are no one kind."""
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


def quantity(value: float, unit: str) -> Any:
    """``value`` in ``unit`` as a Pint quantity; dimensionless for no unit, None for a unit
    not read for certain."""
    registry = get_unit_registry()
    if not unit:
        return registry.Quantity(value, registry.dimensionless)
    parsed = quantity_unit(unit)
    return None if parsed is None else registry.Quantity(value, parsed)


def with_units(node: ast.AST, plain: str, quantities: dict[str, Any]) -> Any:
    """A plain side's ``node`` worked out with each number of ``quantities`` (by its text
    as written) as that quantity and any other as a pure number; None for anything but
    numbers, pi, the four operations, a whole power and a square root, or unlike kinds
    added."""
    registry = get_unit_registry()
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        written = ast.get_source_segment(plain, node) or ""
        number = registry.Quantity(float(node.value), registry.dimensionless)
        return quantities.get(written, number)
    if isinstance(node, ast.Name) and node.id == "pi":
        return registry.Quantity(math.pi, registry.dimensionless)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = with_units(node.operand, plain, quantities)
        return None if inner is None else -inner
    if isinstance(node, ast.BinOp):
        left = with_units(node.left, plain, quantities)
        right = with_units(node.right, plain, quantities)
        return None if left is None or right is None else _operated(node.op, left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sqrt":
        inner = with_units(node.args[0], plain, quantities) if len(node.args) == 1 else None
        return None if inner is None else inner**0.5
    return None


def _operated(op: ast.operator, left: Any, right: Any) -> Any:
    try:
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.Pow) and right.dimensionless and float(right.magnitude).is_integer():
            return left ** int(right.magnitude)
    except (PintError, TypeError, ValueError, ArithmeticError):
        return None
    return None
