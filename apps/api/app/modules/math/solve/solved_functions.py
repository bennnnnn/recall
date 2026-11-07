"""The functions an equation or inequality may hold for the solvers to certify its answer.

The solvers find the points where two sides meet. A step function (``floor``, ``ceiling``,
``round``, ``sign``, ``frac``, ``Heaviside``), a remainder (``mod``), a lattice (``max``,
``min``, ``gcd``, ``lcm``), a piecewise rule, a factorial or a complex part takes its value
on whole intervals or on integers only, and no solver here returns that set: ``floor(x) = 3``
is 3 ≤ x < 4, ``gcd(x, 6) = 3`` is every odd multiple of 3, and SymPy answered "no
solution" for the second (it reads ``gcd(x, 6)`` as the polynomial gcd, 1). So an unknown
inside any function outside ``SOLVED`` declines the solve, and the model answers.

Two checks, because SymPy evaluates some names away before a parse can be read: the written
side is checked for the names (``gcd(x, 6)`` parses to 1, ``x mod 3`` to the letters m·o·d),
and the parse for any other function applied to an unknown (``\\lfloor x \\rfloor``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from sympy import (
    Abs,
    acos,
    acosh,
    acot,
    acoth,
    acsc,
    acsch,
    asec,
    asech,
    asin,
    asinh,
    atan,
    atanh,
    cos,
    cosh,
    cot,
    coth,
    csc,
    csch,
    exp,
    log,
    sec,
    sech,
    sin,
    sinh,
    tan,
    tanh,
)
from sympy.core.function import Application

from app.services.solving import SolveServiceError

# The functions whose equations the solvers work: trig and hyperbolic with their inverses,
# exp, log and absolute value. A root is a power, not a function.
SOLVED = frozenset(
    {
        sin, cos, tan, cot, sec, csc, asin, acos, atan, acot, asec, acsc,
        sinh, cosh, tanh, coth, sech, csch, asinh, acosh, atanh, acoth, asech, acsch,
        exp, log, Abs,
    }
)  # fmt: skip
# Written names whose SymPy reading hides them, or that no solver models.
_UNSOLVED_NAMES = re.compile(
    r"(?<![\\A-Za-z])(?:floor|ceil(?:ing)?|round|trunc|sign|sgn|signum|frac|mod|modulo|"
    r"max|min|gcd|hcf|gcf|lcm|heaviside|piecewise|factorial|binomial|ncr|npr|"
    r"re|im|arg|conjugate)(?![A-Za-z])",
    re.IGNORECASE,
)


_STANDALONE = r"(?<![A-Za-z]){}(?![A-Za-z])"


def _argument(side: str, end: int) -> str:
    """The bracket after a name, or the whole side when none follows (``x mod 3``)."""
    rest = side[end:].lstrip()
    if not rest.startswith("("):
        return side
    depth = 0
    for index, char in enumerate(rest):
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth == 0:
            return rest[: index + 1]
    return rest


def _names_unknown(side: str, names: set[str]) -> bool:
    """Whether an unsolved name in the side is applied to an unknown."""
    for match in _UNSOLVED_NAMES.finditer(side):
        argument = _argument(side, match.end())
        if any(re.search(_STANDALONE.format(re.escape(name)), argument) for name in names):
            return True
    return False


def unsolved_function(sides: Iterable[str], parsed: Iterable[Any], unknowns: Iterable[Any]) -> bool:
    """Whether a side applies, to an unknown, a function no solver here models."""
    names = {str(unknown) for unknown in unknowns}
    if any(_names_unknown(side or "", names) for side in sides):
        return True
    for expr in parsed:
        for applied in getattr(expr, "atoms", lambda *_: set())(Application):
            if applied.func in SOLVED:
                continue
            if any(str(symbol) in names for symbol in applied.free_symbols):
                return True
    return False


def reject_unsolved_functions(
    sides: Iterable[str], parsed: Iterable[Any], unknowns: Iterable[Any]
) -> None:
    """Decline the solve: its answer would be a set no solver here finds."""
    if unsolved_function(sides, parsed, unknowns):
        raise SolveServiceError("The equation holds a function the solver does not model")
