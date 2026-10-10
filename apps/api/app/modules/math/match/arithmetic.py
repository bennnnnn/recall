"""Whole-message numeric arithmetic, kept out of the dimension scan.

A cue such as "what is" or "how would you calculate" is stripped, then the
remainder has to be a number expression. Dates and phone numbers stay out.
"""

from __future__ import annotations

import re

from app.services.text_match import word_index
from app.services.text_normalize import collapse_ws

_MAX = 1000

# Whole-message arithmetic cues. Longer phrases first so "what is" does not
# leave "the value of" behind.
_ARITH_CUES: tuple[str, ...] = (
    "how would you calculate",
    "how would you compute",
    "how would you evaluate",
    "how do you calculate",
    "how do you compute",
    "how can you calculate",
    "can you calculate",
    "could you calculate",
    "the value of",
    "what is",
    "what's",
    "whats",
    "calculate",
    "compute",
    "evaluate",
    "please",
)
# OCR / keyboard glyphs → ASCII before SymPy. Keep ÷ unambiguous *before* this
# map so a lone ASCII `/` can still look like a date.
_ARITH_OP_ASCII: tuple[tuple[str, str], ...] = (
    ("\u00d7", "*"),
    ("\u22c5", "*"),
    ("\u00b7", "*"),
    ("\u2217", "*"),
    ("\u00f7", "/"),
    ("\u2215", "/"),
    ("\u2044", "/"),
    ("\u2212", "-"),
    ("\u2013", "-"),
    ("\u2014", "-"),
)
_UNAMBIGUOUS_ARITH = frozenset("*^" + "".join(src for src, dst in _ARITH_OP_ASCII if dst in "*/"))
_ARITH_ALLOWED = frozenset("0123456789.+-*/^() " + "".join(src for src, _ in _ARITH_OP_ASCII))


def _strip_arith_cues(lower: str) -> tuple[str, bool]:
    """Remove whole-word compute cues. Linear ``word_index``, no regex."""
    had = False
    s = lower
    changed = True
    while changed:
        changed = False
        for cue in _ARITH_CUES:
            idx = word_index(s, cue)
            if idx == -1:
                continue
            s = s[:idx] + " " + s[idx + len(cue) :]
            had = True
            changed = True
            break
    s = s.strip()
    while s and s[-1] in "?.!":
        s = s[:-1].rstrip()
    return collapse_ws(s), had


def _to_ascii_arith(expr: str) -> str:
    out = expr
    for src, dst in _ARITH_OP_ASCII:
        out = out.replace(src, dst)
    return out


def _binary_ops_only_minus_or_slash(compact: str) -> bool:
    """True when every binary operator is ``-`` or ``/`` (dates, phone numbers)."""
    for ch in compact.removeprefix("+"):
        if ch in "+*^":
            return False
    return True


def _looks_like_date_or_phone(compact: str) -> bool:
    """Structural dates (``9/7/2026``) and phones (``1-800-273-8255``).

    Linear scan — not a blanket reject of every ``-``/``/`` chain, so
    ``10-3-2`` and ``100/5/2`` stay calculator arithmetic.
    """
    compact = compact.removeprefix("+")
    if not compact or compact[0] == "-":
        return False
    if re.fullmatch(r"(?:\+?1-?)?\(\d{3}\)\d{3}-\d{4}", compact):
        return True
    groups: list[int] = []
    seps: list[str] = []
    i = 0
    n = len(compact)
    while i < n:
        ch = compact[i]
        if ch.isdigit():
            j = i + 1
            while j < n and compact[j].isdigit():
                j += 1
            groups.append(j - i)
            i = j
            continue
        if ch in "-/":
            seps.append(ch)
            i += 1
            continue
        return False
    if not seps or len(groups) != len(seps) + 1:
        return False
    all_slash = all(sep == "/" for sep in seps)
    all_minus = all(sep == "-" for sep in seps)
    if not (all_slash or all_minus):
        return False
    if len(groups) == 2:
        # Seven-digit phone and year-month date. A bare short subtraction
        # such as 2-6 is arithmetic; prose ranges never pass the allowlist.
        a, b = groups
        return all_minus and ((a == 3 and b == 4) or (a == 4 and b == 2))
    if len(groups) == 3:
        a, b, c = groups
        if a <= 2 and b <= 2 and c in (2, 4):
            return True
        if a == 4 and b <= 2 and c <= 2:
            return True
        return all_minus and a == 3 and b == 3 and c == 4
    return all_minus and len(groups) >= 4 and sum(groups) >= 7


