"""How a feature solver reads an equation's sides: SymPy over plain symbols, numbers as
exact fractions. Below ``forms`` and ``counts``, which both read with it, and with no
import back into the readers above it.
"""

from __future__ import annotations

from typing import Any

from app.modules.math.schemas import MathIntent


def parse_side(text: str, names: list[str]) -> Any:
    from sympy import nsimplify

    from app.modules.math import solve as math_solve

    parsed = math_solve.parse_expression(text, names)
    if isinstance(parsed, tuple):
        raise ValueError("not one expression")
    return nsimplify(parsed, rational=True)


def plain_symbols(expr: Any) -> Any:
    """The same expression over plain symbols, whatever assumptions the parser set."""
    from sympy import Symbol

    return expr.xreplace({s: Symbol(str(s)) for s in expr.free_symbols})


def equation_sides(intent: MathIntent, names: list[str]) -> tuple[Any, Any]:
    return (
        plain_symbols(parse_side(intent.lhs or "", names)),
        plain_symbols(parse_side(intent.rhs or "", names)),
    )
