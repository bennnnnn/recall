"""The units a substituted row's numbers carry, read from the law they were put into.

``reduction`` works a substitution down a layer at a time. A number in it stands for the
law's symbol in the same place: ``\\frac{48 - 8}{10}`` under ``\\frac{v_f - v_i}{t}`` is
v_f, v_i and t, and carries each one's unit when its value is that symbol's; a number the
law writes itself (½, the 2 of 2as) stays bare. The value is never matched alone: a 2 m/s
speed beside a 2 m cliff is told apart by where it stands. A row is labelled only when every
number is known this way, the units go together (a sum of one unit, a function of a pure
number) and the row ends in the dimension of the quantity it states; otherwise it stays as
written. A worked number carries the unit its operation leaves it in.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_SUMS = (ast.Add, ast.Sub)

# The attribute a number node carries its unit in (a Pint unit); a pure number has none.
UNIT = "unit"
# What a law symbol's leaf id starts with, so a symbol never reads as an angle or as π.
SYMBOL = "$"


@dataclass(frozen=True)
class LeafUnits:
    """What a substituted row's numbers may stand for, and what the row must end in."""

    # The law's right sides in its symbols, any of which the row may put numbers into.
    formulas: Sequence[str]
    # Each symbol's values as a row may substitute them, with their Pint units.
    known: Mapping[str, Sequence[tuple[float, Any]]]
    # A unit as it follows a number: ``\\,\\mathrm{m/s}``.
    shown: Callable[[Any], str]
    # The dimensions the row's quantity may have, given the value it reaches (a Pint
    # dimensionality; None for a pure number). None of them: the row stays bare.
    dimensions: Callable[[float], Collection[Any]]


class _Inconsistent(ValueError):
    """These units do not go together: a sum of two dimensions, a sine of a length."""


def unit_of_node(node: ast.expr) -> Any | None:
    return getattr(node, UNIT, None)


def _pure(unit: Any | None) -> Any | None:
    return None if unit is None or unit.dimensionless else unit


def _times(left: Any | None, right: Any | None, power: int) -> Any | None:
    if right is None:
        return left
    right = right**power
    return _pure(right if left is None else left * right)


def _summed(left: Any | None, right: Any | None, zeros: tuple[bool, bool]) -> Any | None:
    """The unit of a sum: its terms' one unit (Ω·A is V), a bare 0 taking the other's."""
    if left is None and zeros[0]:
        return right
    if right is None and zeros[1]:
        return left
    if left == right:
        return left
    if left is None or right is None or left.dimensionality != right.dimensionality:
        raise _Inconsistent("a sum of two units")
    if not math.isclose(float((1 * left).to(right).magnitude), 1.0):
        raise _Inconsistent("a sum of two scales")
    return right


