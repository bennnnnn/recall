"""Calculus intent extractors."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.math import MathIntent
from app.modules.math.tools.extractors.formulas import FORMULA_CALCULUS_EXTRACTORS
from app.modules.math.tools.helpers import (
    _calc_expr_tail,
    _normalize_latex_expr,
    _strip_series_prefix,
    _strip_trailing_differential,
    _strip_trailing_filler,
    math_expr_or_none,
    peel_function_definition,
)

_WRT_VARIABLE = re.compile(r"\b(?:with\s+respect\s+to|wrt)\s+([a-zA-Z])\b", re.IGNORECASE)
_LEIBNIZ_VARIABLE = re.compile(r"/\s*d\s*([a-zA-Z])\b")
_INTEGRAL_VARIABLE = re.compile(r"\bd\s*([a-zA-Z])(?=\s+from\b|\s*$)")
_HIGHER_LEIBNIZ = re.compile(
    r"\bd\s*(?:\^\s*([2-4])|([²³⁴]))\s*[a-zA-Z]\s*/\s*"
    r"d\s*([a-zA-Z])\s*(?:\^\s*[2-4]|[²³⁴])",
    re.IGNORECASE,
)
_DERIVATIVE_AT_POINT = re.compile(
    r"\s+at\s+([a-zA-Z])\s*=\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*$",
    re.IGNORECASE,
)
_UNICODE_SIGMA_EXPR = re.compile(
    r"Σ\s*(.+?)(?=\s+(?:converges?|diverges?)\b|[?;]|$)",
    re.IGNORECASE,
)


def _calculus_variable(cleaned: str, raw: str, expr: str, *, integrate: bool) -> str:
    from app.modules.math.solve import guess_variables

    explicit = _WRT_VARIABLE.search(cleaned) or _LEIBNIZ_VARIABLE.search(cleaned)
    if explicit is not None:
        return explicit.group(1)
    if integrate:
        differential = _INTEGRAL_VARIABLE.search(raw)
        if differential is not None:
            return differential.group(1)
    variables = guess_variables(expr)
    return variables[0] if len(variables) == 1 else "x"


def _split_find_clause(s: str) -> str:
    """``f(x) = x^3 - 3x, find f''(x)`` → the definition before ``, find``."""
    lower = s.lower()
    cut: int | None = None
    for token in (", find ", ", what is ", ", what's "):
        idx = lower.find(token)
        if idx != -1 and (cut is None or idx < cut):
            cut = idx
    return s[:cut] if cut is not None else s


def _derivative_order(cleaned: str) -> int:
    """1-3 from Lagrange primes, then phrasing. Linear scans — no regex."""
    from app.modules.math.match.calculus import lagrange_prime_order

    primes = lagrange_prime_order(cleaned)
    if primes:
        return primes
    low = cleaned.lower()
    for phrase, order in (
        ("third derivative", 3),
        ("3rd derivative", 3),
        ("second derivative", 2),
        ("2nd derivative", 2),
    ):
        if phrase in low:
            return order
    compact = low.replace(" ", "")
    if "d^3" in compact or "d³" in compact:
        return 3
    if "d^2" in compact or "d²" in compact:
        return 2
    return 1


def _extract_critical_points_intent(cleaned: str) -> MathIntent | None:
    """Intercept extrema asks so they cannot fall through to a fake equation solve."""
    low = cleaned.lower()
    if (
        "critical point" not in low
        and "extrema" not in low
        and "local max" not in low
        and "local min" not in low
    ):
        return None
    from app.modules.math import solve as math_solve

    expr: str | None = None
    pairs = math_solve.try_extract_equations_from_text(cleaned)
    if pairs:
        _lhs, rhs = pairs[0]
        expr = math_expr_or_none(rhs)
    if expr is None:
        of_at = low.find(" of ")
        if of_at != -1:
            expr = math_expr_or_none(_strip_trailing_filler(cleaned[of_at + 4 :]))
    return MathIntent(
        kind="calculus",
        expr=expr or "",
        operation="critical_points",
        variable="x",
    )


_IDENTITY_CUES = ("show that", "prove that", "verify that", "always true")
_IDENTITY_SKIP_OPS = {
    "factor",
    "expand",
    "differentiate",
    "derivative",
    "integrate",
    "integral",
    "dsolve",
}


def _extract_identity_intent(cleaned: str) -> MathIntent | None:
    """Certify an identity equality. Must run before algebra solves for x."""
    from app.modules.math import match as mtm

    lower = cleaned.lower()
    has_cue = "identity" in lower or any(cue in lower for cue in _IDENTITY_CUES)
    if not has_cue or not mtm.has_equation(cleaned):
        return None
    op_word = mtm.calc_op(cleaned)
    if op_word in _IDENTITY_SKIP_OPS:
        return None
    if "induction" in lower or "contradiction" in lower:
        return MathIntent(
            kind="calculus",
            operation="simplify",
            school_op="identity",
            lhs="",
            rhs="",
            expr="",
            variable="x",
        )
    if lower.startswith("is "):
        cleaned = cleaned[3:].lstrip()
        lower = cleaned.lower()
    eq = cleaned.find("=")
    if eq <= 0:
        return None
    lhs_raw = cleaned[:eq]
    rhs_raw = cleaned[eq + 1 :]
    rhs_lower = rhs_raw.lower().rstrip(" .?!")
    for suffix in (" always true", " true for all real numbers", " true for all real x"):
        if rhs_lower.endswith(suffix):
            rhs_raw = rhs_raw[: len(rhs_lower) - len(suffix)]
            break
    lhs_low = lhs_raw.lower()
    for cue in (*_IDENTITY_CUES, "the identity", "identity"):
        idx = lhs_low.find(cue)
        if idx != -1:
            lhs_raw = lhs_raw[idx + len(cue) :]
            break
    lhs = math_expr_or_none(_normalize_latex_expr(_strip_trailing_filler(lhs_raw)))
    rhs = math_expr_or_none(_normalize_latex_expr(_strip_trailing_filler(rhs_raw)))
    return MathIntent(
        kind="calculus",
        operation="simplify",
        school_op="identity",
        lhs=lhs or "",
        rhs=rhs or "",
        expr=f"({lhs or '0'})-({rhs or '0'})",
        variable="x",
    )


def _named_axis_bounds(text: str, var: str) -> tuple[str, str] | None:
    """Linear scan for ``var=LO to HI`` — no regex."""
    lower = text.lower()
    needle = f"{var}="
    idx = lower.find(needle)
    if idx == -1:
        needle = f"{var} ="
        idx = lower.find(needle)
        if idx == -1:
            return None
    rest = text[idx + len(needle) :]
    to_at = rest.lower().find(" to ")
    if to_at == -1:
        return None
    lo = rest[:to_at].strip().rstrip(",")
    hi_part = rest[to_at + 4 :].strip()
    end = 0
    while end < len(hi_part) and not hi_part[end].isspace() and hi_part[end] not in ",;":
        end += 1
    hi = hi_part[:end].strip()
    if not lo or not hi:
        return None
    return lo, hi


def _extract_double_integral_intent(cleaned: str) -> MathIntent | None:
    """Intercept ``double integral of … from x=a to b and y=c to d``."""
    lower = cleaned.lower()
    x_bounds = _named_axis_bounds(cleaned, "x")
    y_bounds = _named_axis_bounds(cleaned, "y")
    if x_bounds is None or y_bounds is None:
        return None
    if _named_axis_bounds(cleaned, "z") is not None:
        return None
    if "triple" in cleaned.lower():
        return None
    start = lower.find("double integral")
    if start != -1:
        rest = cleaned[start + len("double integral") :]
    else:
        start = lower.find("integral")
        if start == -1:
            return None
        rest = cleaned[start + len("integral") :]
    rest = rest.lstrip()
    if rest.lower().startswith("of "):
        rest = rest[3:]
    from_at = rest.lower().find(" from ")
    if from_at == -1:
        return None
    expr = math_expr_or_none(_normalize_latex_expr(rest[:from_at].strip()))
    if expr is None:
        return None
    return MathIntent(
        kind="calculus",
        operation="integrate",
        school_op="double_integral",
        expr=expr,
        variable="x",
        variable2="y",
        integral_lower=x_bounds[0],
        integral_upper=x_bounds[1],
        integral_lower2=y_bounds[0],
        integral_upper2=y_bounds[1],
    )


def _leading_integral_bounds(cleaned: str) -> tuple[str, str, str] | None:
    """``integral from 1 to infinity of f(x) dx`` -> expression and bounds."""
    lower = cleaned.lower()
    integral_at = cleaned.find("∫")
    if integral_at != -1:
        rest = cleaned[integral_at + 1 :].strip()
        if rest.startswith("["):
            close = rest.find("]")
            if close != -1:
                bounds = rest[1:close].split(",")
                expr = rest[close + 1 :].strip()
                if len(bounds) == 2 and all(part.strip() for part in bounds) and expr:
                    return expr, bounds[0].strip(), bounds[1].strip()
    marker = "integral from "
    start = lower.find(marker)
    if start == -1:
        return None
    rest = cleaned[start + len(marker) :].strip()
    to_at = rest.lower().find(" to ")
    if to_at == -1:
        return None
    after_to = rest[to_at + 4 :].strip()
    of_at = after_to.lower().find(" of ")
    if of_at == -1:
        return None
    low = rest[:to_at].strip()
    high = after_to[:of_at].strip()
    expr = after_to[of_at + 4 :].strip()
    if not low or not high or not expr or " " in low or " " in high:
        return None
    return expr, low, high


def _extract_calculus_intent(cleaned: str) -> MathIntent | None:
    from app.modules.math import match as mtm

    higher_leibniz = _HIGHER_LEIBNIZ.search(cleaned)
    op_word = mtm.calc_op(cleaned)
    if op_word is None and higher_leibniz is not None:
        op_word = "differentiate"
    if op_word is None or op_word in {"taylor", "partial", "dsolve"}:
        return None
    if op_word == "factor" and any(
        phrase in cleaned.lower() for phrase in ("do not factor", "don't factor")
    ):
        # This is a method constraint on an equation, not a request to factor
        # the pronoun at the end of the sentence.
        return None
    calc_op: Literal["simplify", "differentiate", "integrate", "factor", "expand"] = (
        "differentiate" if op_word in {"differentiate", "derivative"} else "integrate"
    )
    if op_word == "simplify":
        calc_op = "simplify"
    elif op_word == "factor":
        calc_op = "factor"
    elif op_word == "expand":
        calc_op = "expand"
    if calc_op == "integrate" and re.search(r"\bprincipal[\s-]+value\b", cleaned, re.I):
        # The ordinary integrator does not compute a Cauchy principal value.
        # Do not strip this qualifier and certify a different mathematical request.
        return None
    leading_bounds = _leading_integral_bounds(cleaned) if calc_op == "integrate" else None
    tail = _calc_expr_tail(cleaned)
    if calc_op == "differentiate" and higher_leibniz is not None:
        # ``find d²y/dx² if y = ...`` puts the function after the derivative
        # request, not after a word such as "differentiate".  Keep the whole
        # function definition so ``peel_function_definition`` can remove y=.
        lower_cleaned = cleaned.lower()
        if_at = lower_cleaned.find(" if ", higher_leibniz.end())
        if if_at != -1:
            tail = cleaned[if_at + 4 :]
    raw = (
        _strip_trailing_filler(leading_bounds[0])
        if leading_bounds is not None
        else (_strip_trailing_filler(tail) if tail is not None else cleaned)
    )
    evaluation_point: str | None = None
    if calc_op == "differentiate":
        point_match = _DERIVATIVE_AT_POINT.search(raw.rstrip(".?!"))
        if point_match is not None:
            raw = raw[: point_match.start()].rstrip(" ,;.")
            evaluation_point = point_match.group(2)
    if calc_op == "simplify":
        lower_raw = raw.lower()
        for suffix in (
            " state all excluded values",
            " state the excluded values",
            " include all excluded values",
        ):
            at = lower_raw.find(suffix)
            if at != -1:
                raw = raw[:at].rstrip(" ,;.")
                break
    raw = _split_find_clause(raw)
    raw = peel_function_definition(raw)
    # ``simplify 4x+2x=18`` is an equation, not a simplify-of-equality. Fall
    # through so the algebra extractor can solve it. Explicit factor/expand
    # of a single ``poly=0`` stays calculus; a worked multi-equation paste
    # (`Factor it:` then 2x-1=0) must not steal the quadratic.
    if calc_op == "simplify" and "=" in raw:
        return None
    if calc_op in {"factor", "expand"} and "=" in raw:
        from app.modules.math import solve as math_solve

        pairs = math_solve.try_extract_equations_from_text(cleaned)
        if len(pairs) >= 2:
            return None
        if pairs and pairs[0][1].strip() in {"0", "0.0"}:
            raw = pairs[0][0]
    integral_lower: str | None = leading_bounds[1] if leading_bounds is not None else None
    integral_upper: str | None = leading_bounds[2] if leading_bounds is not None else None
    raw_with_differential = raw
    if calc_op == "integrate":
        raw = _strip_trailing_differential(raw)
        bounds = mtm.integral_bounds(raw) if leading_bounds is None else None
        if bounds is not None:
            raw, integral_lower, integral_upper = bounds
    expr = math_expr_or_none(raw)
    if expr is None:
        return None
    return MathIntent(
        kind="calculus",
        expr=expr,
        operation=calc_op,
        variable=_calculus_variable(
            cleaned, raw_with_differential, expr, integrate=calc_op == "integrate"
        ),
        integral_lower=integral_lower,
        integral_upper=integral_upper,
        derivative_order=_derivative_order(cleaned) if calc_op == "differentiate" else 1,
        evaluation_point=evaluation_point,
    )


def _extract_limit_intent(cleaned: str) -> MathIntent | None:
    from app.modules.math import match as mtm

    limit_hit = mtm.parse_limit(cleaned)
    if limit_hit is None:
        return None
    expr = _normalize_latex_expr(_strip_trailing_filler(limit_hit.expr)).replace("^", "**")
    limit_point = limit_hit.point.lstrip("\\")
    guarded = math_expr_or_none(expr)
    if guarded is None:
        return None
    return MathIntent(
        kind="limit",
        expr=guarded,
        variable=limit_hit.var,
        limit_point=limit_point,
        limit_direction=limit_hit.direction,
        operation="limit",
    )


def _extract_series_intent(cleaned: str) -> MathIntent | None:
    from app.modules.math import match as mtm
    from app.modules.math import solve as math_solve

    if "Σ" in cleaned:
        raw_expressions = [
            match.group(1).strip() for match in _UNICODE_SIGMA_EXPR.finditer(cleaned)
        ]
        expressions: list[str] = []
        variable: str | None = None
        for raw in raw_expressions[:2]:
            guarded = math_expr_or_none(_normalize_latex_expr(raw).replace("^", "**"))
            if guarded is None:
                return None
            names = math_solve.guess_variables(guarded)
            if len(names) != 1:
                return None
            if variable is not None and names[0] != variable:
                return None
            variable = names[0]
            expressions.append(guarded)
        if expressions and variable is not None:
            return MathIntent(
                kind="series",
                expr=expressions[0],
                expr2=expressions[1] if len(expressions) == 2 else None,
                variable=variable,
                series_start="1",
                series_end="infinity",
                operation="series",
                school_op="series_convergence",
            )

    series_hit = mtm.parse_series(cleaned)
    if series_hit is None:
        return None
    expr = _normalize_latex_expr(
        _strip_series_prefix(_strip_trailing_filler(series_hit.expr))
    ).replace("^", "**")
    end = series_hit.end.lstrip("\\")
    guarded = math_expr_or_none(expr)
    if guarded is None:
        return None
    return MathIntent(
        kind="series",
        expr=guarded,
        variable=series_hit.var,
        series_start=series_hit.start,
        series_end=end,
        operation="series",
    )


CALCULUS_EXTRACTORS = (
    _extract_critical_points_intent,
    _extract_identity_intent,
    *FORMULA_CALCULUS_EXTRACTORS,
    _extract_double_integral_intent,
    _extract_calculus_intent,
    _extract_limit_intent,
    _extract_series_intent,
)
