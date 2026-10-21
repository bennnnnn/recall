""" "What if the coefficient was 2?" after a solved equation: that equation, rebuilt.

The follow-up names one part of the last equation and a new number for it. The
part is changed and the rest kept, so the solver answers the new equation in the
same verified layout instead of the model guessing at it.

- coefficient (of x), the x coefficient, the leading coefficient
- the constant (term), the number added
- the right side, the other side, or "it equalled 4"
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

from sympy import Rational, sstr

from app.modules.math.solve.declines import sympy_decline
from app.modules.math.solve.parse import parse_expression

_NUMBER = r"[-+]?\d+(?:\.\d+)?(?:\s*/\s*\d+)?"
_CHANGE = re.compile(
    r"^(?:(?:and|so|ok(?:ay)?|now|then)[ ,]+)*what\s+if\s+(?:the\s+)?"
    r"(?:(?P<coefficient>(?:leading\s+)?coefficient(?:\s+of\s+(?P<of>[a-z]))?|(?P<var>[a-z])\s+coefficient)"
    r"|(?P<constant>constant(?:\s+term)?|number\s+added)"
    r"|(?P<right>right(?:[\s-]+hand)?\s+side|other\s+side|answer\s+side)"
    r"|(?P<equals>it))\s+"
    r"(?:was|were|is|became|changed\s+to|equall?ed|was\s+equal\s+to|=)\s*"
    rf"(?P<value>{_NUMBER})\s*(?:instead)?$",
    re.IGNORECASE,
)


def is_part_change(query: str | None) -> bool:
    """True for "what if the coefficient was 2": the words are the change, not a new ask."""
    if not query:
        return False
    return _CHANGE.match(" ".join(query.split()).rstrip("?.! ")) is not None


def changed_part_equation(query: str, lhs: str, rhs: str, variable: str) -> str | None:
    """The last equation with the named part set to the new number, or None."""
    line = " ".join(query.split()).rstrip("?.! ")
    match = _CHANGE.match(line)
    if match is None:
        return None
    name = (match["of"] or match["var"] or variable).lower()
    if name != variable.lower():
        return None
    with sympy_decline() as declined:
        value = Rational(match["value"].replace(" ", ""))
        # The app's parser reads "3x" the way the student typed it.
        left = parse_expression(lhs, [variable])
        right = parse_expression(rhs, [variable])
        var = next((s for s in left.free_symbols if str(s) == variable), None)
        if var is None:
            return None
        if match["coefficient"] or match["var"]:
            old = left.expand().coeff(var, 1)
            if old == 0 or left.expand().coeff(var, 2) != 0:
                return None
            left = left.expand() - old * var + value * var
        elif match["constant"]:
            left = left.expand()
            constant, _ = left.as_independent(var, as_Add=True)
            left = left - constant + value
        else:
            # "the right side was 4", or "what if it was 4" with a number alone.
            if var in right.free_symbols:
                return None
            right = value
    if declined:
        return None
    # "2*x + 5" is typed "2x + 5": a number next to the letter it multiplies.
    typed = re.sub(r"(\d)\*(?=[A-Za-z(])", r"\1", f"{sstr(left)} = {sstr(right)}")
    return typed.replace("**", "^")


def changed_part_problem(
    line: str, recent: Sequence[Any], blocked: Callable[[str], bool] | None
) -> str | None:
    """``what if the coefficient was 2`` after ``3x + 5 = 0`` is ``2x + 5 = 0``."""
    from app.modules.math.followup import _last_user_text, _message_field
    from app.modules.math.tools.extract import extract_math_intent
    from app.modules.math.tools.prompt import needs_symbolic_math

    prior = _last_user_text(recent[:-1])
    if _message_field(recent[-1], "role") != "assistant" or prior is None:
        return None
    if (blocked is not None and blocked(prior)) or not needs_symbolic_math(prior):
        return None
    intent = extract_math_intent(prior)
    if intent is None or not intent.lhs or not intent.rhs:
        return None
    return changed_part_equation(line, intent.lhs, intent.rhs, intent.variable or "x")
