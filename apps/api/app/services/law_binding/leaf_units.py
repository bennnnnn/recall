"""The units a substituted row's numbers carry, read so the working can show them.

``reduction`` works a substitution down a layer at a time; this reads which unit each of
its numbers is in. A number is a given's when its value is; a count or a factor (½, 2)
stays bare. One reading of them is kept: the one whose units go together (a sum of one
unit, a function of a pure number), end in the answer's dimension, and read the most
numbers as givens. A worked number carries the unit its operation leaves it in.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

_SUMS = (ast.Add, ast.Sub)

# The attribute a number node carries its unit in (a Pint unit); a pure number has none.
UNIT = "unit"
# Factors a law writes as numbers (½, 2 in 2as, 4 in 4πr²): a value that equals a given
# may still be one of them.
_FACTORS = frozenset({0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 100.0})
# Readings tried before a row is called too ambiguous to label.
_MOST_READINGS = 4096


@dataclass(frozen=True)
class LeafUnits:
    """What the numbers of a substituted row are: each given's value with its unit."""

    # (the value as the row substitutes it, its Pint unit)
    given: Sequence[tuple[float, Any]]
    # A unit as it follows a number: ``\\,\\mathrm{m/s}``.
    shown: Callable[[Any], str]
    # The dimensions the row may end in (a Pint dimensionality; None for a pure number), or
    # None when any is right: a row that states its own value is checked by that value.
    answers: Sequence[Any] | None


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


def _options(value: float, units: LeafUnits) -> list[Any | None]:
    found: list[Any | None] = []
    for given, unit in units.given:
        # A constant may be written to four figures (the electron mass as 9.109e-31 kg).
        if math.isclose(value, given, rel_tol=1e-4) and unit not in found:
            found.append(unit)
    if not found or abs(value) in _FACTORS:
        found.append(None)
    return found


def _order(tree: ast.expr) -> list[int]:
    """The nodes of ``tree`` left to right, as the row writes them."""
    out: list[int] = []

    def visit(node: ast.expr) -> None:
        if isinstance(node, ast.BinOp):
            visit(node.left)
            out.append(id(node))
            visit(node.right)
            return
        out.append(id(node))
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                visit(child)

    visit(tree)
    return out


def _reaches(unit: Any | None, units: LeafUnits) -> bool:
    if units.answers is None:
        return True
    return (None if unit is None else unit.dimensionality) in units.answers


def label(tree: ast.expr, units: LeafUnits) -> bool:
    """Give each number of ``tree`` its unit, by the one reading of them that is consistent,
    ends in the answer's dimension, and reads the most numbers as givens; otherwise label
    nothing.

    A number equal to a given is that given unless its unit would not fit: in
    ``\\frac{4 + 1 \\cdot 0}{4 + 1}`` the masses are 4 kg and 1 kg, not counts. Of two
    equal numbers only one of which can be the given (2as with a = 2), the law's factor
    comes first, so the later one is the given.
    """
    leaves = [node for node in ast.walk(tree) if isinstance(node, ast.Constant)]
    # ``ast.walk`` is breadth first; the tie-break below reads the numbers left to right.
    order = _order(tree)
    leaves.sort(key=lambda leaf: order.index(id(leaf)))
    options = [_options(_exponent_value(leaf), units) for leaf in leaves]
    if all(option == [None] for option in options):
        return False
    best: tuple[int, tuple[bool, ...]] | None = None
    found: tuple[Any | None, ...] | None = None
    for count, choice in enumerate(product(*options)):
        if count >= _MOST_READINGS:
            return False
        try:
            chosen = {id(leaf): unit for leaf, unit in zip(leaves, choice, strict=True)}
            reached = _unit_of(tree, chosen)
        except (_Inconsistent, ValueError, TypeError):
            continue
        if not _reaches(reached, units):
            continue
        labelled = tuple(unit is not None for unit in choice)
        # More givens first; then the later of two equal numbers is the given.
        rank = (-sum(labelled), labelled)
        if best is None or rank < best:
            best, found = rank, choice
    if found is None or all(unit is None for unit in found):
        return False
    for leaf, unit in zip(leaves, found, strict=True):
        if unit is not None:
            setattr(leaf, UNIT, unit)
    return True
