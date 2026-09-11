"""Pull equations/inequalities out of homework prose."""

from __future__ import annotations

from itertools import pairwise

from app.models.schemas.math import EquationInput
from app.services.math_service.discrete import guess_variables
from app.services.math_service.parse import _normalize_latex_to_sympy
from app.services.math_text_match.scan import MATH_MULTI_LETTER, peel_edge_english

_EQUATION_SIDE_CHARS = frozenset(
    "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+-*/().^ "
)

_FILLER_VERBS = (
    "solve",
    "find",
    "calculate",
    "compute",
    "evaluate",
    "determine",
    "simplify",
    "what is",
    "what's",
)
_SYSTEM_PREFIXES = (
    "the system of equations ",
    "the system ",
    "the equations ",
)


# Two-letter words that sit between homework steps after collapse_ws
# ("…=0 or x-3=0"). 1-letter tokens stay variables; ln/pi stay math.
_TWO_LETTER_ENGLISH = frozenset(
    {"or", "if", "so", "to", "of", "it", "is", "be", "as", "at", "by", "an", "we"}
)


def _english_run_len(s: str, i: int) -> int:
    """Length of an English word starting at ``i``, else 0. Linear scan."""
    n = len(s)
    if i >= n or not s[i].isalpha():
        return 0
    j = i + 1
    while j < n and s[j].isalpha():
        j += 1
    run = s[i:j]
    low = run.lower()
    if low in MATH_MULTI_LETTER:
        return 0
    if len(run) >= 3:
        return j - i
    if len(run) == 2 and low in _TWO_LETTER_ENGLISH:
        return j - i
    return 0


def _english_after(s: str, i: int) -> bool:
    """True when the next token (skipping spaces) is English."""
    n = len(s)
    pos = i
    while pos < n and s[pos] == " ":
        pos += 1
    return _english_run_len(s, pos) > 0


def _english_before(s: str, i: int) -> bool:
    """True when the token ending at ``i`` (exclusive, skipping spaces) is English."""
    k = i
    while k > 0 and s[k - 1] == " ":
        k -= 1
    if k == 0 or not s[k - 1].isalpha():
        return False
    start = k - 1
    while start > 0 and s[start - 1].isalpha():
        start -= 1
    return _english_run_len(s, start) > 0


def _is_equation_side(s: str) -> bool:
    stripped = s.strip()
    if not stripped or len(stripped) > 120:
        return False
    if not all(c in _EQUATION_SIDE_CHARS for c in stripped):
        return False
    k = 0
    n = len(stripped)
    while k < n:
        run = _english_run_len(stripped, k)
        if run:
            # A side that is only a name (`velocity`) is a valid lhs; mixed
            # math + English (`0 Factor it`) is a collapsed homework label.
            has_math = any(c in "0123456789+-*/^()." for c in stripped)
            return not has_math
        if stripped[k].isalpha():
            while k < n and stripped[k].isalpha():
                k += 1
        else:
            k += 1
    return True


def _strip_side_punct(side: str) -> str:
    """Drop sentence punctuation so ``1/2 + 1/3 = x.`` still solves for x."""
    s = side.strip()
    while s and s[-1] in ".?!;:,":
        s = s[:-1].rstrip()
    return s


def _strip_leading_prefixes(text: str, *, strip_bare_x: bool) -> str:
    """Strip leading solve/find/... filler without ``\\s+`` regex pumps."""
    s = text.strip()
    while True:
        prev = s
        low = s.lower()
        if low.startswith("please "):
            s = s[7:].lstrip()
            low = s.lower()
        for polite in ("can you ", "could you "):
            if low.startswith(polite):
                s = s[len(polite) :].lstrip()
                low = s.lower()
                break
        stripped_verb = False
        for verb in _FILLER_VERBS:
            if low.startswith(verb + " "):
                s = s[len(verb) + 1 :].lstrip()
                low = s.lower()
                stripped_verb = True
                break
        if not stripped_verb:
            return s
        if strip_bare_x:
            for sys in _SYSTEM_PREFIXES:
                if low.startswith(sys):
                    s = s[len(sys) :].lstrip()
                    low = s.lower()
                    break
        if low.startswith("for me "):
            s = s[7:].lstrip()
            low = s.lower()
        # "solve the system x + y = 5" used to drop the first x because this
        # path treated a bare "x " filler token the same as the variable in
        # "x + y". Only strip when the next character is not math.
        if strip_bare_x and low.startswith("x "):
            rest = s[2:].lstrip()
            if rest and rest[0] not in "+-*/=^().0123456789":
                s = rest
                low = s.lower()
        if low.startswith("if "):
            s = s[3:].lstrip()
        if s == prev:
            return s
    return s


