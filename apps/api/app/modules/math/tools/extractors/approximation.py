"""A numerical method the question names, read whole or declined.

"Use the trapezoidal rule with n = 4 to approximate the integral of x^2 from 0 to 2" is the
trapezoidal sum T_4, whatever the integral is. This reader runs before every other, so
none of them answers the integral in the method's place: it reads the rule, its count and
the integral (or Euler's equation, start and step) or returns ``declined_reading``, and the
model then answers unchecked. Newton's method for a number of steps is read here too;
Newton run to its root is read beside its equation, in
``algebra._extract_numerical_method_intent``.
"""

from __future__ import annotations

import re
from fractions import Fraction

from app.modules.math.match.numerical_methods import (
    INTEGRATION_RULES,
    NamedMethod,
    named_numerical_method,
    without_named_method,
    without_start,
    worked_rule,
)
from app.modules.math.schemas import MathIntent, declined_reading
from app.services.number_text import SIGNED_DECIMAL

_DECLINED = "numerical_method"
# Euler's equation: "y' = x + y", "dy/dx = x + y", up to the clause that ends it.
_RATE = re.compile(
    r"(?:\bdy\s*/\s*dx|\by\s*'|\by\u2032)\s*=\s*(?P<rate>[^,;=]+?)"
    r"(?=\s*(?:[,;]|\b(?:with|and|where|from|starting|using|if|given|to)\b|$))",
    re.IGNORECASE,
)
_INITIAL = re.compile(rf"\by\s*\(\s*(?P<x>{SIGNED_DECIMAL})\s*\)\s*=\s*(?P<y>{SIGNED_DECIMAL})")
# The value asked for: y(0.2) not followed by "=".
_TARGET = re.compile(rf"\by\s*\(\s*(?P<x>{SIGNED_DECIMAL})\s*\)(?!\s*=)")


def extract_approximation_intent(cleaned: str) -> MathIntent | None:
    """The named rule worked as asked, ``declined_reading`` when it cannot be read whole, or
    None when no rule of integration or Euler's method is named."""
    named = named_numerical_method(cleaned)
    if named is None:
        return None
    if named.rule == "newton":
        # Newton run to its root is read beside its equation (``algebra``); a counted one
        # ("1 Newton iteration … from x = 3") is x_1, read here before that reader.
        counted = named.count is not None or named.unread_count
        return newton_steps_intent(cleaned, named) if counted else None
    if named.rule in INTEGRATION_RULES:
        intent = _integration_rule(cleaned, named)
    elif named.rule == "euler":
        intent = _euler(cleaned, named)
    else:
        intent = None
    return intent if intent is not None else declined_reading(_DECLINED)


def _integration_rule(cleaned: str, named: NamedMethod) -> MathIntent | None:
    rule = worked_rule(named)
    if named.count is None or rule is None:
        return None
    integral = _integral(f"evaluate {without_named_method(cleaned)}")
    if (
        integral is None
        or integral.kind != "calculus"
        or integral.operation != "integrate"
        or not (integral.expr and integral.integral_lower and integral.integral_upper)
    ):
        return None
    return MathIntent(
        kind="numerical_method",
        operation="integrate",
        expr=integral.expr,
        variable=integral.variable,
        integral_lower=integral.integral_lower,
        integral_upper=integral.integral_upper,
        numeric_rule=rule,
        numeric_steps=named.count,
    )


def _integral(text: str) -> MathIntent | None:
    """The integral a rule is applied to, read by the calculus readers."""
    from app.modules.math.match.scan import prepare
    from app.modules.math.tools.extractors.calculus import CALCULUS_EXTRACTORS

    prepared = prepare(text)
    if not prepared:
        return None
    return next(
        (intent for read in CALCULUS_EXTRACTORS if (intent := read(prepared)) is not None),
        None,
    )


def _euler(cleaned: str, named: NamedMethod) -> MathIntent | None:
    """y' = f(x, y), y(x0) = y0, the step h, and how far: y(x_end) or a number of steps."""
    rate, start = _RATE.search(cleaned), _INITIAL.search(cleaned)
    if rate is None or start is None or named.step_size is None:
        return None
    targets = [match for match in _TARGET.finditer(cleaned) if match.start() != start.start()]
    try:
        step = Fraction(named.step_size)
        begin = Fraction(start.group("x"))
        steps = named.count
        if targets:
            span = (Fraction(targets[-1].group("x")) - begin) / step
            if span.denominator != 1 or (steps is not None and steps != span):
                return None
            steps = int(span)
    except (ValueError, ZeroDivisionError):
        return None
    if steps is None or steps < 1:
        return None
    end = begin + steps * step
    return MathIntent(
        kind="numerical_method",
        operation="dsolve",
        expr=rate.group("rate").strip(),
        variable="x",
        initial_x=start.group("x"),
        initial_y=start.group("y"),
        evaluation_point=str(end.numerator) if end.denominator == 1 else str(float(end)),
        numeric_rule="euler",
        numeric_steps=steps,
        numeric_step_size=named.step_size,
    )


# Everything up to the method and the word before its equation: "apply 1 Newton iteration
# to", "use one iteration of Newton's method on".
_NEWTON_LEAD = re.compile(
    r"^.*?\bnewton(?:'s|\u2019s|s)?(?:[-\s]+raphson)?"
    r"(?:\s+(?:method|iterations?|steps?|iterates?))?\s*:?\s+(?:on|for|to|of|with|in)\s+",
    re.IGNORECASE,
)
# A starting value set apart ("x = 3", "x1 = 2"), never the equation Newton works on.
_START_ASSIGNMENT = re.compile(r"^[a-z](?:_?\{?\d\}?)?$", re.IGNORECASE)


def newton_steps_intent(cleaned: str, named: NamedMethod) -> MathIntent:
    """Newton's method for the steps the question counts, from the start it gives, or
    ``declined_reading`` when the count, the start or the equation cannot be read."""
    if named.count is None or named.start is None or named.unread_count:
        return declined_reading(_DECLINED)
    from app.modules.math import solve as math_solve

    pairs = [
        (lhs, rhs)
        for lhs, rhs in math_solve.try_extract_equations_from_text(
            _NEWTON_LEAD.sub("", without_start(cleaned))
        )
        if not _START_ASSIGNMENT.match(lhs.strip())
    ]
    if len(pairs) != 1:
        return declined_reading(_DECLINED)
    lhs, rhs = pairs[0]
    variables = math_solve.guess_variables(f"{lhs} {rhs}")
    if len(variables) != 1:
        return declined_reading(_DECLINED)
    return MathIntent(
        kind="numerical_method",
        expr=lhs if rhs.strip() in ("0", "0.0") else f"({lhs})-({rhs})",
        variable=variables[0],
        newton_guess=float(named.start),
        operation="newton",
        numeric_rule="newton",
        numeric_steps=named.count,
        numeric_first_index=named.first_index,
        numeric_every_step=named.every_iterate,
    )
