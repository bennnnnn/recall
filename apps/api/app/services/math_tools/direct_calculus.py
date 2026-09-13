"""Whole-query guards for completed calculus answers; no solving here."""

from __future__ import annotations

import re

from app.models.schemas.math import MathIntent
from app.services.math_text_match import calc_op
from app.services.math_tools.extract import extract_math_intent
from app.services.math_tools.helpers import math_expr_or_none

_NUMBER = r"[+-]?(?:[0-9]{1,12}(?:\.[0-9]{1,12})?|\.[0-9]{1,12})"
_POINT = rf"(?:{_NUMBER}|-?(?:infinity|inf|oo))"
_INTEGER = r"[+-]?[0-9]{1,12}"
_WRT = re.compile(r"(.+) (?:with respect to|wrt) ([a-zA-Z])", re.IGNORECASE)
_INTEGRAL = re.compile(rf"(.+) from ({_POINT}) to ({_POINT})", re.IGNORECASE)
_LIMIT = re.compile(
    rf"(.+) as ([a-zA-Z]) (?:approaches|goes to|tends to) ({_POINT})"
    r"(?: from (?:the )?(left|right))?",
    re.IGNORECASE,
)
_SUM = re.compile(
    rf"(.+) from ([a-zA-Z])\s*=\s*({_INTEGER}) to ({_INTEGER}|infinity|inf|oo)",
    re.IGNORECASE,
)
_TAYLOR = re.compile(rf"(.+) at ({_NUMBER}) (?:order|degree) ([0-9]{{1,3}})", re.IGNORECASE)
_MACLAURIN = re.compile(r"(.+) (?:order|degree) ([0-9]{1,3})", re.IGNORECASE)
_FUNCTIONS = frozenset(
    {
        "sin",
        "cos",
        "tan",
        "cot",
        "sec",
        "csc",
        "asin",
        "acos",
        "atan",
        "sinh",
        "cosh",
        "tanh",
        "exp",
        "log",
        "ln",
        "sqrt",
        "pi",
    }
)
_ORDERS = {
    "derivative of ": 1,
    "first derivative of ": 1,
    "second derivative of ": 2,
    "2nd derivative of ": 2,
    "third derivative of ": 3,
    "3rd derivative of ": 3,
    "differentiate ": 1,
}


def _expression(raw: str) -> str | None:
    """Reject prose and qualifiers before the existing expression normalizer."""
    if not raw or any(
        not (char.isascii() and (char.isalnum() or char in " +-*/^().")) for char in raw
    ):
        return None
    depth = 0
    for char in raw:
        depth += (char == "(") - (char == ")")
        if depth < 0:
            return None
    if depth:
        return None
    for word in re.findall(r"[A-Za-z]+", raw):
        if len(word) != 1 and word not in _FUNCTIONS:
            return None
    return math_expr_or_none(raw)


def _compact(value: str) -> str:
    return "".join(value.split()).replace("^", "**")


def _point(value: str | None) -> str | float | None:
    if value is None:
        return None
    if value.lower() in {"infinity", "inf", "oo", "-infinity", "-inf", "-oo"}:
        return "-oo" if value.startswith("-") else "oo"
    try:
        return float(value)
    except ValueError:
        return None


def _matches_expression(actual: MathIntent, raw: str) -> bool:
    expected = _expression(raw)
    return expected is not None and _compact(actual.expr or "") == _compact(expected)


def _variable(expr: str, explicit: str | None) -> str:
    from app.services.math_service import guess_variables

    if explicit is not None:
        return explicit
    variables = guess_variables(expr)
    return variables[0] if len(variables) == 1 else "x"


