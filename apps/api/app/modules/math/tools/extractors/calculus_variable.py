"""Which letter a derivative or an integral is worked in: named ("with respect to θ",
``d/dt``, ``dθ``), else the one the expression implies.

Read as x whenever more than one letter stood in it, "Differentiate k sin θ" was a checked 0
and "Integrate r²θ" a checked r²xθ + C (review, 2026-11-14), as "k sin t" was on main. The
extractor and the direct-answer guard (``direct_calculus.py``) both read it here, so the two
agree on what was asked.
"""

from __future__ import annotations

import re

from app.modules.math.function_names import variable_letters
from app.modules.math.tools.expr_rewrite import VARIABLE_NAME

_WRT_VARIABLE = re.compile(rf"\b(?:with\s+respect\s+to|wrt)\s+({VARIABLE_NAME})\b", re.IGNORECASE)
_LEIBNIZ_VARIABLE = re.compile(rf"/\s*d\s*({VARIABLE_NAME})\b")
# ``dx`` alone, or glued to a power or a bracket (``x^2dx``), as ``expr_rewrite`` peels it.
_INTEGRAL_VARIABLE = re.compile(rf"(?:\b|(?<=[\d)\]]))d\s*({VARIABLE_NAME})(?=\s+from\b|\s*$)")


def implied_variable(expr: str) -> str | None:
    """The variable an expression is worked in when the question names none: its one
    letter, x among several (``k sin x`` is in x), x for a number alone. None when several
    letters and no x leave it open: nothing says whether θ, k or r is the variable of
    ``k sin θ`` or ``r²θ``, so no card answers it."""
    from app.modules.math.solve import guess_variables

    variables = guess_variables(expr)
    if len(variables) == 1:
        return variables[0]
    return "x" if "x" in variable_letters(expr) else None


def explicit_variable(cleaned: str) -> str | None:
    """The variable the question names: "with respect to t", ``d/dθ``."""
    explicit = _WRT_VARIABLE.search(cleaned) or _LEIBNIZ_VARIABLE.search(cleaned)
    return explicit.group(1) if explicit is not None else None


def calculus_variable(cleaned: str, raw: str, expr: str, *, integrate: bool) -> str | None:
    """Named, then an integral's differential (``dθ``), then the expression's own."""
    explicit = explicit_variable(cleaned)
    if explicit is not None:
        return explicit
    if integrate:
        differential = _INTEGRAL_VARIABLE.search(raw)
        if differential is not None:
            return differential.group(1)
    return implied_variable(expr)