def _unambiguous_single_slash(compact: str) -> bool:
    """True for a two-number division that cannot reasonably be a date.

    A bare ``9/9`` remains ambiguous, as do year/month forms such as
    ``2026/09``.  Values such as ``456/56`` are not calendar-shaped and should
    reach the arithmetic solver instead of leaving a model to improvise long
    division in plain text.
    """
    if compact.count("/") != 1 or any(ch in compact for ch in "+-*^()"):
        return False
    left, right = compact.split("/", 1)
    if not left or not right:
        return False
    if "." in left or "." in right:
        return all(part.replace(".", "", 1).isdigit() for part in (left, right))
    if not left.isdigit() or not right.isdigit():
        return False
    first, second = int(left), int(right)
    if len(left) == 4 and 1 <= second <= 12:
        return False
    could_be_month_day = (1 <= first <= 12 and 1 <= second <= 31) or (
        1 <= second <= 12 and 1 <= first <= 31
    )
    return not could_be_month_day


def _count_binary_arith_ops(compact: str) -> int:
    """Binary ``+ - * / ^`` in an ASCII expression. Leading/unary ``-`` is not an op."""
    ops = 0
    prev_was_op = True
    for ch in compact:
        if ch in "+*/^":
            ops += 1
            prev_was_op = True
            continue
        if ch == "-":
            if not prev_was_op:
                ops += 1
            prev_was_op = True
            continue
        if ch == "(":
            prev_was_op = True
            continue
        if ch == ")":
            prev_was_op = False
            continue
        prev_was_op = False
    return ops


def _arith_parens_ok(compact: str) -> bool:
    depth = 0
    for ch in compact:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def bare_arithmetic_expr(text: str) -> str | None:
    """Whole-message numeric arithmetic, or None.

    Shared by the SymPy gate and the arithmetic extractor so ``8-8*2`` cannot
    be gated as a dimension pair (``8*2``) and then fail extract.

    Bare subtraction is arithmetic; a single ``/`` needs a cue unless its
    values cannot reasonably be a date (for example ``456/56``).
    Auto-accept with a single subtraction, ``*``, ``^``, times/divide glyphs, two or
    more operators, or a cue word (``what is``, ``calculate``, ...).
    Uncued ``-``/``/`` chains that look like a date or phone are rejected;
    chained arithmetic such as ``10-3-2`` is not.
    """
    if not text or len(text) > _MAX:
        return None
    stripped, had_cue = _strip_arith_cues(text.lower())
    if not stripped or not any(ch.isdigit() for ch in stripped):
        return None
    from app.modules.math.solve.parse import _normalize_latex_to_sympy

    normalized = _normalize_latex_to_sympy(stripped)
    # Numeric radicals and keyboard braced powers use the same normalization
    # as the solver. Only sqrt is admitted here; symbols/prose stay excluded.
    numeric = normalized.replace("sqrt(", "(")
    if any(ch not in _ARITH_ALLOWED for ch in numeric):
        return None
    compact = _to_ascii_arith(numeric).replace(" ", "")
    if not compact or not _arith_parens_ok(compact):
        return None
    if compact[-1] not in "0123456789)":
        return None
    if compact[0] not in "0123456789.(+-":
        return None
    ops = _count_binary_arith_ops(compact)
    has_root = "sqrt(" in normalized
    if ops < 1 and not has_root:
        return None
    unambiguous = has_root or any(ch in stripped for ch in _UNAMBIGUOUS_ARITH)
    unambiguous = unambiguous or "**" in normalized
    unambiguous = unambiguous or _unambiguous_single_slash(compact)
    subtraction = ops == 1 and "-" in compact and not any(ch in "+*/^" for ch in compact)
    # ``-3+5`` is one signed start and one operation, not a date.
    signed_start = compact[0] in "+-" and ops >= 1
    if not (unambiguous or subtraction or ops >= 2 or had_cue or signed_start):
        return None
    # Dates / phones: structural ``9/7/2026`` / ``1-800-273-8255``, not
    # every minus-or-slash chain (``10-3-2``). Keep ``8-8*2`` and cued ``9/9``.
    if (
        not had_cue
        and not unambiguous
        and _binary_ops_only_minus_or_slash(compact)
        and _looks_like_date_or_phone(compact)
    ):
        return None
    return collapse_ws(_to_ascii_arith(normalized))
