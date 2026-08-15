"""String helpers for math intent extraction."""

from __future__ import annotations

import logging
import re

from app.services.text_normalize import collapse_ws

logger = logging.getLogger(__name__)

# Cap before any poly-time regex. CodeQL only treats a const length compare as a
# ReDoS sanitizer — collapsing whitespace alone is not enough.
_MAX_MATH_INPUT = 1000


def _normalize_latex_expr(expr: str) -> str:
    """Delegate to math_service so limit/series paths share frac/abs handling."""
    from app.services.math_service import _normalize_latex_to_sympy

    return _normalize_latex_to_sympy(expr)


def _strip_series_prefix(expr: str) -> str:
    s = collapse_ws(expr)
    if len(s) > _MAX_MATH_INPUT:
        return s[:_MAX_MATH_INPUT]
    prev = None
    while prev != s:
        prev = s
        lower = s.lower()
        for prefix in (
            "does the series ",
            "does the sum ",
            "the series ",
            "the sum ",
            "series ",
            "sum ",
            "of ",
        ):
            if lower.startswith(prefix):
                s = s[len(prefix) :].strip()
                break
        else:
            break
    return s


_DEFAULT_NEWTON_GUESS = 1.0
_NEWTON_NUM = re.compile(r"-?\d+(?:\.\d+)?")

_TRAILING_FILLER_SUFFIXES = (
    " please",
    " please.",
    " now",
    " now.",
    " thank",
    " thanks",
    " thanks.",
    " thank you",
    " thank you.",
    " for me",
    " for me.",
    " to me",
    " to me.",
    " real quick",
    " real quick.",
    " quickly",
    " quickly.",
    " briefly",
    " briefly.",
)

_CALC_VERBS = (
    "simplify",
    "differentiate",
    "derivative",
    "integrate",
    "integral",
    "factor",
    "expand",
)


def _split_and_then(s: str) -> str:
    """Keep text before the first `` and `` / `` then `` clause (no regex)."""
    lower = s.lower()
    cut: int | None = None
    for token in (" and ", " then "):
        idx = lower.find(token)
        if idx != -1 and (cut is None or idx < cut):
            cut = idx
    return s[:cut] if cut is not None else s


def _strip_trailing_filler(expr: str) -> str:
    """`_GRAPH_EXPR`/the calculus expr-match are greedy captures of everything
    after the trigger word, so natural phrasing like "graph x^2 please" or
    "differentiate x^2 for me" sweeps the trailing words into the
    "expression" — which then fails to parse and silently disables the
    verified-math augmentation for phrasing a real user would actually type."""
    s = collapse_ws(expr)
    # Const length compare must sit in this function for CodeQL's ReDoS barrier.
    if len(s) > _MAX_MATH_INPUT:
        return s[:_MAX_MATH_INPUT]
    # A conjunction essentially never appears inside a math expression
    # itself — anything from " and "/" then " onward is a new clause of
    # natural language (e.g. "sin(x) and explain it"), not part of the expr.
    s = _split_and_then(s)
    prev = None
    while prev != s:
        prev = s
        lower = s.lower()
        for suffix in _TRAILING_FILLER_SUFFIXES:
            if lower.endswith(suffix):
                s = s[: -len(suffix)].rstrip()
                break
    return s


def _calc_expr_tail(cleaned: str) -> str | None:
    """Text after the first calculus verb (index scan — avoids poly regex)."""
    lower = cleaned.lower()
    best_at: int | None = None
    best_end = 0
    for verb in _CALC_VERBS:
        needle = f"{verb} "
        idx = lower.find(needle)
        if idx != -1 and (best_at is None or idx < best_at):
            best_at = idx
            best_end = idx + len(needle)
    if best_at is None:
        return None
    return cleaned[best_end:]


def _parse_newton_guess(cleaned: str) -> tuple[float, str]:
    """Return ``(guess, text_for_eq)`` after stripping a trailing guess clause."""
    guess = _DEFAULT_NEWTON_GUESS
    text_for_eq = cleaned
    lower = cleaned.lower()
    for label in (
        "starting at x0 =",
        "starting at x=",
        "starting at",
        "starting near",
        "initial guess of",
        "initial guess",
        "near x=",
        "near",
        "guess",
        "x0 =",
    ):
        idx = lower.find(label)
        if idx == -1:
            continue
        m = _NEWTON_NUM.search(cleaned, idx + len(label))
        if m:
            guess = float(m.group(0))
            # Guess clauses are almost always trailing — drop from the cue onward.
            text_for_eq = cleaned[:idx].rstrip()
            if text_for_eq.lower().endswith(" with"):
                text_for_eq = text_for_eq[: -len(" with")].rstrip()
            break
    return guess, text_for_eq


def _strip_newton_leadin(text_for_eq: str) -> str:
    """Strip newton lead-in without poly regex — phrase prefixes only."""
    for prefix in (
        "please use newton's method to find the root of ",
        "please use newton's method for ",
        "please use newton's method on ",
        "use newton's method to find the root of ",
        "use newton's method for ",
        "use newton's method on ",
        "newton's method for ",
        "newton's method on ",
        "newton's method to find the root of ",
        "please numerically solve ",
        "please numerically approximate ",
        "numerically solve ",
        "numerically approximate ",
        "please find the root of ",
        "find the root of ",
    ):
        if text_for_eq.lower().startswith(prefix):
            return text_for_eq[len(prefix) :].strip()
    return text_for_eq
