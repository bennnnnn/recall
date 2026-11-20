"""The pieces a written-down setup is read and solved with: units by pint, an equation's tree
as SymPy, a side's kind, and the checked setup itself. ``formal.solve`` solves with them and
``formal.checks`` tests a setup's relations with them; neither imports the other."""

from __future__ import annotations

import ast
import math
import unicodedata
from dataclasses import dataclass, field
from typing import Any

_MAX_SYMBOL = 24


def unit_registry() -> Any:
    from app.services.units import get_unit_registry

    return get_unit_registry()


def _unit_text(unit: str) -> str:
    text = unicodedata.normalize("NFKC", unit).strip()
    if not text:
        return "dimensionless"
    for old, new in (("°C", "degC"), ("ºC", "degC"), ("°F", "degF"), ("°", "degree")):
        text = text.replace(old, new)
    text = text.replace("²", "**2").replace("³", "**3").replace("^", "**")
    text = text.replace("·", "*").replace("Ω", "ohm").replace("µ", "u").replace("μ", "u")
    text = text.replace("%", "percent")
    # "J/kg*K" is J/(kg*K) as a science book writes it, not (J/kg)*K as pint reads it.
    numerator, slash, denominator = text.partition("/")
    if slash and "(" not in text and "/" not in denominator and "*" in denominator:
        return f"{numerator}/({denominator})"
    return text


def as_quantity(value: float, unit: str) -> Any:
    """``value`` in ``unit`` as pint reads it ("°C", "Ω", "J/kg*K" as a book writes them)."""
    registry = unit_registry()
    return registry.Quantity(value, _unit_text(unit))


def sympy_tree(node: ast.expr, symbols: dict[str, Any]) -> Any:
    import sympy

    functions = {
        "sqrt": sympy.sqrt,
        "sin": sympy.sin,
        "cos": sympy.cos,
        "tan": sympy.tan,
        "asin": sympy.asin,
        "acos": sympy.acos,
        "atan": sympy.atan,
        "exp": sympy.exp,
        "log": sympy.log,
        "abs": sympy.Abs,
    }
    if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
        return sympy.nsimplify(node.value) if isinstance(node.value, int) else node.value
    if isinstance(node, ast.Name):
        if node.id == "pi":
            return sympy.pi
        if node.id not in symbols:
            if not node.id.isidentifier() or len(node.id) > _MAX_SYMBOL or len(symbols) > 40:
                raise ValueError(f"symbol {node.id}")
            symbols[node.id] = sympy.Symbol(node.id, real=True)  # declared by its equation
        return symbols[node.id]
    if isinstance(node, ast.UnaryOp):
        inner = sympy_tree(node.operand, symbols)
        return -inner if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.BinOp):
        left, right = sympy_tree(node.left, symbols), sympy_tree(node.right, symbols)
        operations = {
            ast.Add: lambda: left + right,
            ast.Sub: lambda: left - right,
            ast.Mult: lambda: left * right,
            ast.Div: lambda: left / right,
            ast.Pow: lambda: left**right,
        }
        build = operations.get(type(node.op))
        if build is None:
            raise ValueError("operator")
        return build()
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return functions[node.func.id](sympy_tree(node.args[0], symbols))
    raise ValueError(f"{type(node).__name__} not allowed")


_NUMPY_FUNCTIONS = ("sqrt", "sin", "cos", "tan", "exp", "log")


_NUMPY_INVERSE = {"asin": "arcsin", "acos": "arccos", "atan": "arctan"}


def kind_of(expression: Any, units: dict[Any, Any]) -> Any:
    """The quantity ``expression`` is when each symbol is 1 of its unit (only its kind
    counts); pint raises when a sum mixes kinds or a function's argument has a unit."""
    import numpy as np
    import sympy

    registry = unit_registry()
    functions: dict[str, Any] = {name: getattr(np, name) for name in _NUMPY_FUNCTIONS}
    functions |= {name: getattr(np, inverse) for name, inverse in _NUMPY_INVERSE.items()}
    functions |= {"Abs": abs, "pi": math.pi}
    order = sorted(expression.free_symbols, key=str)
    value = sympy.lambdify(order, expression, modules=[functions])(
        *(registry.Quantity(1.0, units[symbol]) for symbol in order)
    )
    return value if hasattr(value, "dimensionality") else registry.Quantity(value)


@dataclass
class Setup:
    """A checked setup: each symbol, each given's value in base SI and the number the
    question writes, each symbol's kind, and the equations as SymPy sides."""

    symbols: dict[str, Any]
    values: dict[Any, float]
    written: dict[Any, float]
    units: dict[Any, Any]
    constants: set[Any]
    equations: list[tuple[Any, Any]]
    unknowns: list[Any]
    # Each symbol's unit as the setup writes it (N, cm), for showing a value in it.
    written_units: dict[Any, Any] = field(default_factory=dict)


def in_unit(values: list[float], unit: str) -> list[float]:
    """Base-SI values in the asked unit, each converted on its own: an offset unit (°C from
    kelvin) is no factor."""
    registry = unit_registry()
    asked = as_quantity(1.0, unit)
    base = asked.to_base_units().units
    return [float(registry.Quantity(v, base).to(asked.units).magnitude) for v in values]
