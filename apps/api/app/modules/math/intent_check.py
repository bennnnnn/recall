"""Is a model's structured reading of a question (a ``MathIntent``) the maths the user wrote?

The same test the tool loop's sympy calls pass (``tool_check``): the intent becomes the
call it would make, and that call must match the user's own text.
"""

from __future__ import annotations

from typing import Any

from app.modules.math.tool_check import tool_call_matches_user_text

_CALCULUS_ACTIONS = {"differentiate": "diff"}
# The kinds whose maths this check compares with what the user wrote.
READ_KINDS = frozenset(
    {"equation", "system", "inequality", "calculus", "limit", "graph", "complex"}
)


def intent_in_user_text(intent: Any, text: str) -> bool:
    """Whether a model-extracted ``MathIntent`` is mathematics the user wrote: its equation,
    system, inequality or expression, compared with SymPy, and its bounds or limit point
    written in ``text``. A reading the model derived (equations from a story, "x squared"
    for x²) is not the user's text, and SymPy's answer to it is no checked answer."""
    args: dict[str, Any]
    if intent.kind == "equation":
        args = {"action": "solve", "lhs": intent.lhs, "rhs": intent.rhs}
    elif intent.kind == "system":
        args = {"action": "system", "equations": intent.system_equations or []}
    elif intent.kind == "inequality":
        args = {"action": "inequality", "lhs": intent.lhs, "rhs": intent.rhs}
        args["comparator"] = intent.comparator
    elif intent.kind == "calculus":
        action = _CALCULUS_ACTIONS.get(intent.operation, intent.operation)
        args = {"action": action, "expr": intent.expr}
        args |= {"lower": intent.integral_lower, "upper": intent.integral_upper}
    elif intent.kind == "limit":
        args = {"action": "limit", "expr": intent.expr, "point": intent.limit_point}
    elif intent.kind in {"graph", "complex"}:
        args = {"action": "graph" if intent.kind == "graph" else "simplify", "expr": intent.expr}
    else:
        return False
    return tool_call_matches_user_text(args, [text])