def _strip_leading_filler(text: str) -> str:
    return _strip_leading_prefixes(text, strip_bare_x=True)


def _strip_leading_verb(text: str) -> str:
    """Verb-only filler — keep bare ``x`` as a possible inequality lhs."""
    return _strip_leading_prefixes(text, strip_bare_x=False)


def try_extract_equations_from_text(text: str) -> list[tuple[str, str]]:
    """Best-effort extraction of every `lhs=rhs` clause in the text.

    BUG FIX (was the most severe correctness bug found in the math system
    audit): this used to be a single re.search, so "solve x+y=5, x-y=1"
    silently extracted only the first clause and answered with the same
    "verified, do NOT recompute" confidence as a fully correct response.
    Walking every ``=`` here returns every clause; callers decide whether 1
    match means a single equation or 2+ means a system.
    """
    # Expand LaTeX first so ``\frac{1}{2}x = 3`` survives the ASCII-only
    # side walker (which rejects ``\`` / ``{}``).
    cleaned = _normalize_latex_to_sympy(_strip_leading_filler(text))
    pairs: list[tuple[str, str]] = []
    start = 0
    while start < len(cleaned):
        eq = cleaned.find("=", start)
        if eq == -1:
            break
        if eq + 1 < len(cleaned) and cleaned[eq + 1] == "=":
            start = eq + 2
            continue
        left = eq
        while left > 0 and cleaned[left - 1] in _EQUATION_SIDE_CHARS:
            if cleaned[left - 1] == " " and _english_before(cleaned, left - 1):
                break
            left -= 1
        right = eq + 1
        while right < len(cleaned) and cleaned[right] in _EQUATION_SIDE_CHARS:
            if _english_after(cleaned, right):
                break
            # `=0 (2x-1)(x-3)=0` — next parenthetical is another equation,
            # not part of this RHS (collapse_ws glued the two displays).
            if cleaned[right] == " " and cleaned[eq + 1 : right].strip() in {
                "0",
                "0.0",
            }:
                nxt = right + 1
                while nxt < len(cleaned) and cleaned[nxt] == " ":
                    nxt += 1
                if nxt < len(cleaned) and cleaned[nxt] == "(":
                    break
            right += 1
        lhs = _strip_side_punct(peel_edge_english(cleaned[left:eq].strip()))
        rhs = _strip_side_punct(peel_edge_english(cleaned[eq + 1 : right].strip()))
        if _is_equation_side(lhs) and _is_equation_side(rhs):
            pairs.append((lhs, rhs))
        start = right if right > eq + 1 else eq + 1
    return _collapse_equal_chain(pairs)


