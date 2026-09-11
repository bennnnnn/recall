"""Limit / series / integral / calculus-op cues."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.math_text_match.scan import _CALC_OP, _parse_unsigned_number, ddx_cue_at


def _skip_optional_paren_var(text: str, start: int) -> int:
    """Advance past an optional ``(x)`` / ``(t)`` after Lagrange primes."""
    n = len(text)
    k = start
    if k >= n or text[k] != "(":
        return start
    k += 1
    while k < n and text[k].isspace():
        k += 1
    if k >= n or not text[k].isalpha():
        return start
    k += 1
    while k < n and text[k].isspace():
        k += 1
    if k >= n or text[k] != ")":
        return start
    return k + 1


# Multi-letter names that can carry Lagrange primes (``sin'``, ``ln'``).
# One-letter variables (``y'``, ``f''``) are accepted separately. Long English
# words (``teachers' lounge``) must not look like a derivative.
_MATH_PRIME_NAMES = frozenset(
    {
        "sin",
        "cos",
        "tan",
        "cot",
        "sec",
        "csc",
        "log",
        "ln",
        "lg",
        "exp",
        "sinh",
        "cosh",
        "tanh",
    }
)
_MAX_PRIME_BASE = 8


def _math_prime_base(text: str, prime_at: int) -> bool:
    """True when the token before ``'`` is a variable or function, not English."""
    prev = text[prime_at - 1]
    if prev == ")":
        return True
    if not prev.isalpha():
        return False
    start = prime_at - 1
    while start > 0 and text[start - 1].isalpha():
        start -= 1
        if prime_at - start > _MAX_PRIME_BASE:
            return False
    base = text[start:prime_at]
    if len(base) == 1:
        return True
    return base.lower() in _MATH_PRIME_NAMES


def _lagrange_prime_run(text: str, prime_at: int) -> tuple[int, int] | None:
    """Return ``(after_primes, order)`` when ``'`` at ``prime_at`` is a math prime.

    Rejects contractions (``y'all``), plural possessives (``teachers'``), and
    primes not attached to a letter or ``)``.
    """
    if prime_at <= 0:
        return None
    if not _math_prime_base(text, prime_at):
        return None
    n = len(text)
    j = prime_at
    while j < n and text[j] == "'":
        j += 1
    if j < n and text[j].isalpha():
        return None
    return j, min(j - prime_at, 3)


def lagrange_prime_order(text: str) -> int:
    """Highest Lagrange prime count (``''`` → 2, ``'''`` → 3). 0 if none."""
    best = 0
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "'":
            i += 1
            continue
        run = _lagrange_prime_run(text, i)
        if run is None:
            i += 1
            continue
        after, order = run
        if order > best:
            best = order
        i = after
    return best


def _lagrange_derivative_cue(text: str) -> bool:
    """True for ``y'`` / ``f''(x)`` that are not an ODE assignment (not followed by ``=``)."""
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "'":
            i += 1
            continue
        run = _lagrange_prime_run(text, i)
        if run is None:
            i += 1
            continue
        after, _order = run
        k = _skip_optional_paren_var(text, after)
        while k < n and text[k].isspace():
            k += 1
        if k < n and text[k] == "=":
            i = after
            continue
        return True
    return False


def y_prime_math_cue(text: str) -> bool:
    """``y'`` / ``y''`` as calculus or ODE, not the contraction ``y'all``."""
    start = 0
    while True:
        idx = text.find("y'", start)
        if idx == -1:
            return False
        run = _lagrange_prime_run(text, idx + 1)
        if run is not None:
            return True
        start = idx + 2


def calc_op(text: str) -> str | None:
    m = _CALC_OP.search(text)
    if m:
        return m.group(1).lower()
    if ddx_cue_at(text) is not None:
        return "differentiate"
    if _lagrange_derivative_cue(text):
        return "derivative"
    return None


