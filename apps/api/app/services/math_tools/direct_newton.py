"""Closed Newton requests can show the actual recorded iteration, without solving again."""

from __future__ import annotations

import math
import re
from typing import Any

from app.services import math_service
from app.services.math_tools.block.common import VerifiedMathBlock
from app.services.math_tools.direct_calculus import _compact, _expression

_NUMBER = r"[+-]?(?:[0-9]{1,12}(?:\.[0-9]{1,12})?|\.[0-9]{1,12})"
_START = re.compile(
    rf"(.+) (?:starting at|with initial guess(?: of)?) "
    rf"(?:([A-Za-z])(?:_?0)?\s*=\s*)?({_NUMBER})",
    re.IGNORECASE,
)
_PREFIXES = (
    "use newton method to solve ",
    "use newton's method to solve ",
    "use newton's method to find the root of ",
    "use newton method to find the root of ",
    "use newton's method for ",
    "use newton's method on ",
    "newton's method for ",
    "newton's method on ",
)


def has_newton_request(text: str) -> bool:
    return re.search(r"\bnewton\b", text, re.IGNORECASE) is not None


def _request_parameters(text: str) -> tuple[str, str, float] | None:
    if len(text) > 1000:
        return None
    request = " ".join(text.split()).replace("\u2212", "-").replace("\u2019", "'")
    if request.endswith((".", "?")):
        request = request[:-1].rstrip()
    if request.lower().startswith("please "):
        request = request[7:]
    prefix = next((prefix for prefix in _PREFIXES if request.lower().startswith(prefix)), None)
    if prefix is None:
        return None
    match = _START.fullmatch(request[len(prefix) :])
    if match is None or match[1].count("=") != 1:
        return None
    lhs, rhs = (_expression(part.strip()) for part in match[1].split("="))
    if lhs is None or rhs is None:
        return None
    variables = math_service.guess_variables(f"{lhs} {rhs}")
    if len(variables) != 1:
        return None
    variable = variables[0]
    if match[2] is not None and match[2] != variable:
        return None
    expr = lhs if rhs.strip() in {"0", "0.0"} else f"({lhs})-({rhs})"
    return expr, variable, float(match[3])


def can_direct_newton(verified: VerifiedMathBlock, text: str, fences: list[dict[str, Any]]) -> bool:
    parameters = _request_parameters(text)
    data, result = verified.newton_input, verified.newton_result
    if parameters is None or data is None or result is None:
        return False
    expr, variable, guess = parameters
    if (
        _compact(data.expr) != _compact(expr)
        or data.variable != variable
        or data.initial_guess != guess
        # Precision/iteration overrides are not part of this closed grammar.
        or data.tolerance != 1e-6
        or data.max_iterations != 50
        or not result.converged
        or result.root is None
        or not math.isfinite(result.root)
        or not result.function_latex
        or not result.derivative_latex
        or result.derivative_latex == "0"
        or not result.recurrence_latex
    ):
        return False
    steps = result.iterations
    if (
        not steps
        or result.iterations_used != len(steps)
        or len(steps) > data.max_iterations
        or steps[0].x_n != data.initial_guess
        or steps[-1].x_n != result.root
        or abs(steps[-1].f_x_n) >= data.tolerance
        or any(
            step.n != n or not math.isfinite(step.x_n) or not math.isfinite(step.f_x_n)
            for n, step in enumerate(steps)
        )
    ):
        return False
    answer = f"{result.root:g}"
    return (
        verified.canonical_answer == answer
        and len(fences) == 1
        and fences[0].get("type") == "answer"
        and fences[0].get("content") == answer
    )


def _iterate_text(value: float) -> str:
    # These are the solver's ten-decimal recorded values, not recalculated iterates.
    return f"{value:.10f}".rstrip("0").rstrip(".") or "0"


def format_newton_reply(verified: VerifiedMathBlock) -> str:
    data, result = verified.newton_input, verified.newton_result
    if data is None or result is None:
        raise ValueError("Newton reply requires its verified input and result")
    variable = data.variable
    lines = [
        rf"For $f({variable}) = {result.function_latex}$, Newton's update is",
        "",
        f"${result.recurrence_latex}$.",
        "",
    ]
    steps = result.iterations
    if len(steps) > 8:
        lines.extend(["First four and last three recorded iterates:", ""])
    lines.extend([rf"| $n$ | ${variable}_n$ |", "| ---: | ---: |"])
    shown = steps if len(steps) <= 8 else [*steps[:4], *steps[-3:]]
    for index, step in enumerate(shown):
        if len(steps) > 8 and index == 4:
            lines.append("| … | … |")
        lines.append(f"| {step.n} | {_iterate_text(step.x_n)} |")
    tolerance = _iterate_text(data.tolerance)
    lines.extend(
        [
            "",
            rf"Stopped when $|f({variable}_n)| < {tolerance}$.",
            "",
            rf"${variable} \approx {verified.canonical_answer}$.",
        ]
    )
    return "\n".join(lines) + "\n"
