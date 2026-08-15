"""Pull equations/inequalities out of homework prose."""

from __future__ import annotations

from itertools import pairwise

from app.models.math_schemas import EquationInput
from app.services.math_service.discrete import guess_variables
from app.services.math_service.parse import _normalize_latex_to_sympy

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


def _is_equation_side(s: str) -> bool:
    stripped = s.strip()
    if not stripped or len(stripped) > 120:
        return False
    return all(c in _EQUATION_SIDE_CHARS for c in stripped)


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
        if strip_bare_x and low.startswith("x "):
            s = s[2:].lstrip()
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
            left -= 1
        right = eq + 1
        while right < len(cleaned) and cleaned[right] in _EQUATION_SIDE_CHARS:
            right += 1
        lhs = cleaned[left:eq].strip()
        rhs = cleaned[eq + 1 : right].strip()
        if _is_equation_side(lhs) and _is_equation_side(rhs):
            pairs.append((lhs, rhs))
        start = right if right > eq + 1 else eq + 1
    return pairs


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