def _match_limit_point(s: str) -> tuple[str, int] | None:
    """Match infinity / oo / number at start of ``s``; return (token, end)."""
    low = s.lower()
    for tok in ("-infinity", "infinity", "-inf", "inf", "-oo", "oo"):
        if low.startswith(tok):
            return s[: len(tok)], len(tok)
    start = 1 if s.startswith("-") else 0
    hit = _parse_unsigned_number(s, start)
    if hit is None or (start == 1 and hit[1] == 1):
        return None
    return s[: hit[1]], hit[1]


def _parse_signed_int_token(s: str) -> tuple[str, int] | None:
    start = 1 if s.startswith("-") else 0
    if start >= len(s) or not s[start].isdigit():
        return None
    i = start
    while i < len(s) and s[i].isdigit():
        i += 1
    return s[:i], i


@dataclass(frozen=True)
class LimitHit:
    expr: str
    var: str
    point: str


def _parse_latex_limit(text: str) -> LimitHit | None:
    """Parse ``\\lim_{x \\to 0} expr`` without optional-space regex pumps."""
    idx = text.find("\\lim")
    if idx == -1:
        return None
    rest = text[idx + 4 :]
    while rest.startswith("_") or rest.startswith(" "):
        rest = rest[1:]
    if rest.startswith("{"):
        rest = rest[1:]
    rest = rest.lstrip(" ")
    if not rest or not rest[0].isalpha():
        return None
    var = rest[0]
    rest = rest[1:].lstrip(" ")
    arrow = None
    for candidate in ("\\to", "->", "→"):
        if rest.startswith(candidate):
            arrow = candidate
            break
    if arrow is None:
        return None
    rest = rest[len(arrow) :].lstrip(" ")
    point_hit = _match_limit_point(rest)
    if point_hit is not None:
        point, plen = point_hit
    elif rest.lower().startswith("-\\infty"):
        point, plen = "-\\infty", 7
    elif rest.lower().startswith("\\infty"):
        point, plen = "\\infty", 6
    else:
        return None
    rest = rest[plen:].lstrip(" ")
    if rest.startswith("}"):
        rest = rest[1:].lstrip(" ")
    expr = rest.strip()
    if not expr:
        return None
    return LimitHit(expr=expr, var=var, point=point)


def parse_limit(text: str) -> LimitHit | None:
    lower = text.lower()
    # Compact: lim x->0 expr
    if lower.startswith("lim ") or " lim " in f" {lower} ":
        idx = lower.find("lim ")
        rest = text[idx + 4 :].strip()
        # var
        if not rest:
            return None
        var = rest[0]
        if not var.isalpha():
            return None
        rest_l = rest[1:].lstrip()
        for arrow in ("->", "→"):
            if rest_l.startswith(arrow):
                rest_l = rest_l[len(arrow) :].lstrip()
                break
        else:
            return None
        point_hit = _match_limit_point(rest_l)
        if not point_hit:
            return None
        point, pend = point_hit
        expr = rest_l[pend:].strip()
        if expr.lower().startswith("of "):
            expr = expr[3:].strip()
        if expr:
            return LimitHit(expr=expr, var=var, point=point)
    # Prose: ... as x approaches 0
    as_idx = lower.find(" as ")
    if as_idx != -1 and ("limit" in lower or "lim" in lower):
        before = text[:as_idx].strip()
        for lead in (
            "find ",
            "evaluate ",
            "compute ",
            "what is ",
            "determine ",
            "the ",
            "limit of ",
        ):
            low = before.lower()
            if low.startswith(lead):
                before = before[len(lead) :].strip()
        after = text[as_idx + 4 :].strip()
        if not after or not after[0].isalpha():
            return None
        var = after[0]
        rest = after[1:].lstrip().lower()
        for cue in ("approaches ", "goes to ", "tends to ", "->", "→", "to "):
            if rest.startswith(cue):
                rest = rest[len(cue) :].lstrip()
                break
        else:
            return None
        # prose uses "infinity" / "inf" / number (allow longer "infinity" spelling)
        point_hit = _match_limit_point(rest)
        if point_hit is None:
            for tok in ("-infinity", "infinity"):
                if rest.startswith(tok):
                    point_hit = (tok, len(tok))
                    break
        if not point_hit or not before:
            return None
        return LimitHit(expr=before, var=var, point=point_hit[0])
    return _parse_latex_limit(text)