def _zero(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value == 0 and unit_of_node(node) is None


def _exponent_value(node: ast.expr) -> float:
    """A power's exponent as a number: 2, or ⅓ written \\frac{1}{3}."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.UnaryOp):
        return -_exponent_value(node.operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _exponent_value(node.left) / _exponent_value(node.right)
    raise _Inconsistent("a unit to a worked power")


def carried(node: ast.expr) -> Any | None:
    """The unit an operation of numbers leaves its result in: the operands' combined."""
    if isinstance(node, ast.UnaryOp):
        return unit_of_node(node.operand)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        inner = unit_of_node(node.args[0])
        if inner is None or node.func.id not in {"sqrt", "abs"}:
            return None
        return _pure(inner**0.5) if node.func.id == "sqrt" else inner
    if not isinstance(node, ast.BinOp):
        return None
    left, right = unit_of_node(node.left), unit_of_node(node.right)
    if isinstance(node.op, _SUMS):
        try:
            return _summed(left, right, (_zero(node.left), _zero(node.right)))
        except (_Inconsistent, ValueError, TypeError):
            return None
    if isinstance(node.op, ast.Pow):
        if left is None:
            return None
        try:
            return _pure(left ** _exponent_value(node.right))
        except (_Inconsistent, ZeroDivisionError):
            return None
    return _times(left, right, 1 if isinstance(node.op, ast.Mult) else -1)


def _unit_of(node: ast.expr, chosen: dict[int, Any]) -> Any | None:
    """The unit ``node`` works out to, its numbers read as ``chosen``; raises when they do
    not go together."""
    if isinstance(node, ast.Constant):
        return chosen.get(id(node))
    if isinstance(node, ast.Name):
        return None
    if isinstance(node, ast.UnaryOp):
        return _unit_of(node.operand, chosen)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        inner = _unit_of(node.args[0], chosen)
        if node.func.id == "sqrt":
            return None if inner is None else _pure(inner**0.5)
        if node.func.id == "abs":
            return inner
        if inner is not None:
            raise _Inconsistent(node.func.id)
        return None
    if not isinstance(node, ast.BinOp):
        raise _Inconsistent("node")
    left, right = _unit_of(node.left, chosen), _unit_of(node.right, chosen)
    if isinstance(node.op, _SUMS):
        zeros = tuple(
            isinstance(side, ast.Constant) and side.value == 0 and chosen.get(id(side)) is None
            for side in (node.left, node.right)
        )
        return _summed(left, right, (zeros[0], zeros[1]))
    if isinstance(node.op, ast.Pow):
        if right is not None:
            raise _Inconsistent("a power with a unit")
        if left is None:
            return None
        return _pure(left ** _exponent_value(node.right))
    return _times(left, right, 1 if isinstance(node.op, ast.Mult) else -1)


def _align(law: ast.expr, row: ast.expr, found: dict[int, tuple[str, int]]) -> bool:
    """Whether ``row`` is ``law`` with numbers put in, noting the symbol each number replaced
    (and its sign: a written -0.04 under -h_o is h_o = 0.04)."""
    if isinstance(row, ast.Constant):
        symbol = _symbol(law)
        if symbol is not None:
            found[id(row)] = (symbol, 1)
            return True
        if isinstance(law, ast.UnaryOp) and isinstance(law.op, ast.USub):
            negated = _symbol(law.operand)
            if negated is not None:
                found[id(row)] = (negated, -1)
                return True
        return isinstance(law, ast.Constant) and _number(law) == _number(row)
    if isinstance(row, ast.Name):
        # An angle under its symbol (θ), or π under π.
        return isinstance(law, ast.Name)
    if isinstance(row, ast.BinOp) and isinstance(law, ast.BinOp):
        return (
            type(row.op) is type(law.op)
            and _align(law.left, row.left, found)
            and _align(law.right, row.right, found)
        )
    if isinstance(row, ast.UnaryOp) and isinstance(law, ast.UnaryOp):
        return type(row.op) is type(law.op) and _align(law.operand, row.operand, found)
    if isinstance(row, ast.Call) and isinstance(law, ast.Call):
        if not isinstance(row.func, ast.Name) or not isinstance(law.func, ast.Name):
            return False
        return row.func.id == law.func.id and _align(law.args[0], row.args[0], found)
    return False


def _symbol(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name) and node.id.startswith(SYMBOL):
        return node.id[len(SYMBOL) :]
    return None


def _number(node: ast.Constant) -> float:
    return float(node.value) if isinstance(node.value, int | float) else math.nan


def _chosen(
    row: ast.expr, found: dict[int, tuple[str, int]], units: LeafUnits
) -> dict[int, Any] | None:
    """Each number's unit by the symbol it replaced, when its value is that symbol's."""
    chosen: dict[int, Any] = {}
    for leaf in ast.walk(row):
        if not isinstance(leaf, ast.Constant) or id(leaf) not in found:
            continue
        symbol, sign = found[id(leaf)]
        value = sign * _number(leaf)
        unit = next(
            (
                unit
                for known, unit in units.known.get(symbol, ())
                # A constant may be written to four figures (the electron mass, 9.109e-31).
                if math.isclose(value, known, rel_tol=1e-4, abs_tol=1e-12)
            ),
            False,
        )
        if unit is False:
            return None
        chosen[id(leaf)] = _pure(unit)
    return chosen


def label(row: ast.expr, laws: Sequence[ast.expr], units: LeafUnits, value: float) -> bool:
    """Give each number of ``row`` the unit of the law symbol it replaced, when one law fits
    it, every number is known, the units go together and the row ends in its quantity's
    dimension; otherwise label nothing."""
    for law in laws:
        found: dict[int, tuple[str, int]] = {}
        if not _align(law, row, found):
            continue
        chosen = _chosen(row, found, units)
        if chosen is None or all(unit is None for unit in chosen.values()):
            continue
        try:
            reached = _unit_of(row, chosen)
        except (_Inconsistent, ValueError, TypeError):
            continue
        if (None if reached is None else reached.dimensionality) not in units.dimensions(value):
            continue
        for leaf in ast.walk(row):
            if isinstance(leaf, ast.Constant) and chosen.get(id(leaf)) is not None:
                setattr(leaf, UNIT, chosen[id(leaf)])
        return True
    return False
