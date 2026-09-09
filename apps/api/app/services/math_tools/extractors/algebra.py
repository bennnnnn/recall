"""Algebra and numerical-method intent extractors."""

from __future__ import annotations

import re

from app.models.math_schemas import MathIntent
from app.services import math_service
from app.services.math_tools.helpers import (
    _parse_newton_guess,
    _strip_newton_leadin,
    substituted_eval_expr,
)

_SOLVE_FOR_VAR_RE = re.compile(
    r"(?:solve\s+for|find|solve)\s+(?:the\s+value\s+of\s+)?([a-zA-Z])(?![a-zA-Z])",
    re.IGNORECASE,
)
_SOLVE_CUES = (
    "solve",
    "find",
    "calculate",
    "compute",
    "evaluate",
    "determine",
    "simplify",
    "what is",
    "what's",
    "isolate",
    "factor",
    "expand",
)
_PLOT_VERB_PREFIXES = (
    "draw ",
    "sketch ",
    "visualize ",
    "visualise ",
    "chart ",
    "graph ",
    "plot ",
)
_TRAILING_OK_WORDS = frozenset({"please", "thanks", "now", "quickly", "briefly", "here"})
_EQ_BIND_PREFIXES = ("let ", "set ", "given ", "if ", "when ", "where ")


def _has_solve_cue(cleaned: str) -> bool:
    lower = cleaned.lower()
    return any(cue in lower for cue in _SOLVE_CUES)


def _blank_extracted_equation(core: str, lhs: str, rhs: str) -> str:
    """Remove the extracted ``lhs=rhs`` span so leftover English can be counted.

    Do not ``str.replace`` a 1-letter lhs — that hits the ``y`` in ``why``.
    """
    eq = core.find("=")
    if eq == -1:
        return core
    start = core.rfind(lhs, 0, eq)
    end = core.find(rhs, eq + 1)
    if start == -1 or end == -1:
        return core
    return core[:start] + " " + core[end + len(rhs) :]


def _leftover_prose_blocks_solve(cleaned: str, lhs: str, rhs: str) -> bool:
    """True when English around the extracted sides is a sentence, not a glue.

    ``2x+3=7please`` / ``2x + 3 = 7 please`` still solve. ``tell me about
    y=x^2`` does not.
    """
    if _has_solve_cue(cleaned):
        return False
    core = _equation_core_after_leadin(cleaned)
    s = _blank_extracted_equation(core, lhs, rhs)
    words = [w.lower().strip(".,?!:;") for w in s.split() if w.strip(".,?!=:;")]
    english = [w for w in words if len(w) >= 3 and w.isalpha() and w not in _TRAILING_OK_WORDS]
    return len(english) >= 2


def _has_unclaimed_plot_verb(cleaned: str) -> bool:
    """Plot phrasing that missed ``graph_expr`` must not fall through to solve."""
    from app.services import math_text_match as mtm
    from app.services.math_text_match.graph import _find_unprefixed_phrase

    if mtm.graph_expr(cleaned) is not None:
        return False
    if _has_solve_cue(cleaned):
        return False
    lower = cleaned.lower()
    return any(_find_unprefixed_phrase(lower, prefix) != -1 for prefix in _PLOT_VERB_PREFIXES)


def _equation_core_after_leadin(cleaned: str) -> str:
    from app.services.math_service.extract_eq import _strip_leading_filler

    s = _strip_leading_filler(cleaned)
    prev = None
    while prev != s:
        prev = s
        low = s.lower()
        for prefix in _EQ_BIND_PREFIXES:
            if low.startswith(prefix):
                s = s[len(prefix) :].lstrip()
                break
        else:
            break
    return s


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
    # ``e``/``E`` are Euler's number in guess_variables — still honor an
    # explicit "solve for e" when that letter is actually in the equation.
    if var in {"e", "E"}:
        return var if var in letters else None
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


def _primary_equation_pair(eq_pairs: list[tuple[str, str]]) -> tuple[str, str]:
    """Pick the problem statement from a worked solution (steps + roots).

    A paste like ``2x^2-7x+3=0`` then ``2x-1=0`` / ``x-3=0`` is one quadratic,
    not three simultaneous equations. Prefer the longest ``= 0`` polynomial.
    """
    zeros = [(lhs, rhs) for lhs, rhs in eq_pairs if rhs.strip() in {"0", "0.0"}]
    pool = zeros or eq_pairs
    return max(pool, key=lambda pair: (pair[0].count("^"), len(pair[0])))


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
    # One variable + several =0 lines is factoring / "set each factor to 0",
    # not a simultaneous system. Treating 2x-1=0 AND x-3=0 as a system
    # attaches ```answer no solution while the quadratic is solved.
    if len(variables) < 2:
        return None
    return MathIntent(
        kind="system",
        system_equations=eq_pairs[:4],
        system_variables=variables,
        operation="solve",
    )


def _extract_equation_intent(cleaned: str) -> MathIntent | None:
    if _has_unclaimed_plot_verb(cleaned):
        return None
    eq_pairs = math_service.try_extract_equations_from_text(cleaned)
    if not eq_pairs:
        return None
    # Let-binding + "what is x+2" is arithmetic after substitute, not solve x=5.
    if substituted_eval_expr(cleaned) is not None:
        return None
    lhs, rhs = eq_pairs[0] if len(eq_pairs) == 1 else _primary_equation_pair(eq_pairs)
    from app.services.math_tools.helpers import math_expr_or_none

    if math_expr_or_none(lhs) is None or math_expr_or_none(rhs) is None:
        return None
    if _leftover_prose_blocks_solve(cleaned, lhs, rhs):
        return None
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