@dataclass(frozen=True)
class SeriesHit:
    expr: str
    var: str
    start: str
    end: str


def _parse_latex_series(text: str) -> SeriesHit | None:
    """Parse ``\\sum_{n=1}^{\\infty} expr`` without optional-space regex pumps."""
    idx = text.find("\\sum")
    if idx == -1:
        return None
    rest = text[idx + 4 :]
    while rest.startswith("_") or rest.startswith(" "):
        rest = rest[1:]
    if rest.startswith("{"):
        rest = rest[1:]
    rest = rest.lstrip(" ")
    if not rest or not rest[0].isalpha():
        return None
    var = rest[0]
    rest = rest[1:].lstrip(" ")
    if not rest.startswith("="):
        return None
    rest = rest[1:].lstrip(" ")
    start_hit = _parse_signed_int_token(rest)
    if start_hit is None:
        return None
    start, send = start_hit
    rest = rest[send:].lstrip(" ")
    if rest.startswith("}"):
        rest = rest[1:].lstrip(" ")
    if not rest.startswith("^"):
        return None
    rest = rest[1:].lstrip(" ")
    if rest.startswith("{"):
        rest = rest[1:]
    rest = rest.lstrip(" ")
    end_tok: str | None = None
    low = rest.lower()
    for tok in ("\\infty", "infinity"):
        if low.startswith(tok):
            end_tok = rest[: len(tok)]
            rest = rest[len(tok) :]
            break
    if end_tok is None:
        end_hit = _parse_signed_int_token(rest)
        if end_hit is None:
            return None
        end_tok, eend = end_hit
        rest = rest[eend:]
    rest = rest.lstrip(" ")
    if rest.startswith("}"):
        rest = rest[1:].lstrip(" ")
    expr = rest.strip()
    if not expr:
        return None
    return SeriesHit(expr=expr, var=var, start=start, end=end_tok)


def parse_series(text: str) -> SeriesHit | None:
    lower = text.lower()
    if not any(k in lower for k in ("sum ", "series", "converge", "diverge")):
        # also bare "sum of"
        if "sum" not in lower:
            return None
    # sum|series [of] EXPR from VAR=START to END
    for head in ("sum of ", "series of ", "sum ", "series "):
        idx = lower.find(head)
        if idx == -1:
            continue
        rest = text[idx + len(head) :]
        from_idx = rest.lower().find(" from ")
        if from_idx == -1:
            continue
        expr = rest[:from_idx].strip()
        tail = rest[from_idx + 6 :].strip()
        parts = tail.replace(" ", "")
        # var=START to END — linear scan on compacted digits
        if not parts or not parts[0].isalpha():
            continue
        var = parts[0]
        if len(parts) < 2 or parts[1] != "=":
            continue
        after_eq = parts[2:]
        start_hit = _parse_signed_int_token(after_eq)
        if start_hit is None:
            continue
        start, send = start_hit
        after_start = after_eq[send:]
        if not after_start.lower().startswith("to"):
            continue
        after_to = after_start[2:]
        end_tok: str | None = None
        low_end = after_to.lower()
        for tok in ("infinity", "inf", "oo"):
            if low_end.startswith(tok):
                end_tok = after_to[: len(tok)]
                break
        if end_tok is None:
            end_hit = _parse_signed_int_token(after_to)
            if end_hit is None:
                continue
            end_tok = end_hit[0]
        if expr:
            return SeriesHit(expr=expr, var=var, start=start, end=end_tok)
    return _parse_latex_series(text)


def integral_bounds(expr: str) -> tuple[str, str, str] | None:
    """Return (expr_without_bounds, lo, hi) for trailing ``from LO to HI``."""
    lower = expr.lower()
    idx = lower.rfind(" from ")
    if idx == -1:
        return None
    head = expr[:idx].strip()
    tail = expr[idx + 6 :].strip()
    to_idx = tail.lower().find(" to ")
    if to_idx == -1:
        return None
    lo = tail[:to_idx].strip()
    hi = tail[to_idx + 4 :].strip()
    if head and lo and hi and " " not in hi:
        return head, lo, hi
    return None
