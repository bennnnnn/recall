"""Evaluate and typeset the arithmetic of an expression operation.

A catalog expression is plain arithmetic in the operation's variable names:
``v - a*t``, ``sqrt(v**2 - 2*a*d)``. It is parsed once into a small tree of
numbers, names, the four operations, powers and a closed list of functions,
and anything else is refused when the catalog loads. Nothing is executed:
the tree is walked. The same tree prints the rearranged formula with the
law's symbols and the substitution with the values the solver used, so the
two can never disagree with the number.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Callable, Mapping
from functools import lru_cache

from app.modules.physics.display import latex_given
from app.modules.physics.solvers.common import (
    _BIG_G,
    _COULOMB_K,
    _ELEMENTARY_CHARGE,
    _EPSILON_0,
    _MU_0,
    _PLANCK_H,
    _SPEED_OF_LIGHT,
)

_FUNCTIONS: dict[str, Callable[[float], float]] = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "exp": math.exp,
    "log": math.log,
}
_FUNCTION_LATEX = {
    "sin": r"\sin",
    "cos": r"\cos",
    "tan": r"\tan",
    "asin": r"\arcsin",
    "acos": r"\arccos",
    "atan": r"\arctan",
    "log": r"\ln",
}
# Physical constants by the name an expression uses, with the symbol the
# formula shows. The values are the solvers' own (CODATA via Pint).
_CONSTANTS = {
    "pi": (math.pi, r"\pi"),
    "mu_0": (_MU_0, r"\mu_0"),
    "epsilon_0": (_EPSILON_0, r"\varepsilon_0"),
    "k_e": (_COULOMB_K, "k_e"),
    "G_grav": (_BIG_G, "G"),
    "h_planck": (_PLANCK_H, "h"),
    "c_light": (_SPEED_OF_LIGHT, "c"),
    "e_charge": (_ELEMENTARY_CHARGE, "e"),
}
_BINARY = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_UNARY = (ast.USub, ast.UAdd)


class ExpressionError(ValueError):
    """A catalog expression uses something this module does not evaluate."""


@lru_cache(maxsize=512)
def parse(expression: str) -> ast.expr:
    """The checked tree of one expression. Raises on anything not arithmetic."""
    try:
        tree = ast.parse(expression, mode="eval").body
    except SyntaxError as exc:
        raise ExpressionError(f"not an expression: {expression}") from exc
    for node in ast.walk(tree):
        _check(node, expression)
    return tree


def _check(node: ast.AST, expression: str) -> None:
    if isinstance(node, ast.BinOp | ast.UnaryOp | ast.Name | ast.Load | ast.Call):
        if isinstance(node, ast.BinOp) and not isinstance(node.op, _BINARY):
            raise ExpressionError(f"operator not allowed in {expression}")
        if isinstance(node, ast.UnaryOp) and not isinstance(node.op, _UNARY):
            raise ExpressionError(f"operator not allowed in {expression}")
        if isinstance(node, ast.Call) and not (
            isinstance(node.func, ast.Name)
            and node.func.id in _FUNCTIONS
            and len(node.args) == 1
            and not node.keywords
        ):
            raise ExpressionError(f"call not allowed in {expression}")
        return
    if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
        return
    if isinstance(node, ast.operator | ast.unaryop):
        return
    raise ExpressionError(f"{type(node).__name__} not allowed in {expression}")


def names(expression: str) -> frozenset[str]:
    """The variable names an expression reads; functions and constants excluded."""
    tree = parse(expression)
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    return frozenset(
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id not in called and node.id not in _CONSTANTS
    )


def _number(node: ast.Constant) -> float:
    """A literal ``parse`` already checked is an int or a float."""
    if not isinstance(node.value, int | float) or isinstance(node.value, bool):
        raise ExpressionError(f"not a number: {node.value!r}")
    return float(node.value)


def evaluate(expression: str, values: Mapping[str, float]) -> float:
    """The number the expression gives. A domain error is a ValueError."""
    return _value(parse(expression), values)


def _value(node: ast.expr, values: Mapping[str, float]) -> float:
    if isinstance(node, ast.Constant):
        return _number(node)
    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id][0]
        return values[node.id]
    if isinstance(node, ast.UnaryOp):
        operand = _value(node.operand, values)
        return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return _FUNCTIONS[node.func.id](_value(node.args[0], values))
    if not isinstance(node, ast.BinOp):
        raise ExpressionError(f"cannot evaluate {type(node).__name__}")
    left, right = _value(node.left, values), _value(node.right, values)
    if isinstance(node.op, ast.Add):
        return left + right
    if isinstance(node.op, ast.Sub):
        return left - right
    if isinstance(node.op, ast.Mult):
        return left * right
    if isinstance(node.op, ast.Div):
        if right == 0:
            raise ValueError("division by zero")
        return left / right
    result = left**right
    if isinstance(result, complex):
        raise ValueError("no real power")
    return float(result)


def to_latex(
    expression: str,
    symbols: Mapping[str, str],
    values: Mapping[str, float] | None = None,
) -> str:
    """The expression typeset: with the law's symbols, or with ``values`` plugged in."""
    return _latex(parse(expression), symbols, values)


