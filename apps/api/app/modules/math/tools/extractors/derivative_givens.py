"""What a derivative question gives: the function, the point, or one relation in x and y.

"Find dy/dx if y = x^2 sin x" was read and "Find dy/dx for y = x ln x" was not: the reader
took the words after the cue as the function and peeled only an "if". "for", "when",
"where", "given", or the function stated first ("Given y = x^3 - 4x, find dy/dx", "y =
sin(3x)cos x. Find dy/dx.") fell through to the equation solver, whose solve of y = x ln x
for x was certified as the derivative (2026-11-14, grade 12 book). The relations the
message writes say what it gives whatever words join them: one that defines a function is
the function, one that sets the variable to a number the point, and one in the variable
and y together a curve to differentiate implicitly. Any other set (x and y each given by
t, two functions, two points) is more than one reading here can carry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.math.schemas import MathIntent, declined_reading
from app.modules.math.tools.expr_rewrite import math_expr_or_none
from app.modules.math.tools.function_def import is_named_function_lhs
from app.modules.turn_reading.at_a_point import differentiated_letters

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class DerivativeGivens:
    """The relations of a derivative question, read by what each gives."""

    # The formula of the one function the message defines ("y = x ln x" gives x ln x).
    function: str | None = None
    # Its name: y, or f for f(x).
    name: str | None = None
    # The one value the variable is given ("at x = 2").
    point: str | None = None
    # The one relation in the variable and y that defines no function ("x^2 + y^2 = 25").
    implicit: tuple[str, str] | None = None
    # Relations no one reading carries: a parametric pair, two functions, two points.
    unresolved: bool = False


def _defines(lhs: str, rhs: str) -> bool:
    """``lhs`` names a function (``y``, ``f(x)``) that ``rhs`` gives without itself."""
    if not is_named_function_lhs(lhs):
        return False
    name = lhs.replace(" ", "")[0]
    return re.search(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])", rhs) is None


def derivative_givens(cleaned: str, variable: str) -> DerivativeGivens | None:
    """What the relations of ``cleaned`` give a derivative in ``variable``; None when it
    writes no relation."""
    from app.modules.math import solve as math_solve

    pairs = math_solve.try_extract_equations_from_text(cleaned)
    if not pairs:
        return None
    functions: list[tuple[str, str]] = []
    points: list[str] = []
    curves: list[tuple[str, str]] = []
    for lhs, rhs in pairs:
        if lhs.replace(" ", "") == variable:
            # x = 2 is the point; x = t^2 gives the variable itself by another.
            if _NUMBER.fullmatch(rhs.replace(" ", "")) is None:
                return DerivativeGivens(unresolved=True)
            points.append(rhs.replace(" ", ""))
        elif _defines(lhs, rhs) and math_expr_or_none(rhs) is not None:
            functions.append((lhs.replace(" ", "")[0].lower(), rhs))
        else:
            curves.append((lhs, rhs))
    if len(points) > 1:
        return DerivativeGivens(unresolved=True)
    point = points[0] if points else None
    if len(functions) == 1 and not curves:
        name, formula = functions[0]
        return DerivativeGivens(function=formula, name=name, point=point)
    if not functions and len(curves) == 1 and point is None:
        return DerivativeGivens(implicit=curves[0])
    if not functions and not curves:
        return DerivativeGivens(point=point)
    return DerivativeGivens(unresolved=True)


def defined_function(
    cleaned: str, raw: str, expr: str | None, variable: str
) -> MathIntent | tuple[str | None, str | None]:
    """The function to differentiate and the point the message gives, or a declined reading.

    The function as the message defines it, whatever words join it to the ask, when the
    words after the cue (``raw``, read as ``expr``) were no formula ("for y = x ln x", "at
    x = 2") or only its name ("the derivative of y with respect to x, where y = x^2 ln x").
    """
    if expr is not None and "=" not in raw and len(expr.strip()) > 1:
        return expr, None
    given = derivative_givens(cleaned, variable)
    if given is not None and given.unresolved:
        return declined_reading("derivative_givens")
    # A derivative written of another letter is not this function's: the A' of a reflected
    # point A'(3, 2) is no derivative of y = x.
    named = differentiated_letters(cleaned)
    if given is not None and given.function is not None and (not named or given.name in named):
        return math_expr_or_none(given.function), given.point
    return (None if "=" in raw else expr), None
