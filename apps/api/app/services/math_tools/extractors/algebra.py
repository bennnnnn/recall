"""Algebra and numerical-method intent extractors."""

from __future__ import annotations

import re

from app.models.math_schemas import MathIntent
from app.services import math_service
from app.services.math_tools.helpers import _parse_newton_guess, _strip_newton_leadin

_SOLVE_FOR_VAR_RE = re.compile(
    r"(?:solve\s+for|find|solve)\s+(?:the\s+value\s+of\s+)?([a-zA-Z])(?![a-zA-Z])",
    re.IGNORECASE,
)
_LEADIN_WORDS = frozenset(
    {
        "solve",
        "for",
        "find",
        "the",
        "value",
        "of",
        "in",
        "when",
        "given",
        "if",
        "such",
        "that",
        "where",
        "with",
        "please",
        "let",
        "us",
        "determine",
        "calculate",
        "compute",
        "get",
        "isolate",
        "express",
        "what",
        "is",
        "are",
        "does",
        "can",
        "you",
        "show",
        "tell",
    }
)


def _requested_variable(cleaned: str, equation_text: str) -> str | None:
    """Return the variable the user explicitly asked to solve for, or None."""
    m = _SOLVE_FOR_VAR_RE.search(cleaned)
    if m is None:
        return None
    var = m.group(1)
    tokens = re.findall(r"[a-zA-Z]+", equation_text)
    kept = [t for t in tokens if t.lower() not in _LEADIN_WORDS]
    letters = {c for t in kept for c in t if c.isalpha()}
    letters.discard("e")
    letters.discard("E")
    return var if var in letters else None


def _extract_numerical_method_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not ("newton" in lower or "numerically" in lower or "root of" in lower):
        return None
    guess, text_for_eq = _parse_newton_guess(cleaned)
    text_for_eq = _strip_newton_leadin(text_for_eq)
    newton_pairs = math_service.try_extract_equations_from_text(text_for_eq)
    if not newton_pairs:
        return None
    lhs, rhs = newton_pairs[0]
    rhs_is_zero = rhs.strip() in ("0", "0.0")
    expr = lhs if rhs_is_zero else f"({lhs})-({rhs})"
    variables = math_service.guess_variables(f"{lhs} {rhs}")
    var = variables[0] if variables else "x"
    return MathIntent(
        kind="numerical_method",
        expr=expr,
        variable=var,
        newton_guess=float(guess),
        operation="newton",
    )


def _extract_matrix_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    signal = mtm.matrix_signal(cleaned)
    if signal is None:
        return None
    op, rows = signal
    return MathIntent(kind="matrix", matrix_op=op, matrix_rows=rows, operation="solve")


def _extract_system_intent(cleaned: str) -> MathIntent | None:
    eq_pairs = math_service.try_extract_equations_from_text(cleaned)
    if len(eq_pairs) < 2:
        return None
    # BUG FIX (most severe correctness bug found in the audit): this
    # used to fall through to the single-equation branch below, which
    # only ever looked at the FIRST clause and answered with the same
    # "verified, do NOT recompute" confidence as a fully correct
    # response — silently discarding every other equation in the system.
    all_text = " ".join(f"{lhs} {rhs}" for lhs, rhs in eq_pairs)
    variables = math_service.guess_variables(all_text)
    return MathIntent(
        kind="system",
        system_equations=eq_pairs[:4],
        system_variables=variables,
        operation="solve",
    )


def _extract_equation_intent(cleaned: str) -> MathIntent | None:
    eq_pairs = math_service.try_extract_equations_from_text(cleaned)
    if len(eq_pairs) != 1:
        return None
    lhs, rhs = eq_pairs[0]
    variables = math_service.guess_variables(lhs + rhs)
    requested = _requested_variable(cleaned, lhs + rhs)
    variable = requested or (variables[0] if variables else "x")
    return MathIntent(
        kind="equation",
        lhs=lhs,
        rhs=rhs,
        operation="solve",
        variable=variable,
    )


def _extract_inequality_intent(cleaned: str) -> MathIntent | None:
    # Inequality — only reached when a math keyword already matched (this
    # function is called solely from needs_symbolic_math-gated paths), so bare
    # < / > here is safe from prose false-positives like "less than 5 minutes".
    compound = math_service.try_extract_compound_inequality_from_text(cleaned)
    if compound is not None:
        low, low_op, mid, high_op, high = compound
        variables = math_service.guess_variables(f"{low} {mid} {high}")
        requested = _requested_variable(cleaned, f"{low} {mid} {high}")
        variable = requested or (variables[0] if variables else "x")
        return MathIntent(
            kind="inequality",
            lower=low,
            lhs=mid,
            rhs=high,
            comparator=low_op,
            comparator_upper=high_op,
            operation="solve",
            variable=variable,
        )
    ineq = math_service.try_extract_inequality_from_text(cleaned)
    if not ineq:
        return None
    lhs, rhs, comparator = ineq
    variables = math_service.guess_variables(lhs + rhs)
    requested = _requested_variable(cleaned, lhs + rhs)
    variable = requested or (variables[0] if variables else "x")
    return MathIntent(
        kind="inequality",
        lhs=lhs,
        rhs=rhs,
        comparator=comparator,
        operation="solve",
        variable=variable,
    )


PRE_DISCRETE_ALGEBRA_EXTRACTORS = (_extract_numerical_method_intent,)
ALGEBRA_EXTRACTORS = (
    _extract_matrix_intent,
    _extract_system_intent,
    _extract_equation_intent,
    _extract_inequality_intent,
)