def calculus_direct_request(text: str, *, answer: str | None = None) -> bool | None:
    """None is another family; False blocks partial asks from generic fallback.

    The complete expression and every operation parameter must agree with the
    existing extractor. Domains, evaluation points, and extra asks cannot be
    dropped through its trailing-clause cleanup.
    """
    if len(text) > 1000:
        return False
    request = " ".join(text.split()).replace("\u2212", "-")
    lower = request.lower()
    recognized = calc_op(request) in {
        "differentiate",
        "derivative",
        "integrate",
        "integral",
        "partial",
        "taylor",
    }
    recognized = recognized or any(
        word in lower.split() for word in ("limit", "sum", "series", "maclaurin")
    )
    if not recognized:
        return None
    request = request.rstrip(".?")
    if request.lower().startswith("please "):
        request = request[7:]
    for prefix in (
        "find ",
        "calculate ",
        "compute ",
        "evaluate ",
        "determine ",
        "what is ",
        "what's ",
    ):
        if request.lower().startswith(prefix):
            request = request[len(prefix) :]
            break
    if request.lower().startswith("the "):
        request = request[4:]
    actual = extract_math_intent(text)
    if actual is None:
        return False
    if actual.operation == "dsolve":
        return None
    lower = request.lower()
    for prefix, order in _ORDERS.items():
        if not lower.startswith(prefix):
            continue
        expr = request[len(prefix) :]
        wrt = _WRT.fullmatch(expr)
        expr, variable = (wrt[1], wrt[2]) if wrt else (expr, None)
        return (
            actual.kind == "calculus"
            and actual.operation == "differentiate"
            and actual.derivative_order == order
            and _matches_expression(actual, expr)
            and actual.variable == _variable(expr, variable)
        )
    if lower.startswith("partial derivative of "):
        match = _WRT.fullmatch(request[len("partial derivative of ") :])
        return bool(
            match
            and actual.kind == "calculus"
            and actual.operation == "partial"
            and actual.variable == match[2]
            and _matches_expression(actual, match[1])
        )
    for prefix in (
        "integrate ",
        "integral of ",
        "definite integral of ",
        "indefinite integral of ",
    ):
        if not lower.startswith(prefix):
            continue
        expr = request[len(prefix) :]
        bounds = _INTEGRAL.fullmatch(expr)
        if bounds:
            expr, low, high = bounds[1], bounds[2], bounds[3]
        else:
            low = high = None
        if (prefix == "definite integral of " and bounds is None) or (
            prefix == "indefinite integral of " and bounds is not None
        ):
            return False
        if answer is not None and r"\infty" in answer:
            return False
        wrt = _WRT.fullmatch(expr)
        expr, variable = (wrt[1], wrt[2]) if wrt else (expr, None)
        differential = re.fullmatch(r"(.+) d\s*([a-zA-Z])", expr)
        if differential:
            if variable is not None:
                return False
            expr, variable = differential[1], differential[2]
        return (
            actual.kind == "calculus"
            and actual.operation == "integrate"
            and _matches_expression(actual, expr)
            and actual.variable == _variable(expr, variable)
            and (
                actual.integral_lower is None
                if low is None
                else _point(actual.integral_lower) == _point(low)
            )
            and (
                actual.integral_upper is None
                if high is None
                else _point(actual.integral_upper) == _point(high)
            )
        )
    if lower.startswith("limit of "):
        match = _LIMIT.fullmatch(request[len("limit of ") :])
        return bool(
            match
            and actual.kind == "limit"
            and _matches_expression(actual, match[1])
            and actual.variable == match[2]
            and _point(actual.limit_point) == _point(match[3])
            and actual.limit_direction
            == {"left": "-", "right": "+", None: "+-"}[match[4].lower() if match[4] else None]
        )
    for prefix in ("sum of ", "sum "):
        if not lower.startswith(prefix):
            continue
        match = _SUM.fullmatch(request[len(prefix) :])
        # Infinite limits have a value in the extended reals, but an infinite
        # series answer needs its divergence explained rather than a bare sum.
        if answer is not None and r"\infty" in answer:
            return False
        return bool(
            match
            and actual.kind == "series"
            and _matches_expression(actual, match[1])
            and actual.variable == match[2]
            and _point(actual.series_start) == _point(match[3])
            and _point(actual.series_end) == _point(match[4])
        )
    for prefix, pattern in (("taylor series of ", _TAYLOR), ("maclaurin series of ", _MACLAURIN)):
        if not lower.startswith(prefix):
            continue
        match = pattern.fullmatch(request[len(prefix) :])
        if match is None:
            return False
        center, taylor_order = (
            (match[2], match[3]) if prefix.startswith("taylor") else ("0", match[2])
        )
        return (
            actual.kind == "calculus"
            and actual.operation == "taylor"
            and actual.variable == "x"
            and _matches_expression(actual, match[1])
            and _point(actual.limit_point) == _point(center)
            and actual.taylor_n == int(taylor_order)
        )
    return False