_PRECEDENCE = {ast.Add: 1, ast.Sub: 1, ast.Mult: 2, ast.Div: 2, ast.Pow: 4}


def _precedence(node: ast.expr) -> int:
    if isinstance(node, ast.BinOp):
        return _PRECEDENCE[type(node.op)]
    if isinstance(node, ast.UnaryOp):
        return 3
    return 5


def _plugged(node: ast.expr, values: Mapping[str, float] | None) -> bool:
    """A leaf shown as a number: a literal, or a name with a value plugged in."""
    return isinstance(node, ast.Constant) or (
        isinstance(node, ast.Name) and values is not None and node.id != "pi"
    )


def _negative_leaf(node: ast.expr, values: Mapping[str, float] | None) -> bool:
    if isinstance(node, ast.Constant):
        return _number(node) < 0
    return (
        isinstance(node, ast.Name)
        and values is not None
        and node.id in values
        and values[node.id] < 0
    )


def _wrapped(
    node: ast.expr,
    symbols: Mapping[str, str],
    values: Mapping[str, float] | None,
    above: int,
) -> str:
    text = _latex(node, symbols, values)
    if _precedence(node) < above or (above >= 2 and _negative_leaf(node, values)):
        return f"({text})"
    return text


def _latex(
    node: ast.expr,
    symbols: Mapping[str, str],
    values: Mapping[str, float] | None,
) -> str:
    if isinstance(node, ast.Constant):
        return latex_given(_number(node))
    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            value, symbol = _CONSTANTS[node.id]
            # A substitution shows a constant's value, as every solver row does; π stays π.
            return latex_given(value) if values is not None and node.id != "pi" else symbol
        if values is not None:
            return latex_given(values[node.id])
        return symbols.get(node.id, node.id)
    if isinstance(node, ast.UnaryOp):
        operand = _wrapped(node.operand, symbols, values, 3)
        return f"-{operand}" if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        inner = _latex(node.args[0], symbols, values)
        name = node.func.id
        if name == "sqrt":
            return rf"\sqrt{{{inner}}}"
        if name == "exp":
            return rf"e^{{{inner}}}"
        return f"{_FUNCTION_LATEX[name]}({inner})"
    if not isinstance(node, ast.BinOp):
        raise ExpressionError(f"cannot typeset {type(node).__name__}")
    if isinstance(node.op, ast.Div):
        top = _latex(node.left, symbols, values)
        bottom = _latex(node.right, symbols, values)
        return rf"\frac{{{top}}}{{{bottom}}}"
    if isinstance(node.op, ast.Pow):
        base = _wrapped(node.left, symbols, values, 5)
        return f"{base}^{{{_latex(node.right, symbols, values)}}}"
    if isinstance(node.op, ast.Mult):
        left = _wrapped(node.left, symbols, values, 2)
        right = _wrapped(node.right, symbols, values, 2)
        # Numbers side by side need a dot; symbols are written together.
        joined = _plugged(_rightmost(node.left), values) and _plugged(_leftmost(node.right), values)
        return rf"{left} \cdot {right}" if joined else f"{left} {right}"
    operator = "+" if isinstance(node.op, ast.Add) else "-"
    left = _latex(node.left, symbols, values)
    # a - (b + c) keeps its brackets, and so does a negative number after a sign.
    right = _wrapped(node.right, symbols, values, 2 if operator == "-" else 1)
    if _negative_leaf(node.right, values):
        right = f"({right})"
    return f"{left} {operator} {right}"


def _leftmost(node: ast.expr) -> ast.expr:
    while isinstance(node, ast.BinOp) and not isinstance(node.op, ast.Div):
        node = node.left
    return node


def _rightmost(node: ast.expr) -> ast.expr:
    while isinstance(node, ast.BinOp) and not isinstance(node.op, ast.Div | ast.Pow):
        node = node.right
    return node
