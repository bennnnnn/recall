"""Trig calls on angles in degrees inside a sum, product, difference or quotient.

"Evaluate sin 30° + cos 60°" was a checked -0.00748 and "sin 30° cos 60°" a checked -0.0087,
on main too: the one-call reader took everything after ``sin`` as its angle, so the turn
worked sin((30° + cos 60)·π/180) (review, 2026-11-15). A degree mark ends the bare argument
it closes, as a bracket would: each call here is its own ``f((n)*pi/180)``, bracketed
(``sin(30°)``) or bare (``sin 30°``, ``sin 30 degrees``), with its power (``sin²30°``,
``cos^2 60°``). Calls in radians may stand beside them when π brackets the angle
(``cos(π/3)``). Anything else there, a degree mark the calls do not hold (``sin 30° + 15°``),
another name (``arcsin 0.5``) or a bare radian call whose argument nothing ends
(``cos π/3``), is declined, never read as one long argument.
"""

from __future__ import annotations

import re

from app.modules.math.function_names import TRIG, function_name_alternation
from app.modules.math.schemas import MathIntent, declined_reading
from app.modules.math.tools.expr_rewrite import math_expr_or_none
from app.services.number_text import SIGNED_DECIMAL

_DEGREE_TRIG_CALL = re.compile(
    rf"(?<![A-Za-z])(?P<name>{function_name_alternation(TRIG)})"
    r"(?:\s*+\^\s*+(?P<caret>\d)|(?P<raised>[²³]))?\s*+"
    rf"(?:\(\s*+(?P<bracketed>{SIGNED_DECIMAL})\s*+(?:degrees?|deg|°)\s*+\)"
    rf"|(?P<bare>{SIGNED_DECIMAL})\s*+(?:°|degrees?\b|deg\b))",
    re.IGNORECASE,
)
# A call in radians, its angle bracketed with π in it: ``cos(π/3)``, ``tan(pi/4)``.
_RADIAN_TRIG_CALL = re.compile(
    rf"(?<![A-Za-z])(?:{function_name_alternation(TRIG)})\s*+\([^()]*(?:pi|π)[^()]*\)",
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(r"@(\d+)@")
# What may stand between the calls: numbers, operators, brackets and π.
_BETWEEN_CALLS = re.compile("[\\d\\s.+\\-\u2212*/\u00d7\u00b7\u00f7^()]*")


def _call(match: re.Match[str]) -> str:
    power = match["caret"] or {"²": "2", "³": "3"}.get(match["raised"] or "")
    angle = match["bracketed"] or match["bare"]
    call = f"{match['name'].lower()}(({angle})*pi/180)"
    return f"{call}**{power}" if power else call


def degree_expression_intent(expression: str) -> MathIntent | None:
    """The trig expression of the degree calls in ``expression``, a declined reading when
    something beside them cannot be read, and None when it holds none or only one call alone
    (the single-angle reader works that, with its working)."""
    calls: list[str] = []

    def placeholder(match: re.Match[str]) -> str:
        calls.append(_call(match))
        return f" @{len(calls) - 1}@ "

    marked = _DEGREE_TRIG_CALL.sub(placeholder, expression)
    if not calls:
        return None
    alone = _PLACEHOLDER.fullmatch(marked.strip())
    if alone is not None and "**" not in calls[0]:
        return None
    between = _PLACEHOLDER.sub(" ", _RADIAN_TRIG_CALL.sub(" ", marked))
    between = re.sub(r"\bpi\b|π", " ", between, flags=re.IGNORECASE)
    if _BETWEEN_CALLS.fullmatch(between) is None:
        return declined_reading("trig_degrees")
    expr = math_expr_or_none(_PLACEHOLDER.sub(lambda found: calls[int(found[1])], marked))
    if expr is None:
        return declined_reading("trig_degrees")
    return MathIntent(kind="trig", school_op="expression", expr=expr, operation="solve")
