"""Unicode maths glyphs from OCR and homework as ASCII: operators, vulgar fractions,
superscripts and subscripts, and root signs."""

from __future__ import annotations

from app.services.glyphs import OPERATOR_GLYPHS, SUPERSCRIPT_GLYPHS
from app.services.script_runs import (
    fold_subscript_runs,
    fold_superscript_runs,
    root_index_at,
    unclear_root_index,
)

# OCR / homework unicode operators → ASCII before the allowlist runs.
# Do NOT widen `_SAFE_EXPR_CHARS`; map glyphs here instead.
# Escapes (not literals) keep RUF001 from flagging lookalike punctuation.
# The operators are the shared table (services/glyphs.py); π and ∞ are the solver's own.
# π is bracketed so a letter beside it stays a factor: "sin(πx)" was the one name "pix".
_UNICODE_OP_SUBS: tuple[tuple[str, str], ...] = (
    *OPERATOR_GLYPHS.items(),
    ("\u03c0", "(pi)"),  # π
    ("\u221e", "oo"),  # ∞
)

_UNICODE_VULGAR: tuple[tuple[str, str], ...] = (
    ("\u00bd", "(1)/(2)"),
    ("\u2153", "(1)/(3)"),
    ("\u2154", "(2)/(3)"),
    ("\u00bc", "(1)/(4)"),
    ("\u00be", "(3)/(4)"),
    ("\u2155", "(1)/(5)"),
    ("\u2156", "(2)/(5)"),
    ("\u2157", "(3)/(5)"),
    ("\u2158", "(4)/(5)"),
    ("\u2159", "(1)/(6)"),
    ("\u215a", "(5)/(6)"),
    ("\u215b", "(1)/(8)"),
    ("\u215c", "(3)/(8)"),
    ("\u215d", "(5)/(8)"),
    ("\u215e", "(7)/(8)"),
)


def _rewrite_unicode_script_runs(s: str) -> str:
    """``x²`` → ``x**2``, ``eˣ`` → ``e**x``, ``e⁻ˣ`` → ``e**(-x)``, ``x₁`` → ``x_1``: the
    one reading every reader shares (``services/script_runs.py``)."""
    return fold_subscript_runs(fold_superscript_runs(s, mark="**", group_numbers=True))


_UNICODE_HIGHER_ROOTS = {"\u221b": "3", "\u221c": "4"}  # cube and fourth root signs


def _higher_root_at(s: str, i: int) -> tuple[str, int] | None:
    """The index of a root sign at ``i`` and where the sign ends: ``∛``, ``∜``, or an index
    raised before ``√`` (``⁵√32``, the shared reading's ``root_index_at``)."""
    index = _UNICODE_HIGHER_ROOTS.get(s[i])
    if index is not None:
        return index, i + 1
    return root_index_at(s, i)


def _rewrite_unicode_higher_roots(s: str) -> str:
    """``∛(x)`` / ``∛8`` / ``⁵√32`` → ``((x))**(1/3)``; a sign with nothing after it is left
    alone."""
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        root = _higher_root_at(s, i)
        if root is None:
            out.append(s[i])
            i += 1
            continue
        index, j = root
        while j < n and s[j] in " \t":
            j += 1
        if j < n and s[j] == "(":
            depth = 1
            k = j + 1
            while k < n and depth:
                depth += {"(": 1, ")": -1}.get(s[k], 0)
                k += 1
            if depth:
                out.append(s[i])
                i += 1
                continue
            body = s[j + 1 : k - 1]
        else:
            k = j
            while k < n and (s[k].isalnum() or s[k] == "."):
                k += 1
            body = s[j:k]
        if not body.strip():
            out.append(s[i])
            i += 1
            continue
        out.append(f"(({body})**(1/{index}))")
        i = k
    return "".join(out)


def _after_unclear_index(s: str, root_at: int) -> bool:
    """Raised digits glued to what they could raise stand before the root sign at
    ``root_at``: ``2³√27`` is 2∛27 or 2³·√27 (``services/script_runs.py``)."""
    start = root_at
    while (
        start and s[start - 1] in SUPERSCRIPT_GLYPHS and SUPERSCRIPT_GLYPHS[s[start - 1]].isdigit()
    ):
        start -= 1
    return start < root_at and unclear_root_index(s, start)


def _rewrite_unicode_sqrts(s: str) -> str:
    """``√9`` / ``√x`` / ``√(x+1)`` → ``sqrt(...)``. Linear scan, leftover ``√`` → ``sqrt``."""
    out: list[str] = []
    i = 0
    n = len(s)
    root = "\u221a"
    while i < n:
        if s[i] != root:
            out.append(s[i])
            i += 1
            continue
        if _after_unclear_index(s, i):
            out.append(root)  # left for the parser to refuse: index or power, nothing says
            i += 1
            continue
        i += 1
        while i < n and s[i] in " \t":
            i += 1
        if i >= n:
            out.append("sqrt")
            break
        if s[i] == "(":
            depth = 1
            j = i + 1
            while j < n and depth:
                if s[j] == "(":
                    depth += 1
                elif s[j] == ")":
                    depth -= 1
                j += 1
            if depth == 0:
                out.append("sqrt(")
                out.append(s[i + 1 : j - 1])
                out.append(")")
                i = j
                continue
            out.append("sqrt")
            continue
        if s[i].isdigit():
            j = i
            while j < n and s[j].isdigit():
                j += 1
            if j < n and s[j] == "." and j + 1 < n and s[j + 1].isdigit():
                j += 1
                while j < n and s[j].isdigit():
                    j += 1
            out.append("sqrt(")
            out.append(s[i:j])
            out.append(")")
            i = j
            continue
        if s[i].isalpha():
            out.append("sqrt(")
            out.append(s[i])
            out.append(")")
            i += 1
            continue
        out.append("sqrt")
    return "".join(out)
