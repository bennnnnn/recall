"""String helpers for math intent extraction."""

from __future__ import annotations

import logging
import re

from app.services.math_text_match.scan import ddx_cue_at, ddx_expr_after, looks_like_math_expr
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
    while s and s[-1] in ".?!":
        s = s[:-1].rstrip()
    return s


def _strip_trailing_differential(expr: str) -> str:
    """Peel ``dx`` / ``d x`` so implicit multiplication does not eat the integrand."""
    s = collapse_ws(expr)
    if len(s) > _MAX_MATH_INPUT:
        s = s[:_MAX_MATH_INPUT]
    lower = s.lower()
    for token in (" dx", " dy", " d x", " d y"):
        if lower.endswith(token):
            return s[: -len(token)].rstrip()
        marker = token + " from "
        idx = lower.find(marker)
        if idx != -1:
            return (s[:idx] + s[idx + len(token) :]).rstrip()
    return s


_EXPR_LEADINS = (
    "the polynomial ",
    "the expression ",
    "the function ",
    "the equation ",
    "polynomial ",
    "expression ",
    "function ",
    "equation ",
    "of ",
    "the ",
)


_ENGLISH_POWERS: tuple[tuple[str, str], ...] = (
    ("squared", "^2"),
    ("cubed", "^3"),
)


def _single_letter_or_digit_before(text: str, idx: int) -> bool:
    """True when ``text[idx]`` follows a 1-letter variable, a digit, or ``)``.

    ``area squared`` must not become ``are^2``; ``x squared`` / ``3 squared``
    / ``) squared`` should.
    """
    if idx <= 0:
        return False
    ch = text[idx - 1]
    if ch in ")]":
        return True
    if ch.isdigit():
        return True
    if not ch.isalpha():
        return False
    return idx < 2 or not text[idx - 2].isalpha()


def rewrite_english_powers(expr: str) -> str:
    """``x squared`` → ``x^2``. Leaves ``square root`` / ``draw a square`` alone."""
    if len(expr) > _MAX_MATH_INPUT:
        expr = expr[:_MAX_MATH_INPUT]
    lower = expr.lower()
    out: list[str] = []
    i = 0
    n = len(expr)
    while i < n:
        matched = False
        if _single_letter_or_digit_before(expr, i):
            j = i
            while j < n and expr[j].isspace():
                j += 1
            rest = lower[j:]
            for word, repl in _ENGLISH_POWERS:
                if not rest.startswith(word):
                    continue
                end = j + len(word)
                if end < n and lower[end].isalpha():
                    continue
                out.append(repl)
                i = end
                matched = True
                break
        if not matched:
            out.append(expr[i])
            i += 1
    return "".join(out)


def _strip_expr_leadins(expr: str) -> str:
    """Drop scaffolding words so ``factor the polynomial x^3 - 1`` keeps ``x^3 - 1``."""
    s = collapse_ws(expr)
    if len(s) > _MAX_MATH_INPUT:
        return s[:_MAX_MATH_INPUT]
    prev = None
    while prev != s:
        prev = s
        lower = s.lower()
        for prefix in _EXPR_LEADINS:
            if lower.startswith(prefix):
                s = s[len(prefix) :].strip()
                break
        else:
            break
    wrt = s.lower().find(" with respect to ")
    if wrt != -1:
        s = s[:wrt].rstrip()
    return s


def _is_named_function_lhs(left: str) -> bool:
    """``y`` or ``f(x)`` — a definition lhs, not ``2x+3``."""
    compact = left.replace(" ", "")
    if len(compact) == 1 and compact.isalpha():
        return True
    return (
        len(compact) == 4
        and compact[0].isalpha()
        and compact[1] == "("
        and compact[2].isalpha()
        and compact[3] == ")"
    )


_EVAL_AFTER_GIVEN_CUES = (
    "what is",
    "what's",
    "whats",
    "compute ",
    "evaluate ",
    "calculate ",
)


def substituted_eval_expr(cleaned: str) -> str | None:
    """``Let x = 5. What is x + 2?`` → ``5+2``. Bare ``let x = 5`` stays None."""
    if len(cleaned) > _MAX_MATH_INPUT:
        return None
    from app.services import math_service

    eq_pairs = math_service.try_extract_equations_from_text(cleaned)
    if len(eq_pairs) != 1:
        return None
    lhs, rhs = eq_pairs[0]
    left = lhs.replace(" ", "")
    if len(left) != 1 or not left.isalpha():
        return None
    compact_rhs = rhs.replace(" ", "")
    sign = ""
    if compact_rhs.startswith("-"):
        sign = "-"
        compact_rhs = compact_rhs[1:]
    if not compact_rhs or compact_rhs.count(".") > 1:
        return None
    if not all(ch.isdigit() or ch == "." for ch in compact_rhs):
        return None
    eq_at = cleaned.find("=")
    if eq_at == -1:
        return None
    rest = cleaned[eq_at + 1 :]
    rest_l = rest.lower()
    cue_at = -1
    cue_len = 0
    for cue in _EVAL_AFTER_GIVEN_CUES:
        found = rest_l.find(cue)
        if found != -1 and (cue_at == -1 or found < cue_at):
            cue_at = found
            cue_len = len(cue)
    if cue_at == -1:
        return None
    expr = rest[cue_at + cue_len :].strip()
    while expr and expr[-1] in "?.!":
        expr = expr[:-1].rstrip()
    if not expr:
        return None
    replacement = sign + compact_rhs
    var = left.lower()
    out: list[str] = []
    i = 0
    saw_var = False
    while i < len(expr):
        ch = expr[i]
        isolated = (i == 0 or not expr[i - 1].isalpha()) and (
            i + 1 >= len(expr) or not expr[i + 1].isalpha()
        )
        if ch.lower() == var and isolated:
            out.append(replacement)
            saw_var = True
            i += 1
            continue
        out.append(ch)
        i += 1
    if not saw_var:
        return None
    result = "".join(out).replace(" ", "")
    if any(ch.isalpha() for ch in result) or not any(ch.isdigit() for ch in result):
        return None
    return result


def peel_function_definition(expr: str) -> str:
    """``y = x^3 - 3x`` / ``of y = …`` / ``if y = …`` → the rhs expression."""
    s = _strip_expr_leadins(collapse_ws(expr))
    if len(s) > _MAX_MATH_INPUT:
        s = s[:_MAX_MATH_INPUT]
    low = s.lower()
    if low.startswith("if "):
        s = s[3:].lstrip()
        s = _strip_expr_leadins(s)
    eq = s.find("=")
    if eq == -1:
        return s
    left = s[:eq].strip()
    right = s[eq + 1 :].strip()
    if _is_named_function_lhs(left) and looks_like_math_expr(right):
        return right
    return s


def math_expr_or_none(expr: str) -> str | None:
    """Return ``expr`` only when it looks like math, not leftover English."""
    stripped = rewrite_english_powers(_strip_expr_leadins(expr))
    if not looks_like_math_expr(stripped):
        return None
    return stripped


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
    ddx_tail = ddx_expr_after(cleaned)
    if ddx_tail is not None:
        ddx = ddx_cue_at(cleaned)
        if ddx is not None and (best_at is None or ddx < best_at):
            return ddx_tail
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