def _collapse_equal_chain(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """``2x+3=3=7`` is one equation (first lhs, last rhs), not ``2x+3=3``.

    Adjacent pairs form a chain when the previous RHS is the next LHS.
    Independent clauses (``x+y=5, x-y=1``) stay separate.
    """
    if len(pairs) < 2:
        return pairs
    for i in range(len(pairs) - 1):
        if pairs[i][1].strip() != pairs[i + 1][0].strip():
            return pairs
    return [(pairs[0][0], pairs[-1][1])]


def try_extract_equation_from_text(text: str) -> EquationInput | None:
    """Best-effort SINGLE-equation extraction — kept for callers that only
    ever want one equation. See try_extract_equations_from_text for the
    multi-equation (system) case."""
    pairs = try_extract_equations_from_text(text)
    if not pairs:
        return None
    lhs, rhs = pairs[0]
    variables = guess_variables(f"{lhs} {rhs}")
    try:
        return EquationInput(lhs=lhs, rhs=rhs, variables=variables or ["x"])
    except Exception:
        return None


# Inequality operators → canonical form. Longer forms first so ``<=`` wins
# over ``<``, and ``\\leq`` wins over ``\\le``. ``\\le``/``\\ge`` must not
# match the prefix inside ``\\left`` / ``\\geq``. ASCII ``<=``/``>=`` are
# required after LaTeX normalize turns ``\\leq`` into ``<=``.
_INEQ_OPS: tuple[tuple[str, str], ...] = (
    ("\\leq", "<="),
    ("\\geq", ">="),
    ("\\le", "<="),
    ("\\ge", ">="),
    ("≤", "<="),
    ("≥", ">="),
    ("<=", "<="),
    (">=", ">="),
    ("<", "<"),
    (">", ">"),
)


def _find_inequality_ops(cleaned: str) -> list[tuple[int, int, str]]:
    """Non-overlapping ``(start, end, canon)`` hits, longest-op-first at each index."""
    hits: list[tuple[int, int, str]] = []
    i = 0
    n = len(cleaned)
    while i < n:
        matched: tuple[int, int, str] | None = None
        for op, canon in _INEQ_OPS:
            if cleaned.startswith(op, i):
                after = i + len(op)
                if op in ("\\le", "\\ge") and after < n and cleaned[after].isalpha():
                    continue
                matched = (i, after, canon)
                break
        if matched is not None:
            hits.append(matched)
            i = matched[1]
        else:
            i += 1
    return hits


def try_extract_compound_inequality_from_text(
    text: str,
) -> tuple[str, str, str, str, str] | None:
    """Extract ``low OP mid OP high`` (e.g. ``1 < x < 5``).

    Returns ``(low, low_op, mid, high_op, high)`` with canonical ops, or None.
    Must run before single-op extract so ``1 < x < 5`` is not eaten as ``1 < x``.
    """
    cleaned = _normalize_latex_to_sympy(_strip_leading_verb(text))
    hits = _find_inequality_ops(cleaned)
    if len(hits) < 2:
        return None
    for a, b in pairwise(hits):
        left = a[0]
        while left > 0 and cleaned[left - 1] in _EQUATION_SIDE_CHARS:
            left -= 1
        low = cleaned[left : a[0]].strip()
        mid = cleaned[a[1] : b[0]].strip()
        right = b[1]
        while right < len(cleaned) and cleaned[right] in _EQUATION_SIDE_CHARS:
            right += 1
        high = cleaned[b[1] : right].strip()
        if not (
            _is_equation_side(low)
            and _is_equation_side(mid)
            and _is_equation_side(high)
            and any(c.isalpha() for c in mid)
        ):
            continue
        return low, a[2], mid, b[2], high
    return None


def try_extract_inequality_from_text(text: str) -> tuple[str, str, str] | None:
    """Best-effort extraction of a single `lhs OP rhs` inequality (OP ∈
    <, >, ≤, ≥, \\leq, \\geq, \\le, \\ge). Returns (lhs, rhs, canonical_comparator)
    or None. NOTE: callers gate this on a math keyword (needs_symbolic_math)
    having already matched, so prose like "less than 5 minutes" (no keyword)
    never reaches here — bare < / > is safe in that context."""
    cleaned = _normalize_latex_to_sympy(_strip_leading_verb(text))
    best: tuple[int, str, str, str] | None = None  # (index, lhs, rhs, canon)
    for start, after, canon in _find_inequality_ops(cleaned):
        left = start
        while left > 0 and cleaned[left - 1] in _EQUATION_SIDE_CHARS:
            left -= 1
        right = after
        while right < len(cleaned) and cleaned[right] in _EQUATION_SIDE_CHARS:
            right += 1
        lhs = cleaned[left:start].strip()
        rhs = cleaned[after:right].strip()
        if _is_equation_side(lhs) and _is_equation_side(rhs):
            if best is None or start < best[0]:
                best = (start, lhs, rhs, canon)
    if best is None:
        return None
    return best[1], best[2], best[3]
