"""The plain reading every part of a graph's check shares: a text in the formula reader's
spelling, a number in it, the comparisons of a variable it writes, its clauses, and whether
two numbers are one.

A question and a description are read the same way: ``plain`` first (x⁵, eˣ, √x and
|x² - 1| as they are written), then the solver's own formula reader (``tool_check``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sympy import Expr, Float, Symbol

from app.modules.math.solve.latex_normalize import rewrite_abs_bars
from app.modules.math.solve.unicode_normalize import (
    rewrite_unicode_script_runs,
    rewrite_unicode_sqrts,
)
from app.modules.math.tool_check import parse_formula, written_relations
from app.services.glyphs import OPERATOR_GLYPHS

# The reader's own glyphs, on top of the shared operator table (services/glyphs).
_READER_GLYPHS = {
    "≤": "<=", "≥": ">=", "≠": " != ", "π": "pi", "\\pi": "pi"
}  # fmt: skip
_OPERATORS = str.maketrans(OPERATOR_GLYPHS)
# A differential after an integrand: the "dx" of "∫ sin x dx".
_DIFFERENTIAL = re.compile(r"(?<=\S)\s+d[a-z](?![\w/])")
# An integral's bounds as scripts: "∫₀²", "\\int_0^2", "∫_{-1}^{3}", read as the words
# "from 0 to 2 of" that every interval reader reads; LaTeX's thin spaces as spaces.
_BOUND = r"(?:\{([^{}]{1,12})\}|(-?[\w.]{1,8}))"
_SCRIPTED_INTEGRAL = re.compile(rf"(?:∫|\\int)\s*_\s*{_BOUND}\s*(?:\^|\*\*)\s*{_BOUND}")
_THIN_SPACE = re.compile(r"\\[,;:!]")
# A function defined: "f(x) =", "g(t)=".
DEFINES = re.compile(r"\b[a-zA-Z]\(\s?[a-z]\s?\)\s?=")
LOWER, UPPER = frozenset({">", ">="}), frozenset({"<", "<="})
_FLIPPED = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "=": "=", "!=": "!="}


def plain(text: str) -> str:
    """``text`` in the spelling the formula reader reads: the solver's own rewrites of
    operators, superscripts and roots (``solve.unicode_normalize``), |…| as Abs(…) as the
    solver reads it (``solve.latex_normalize``), an integral's scripted bounds in words,
    and no differential after an integrand."""
    out = text.translate(_OPERATORS)
    for glyph, written in _READER_GLYPHS.items():
        out = out.replace(glyph, written)
    out = rewrite_unicode_sqrts(rewrite_unicode_script_runs(out))
    out = _SCRIPTED_INTEGRAL.sub(_integral_words, _THIN_SPACE.sub(" ", out))
    return _DIFFERENTIAL.sub("", rewrite_abs_bars(out, apart=True))


def _integral_words(match: re.Match[str]) -> str:
    low = match.group(1) or match.group(2)
    high = match.group(3) or match.group(4)
    return f"∫ from {low} to {high} of "


def number(text: str) -> Any | None:
    """The real number ``text`` writes ("-1/2", "π/4", "e^2", "1.5708"), or None."""
    parsed = parse_formula(plain(text.strip().rstrip(".,;:")))
    if not isinstance(parsed, Expr) or not parsed.is_number or parsed.is_real is False:
        return None
    return parsed


def same_number(a: Any, b: Any, rel: float = 1e-9) -> bool:
    """``b``, a value a description writes, is ``a``: to ``rel`` of its size, or to the
    places a decimal written for it holds (π/2 written 1.5708)."""
    try:
        near = max(rel, 1e-4) if isinstance(b, Float) else rel
        return abs(float(a) - float(b)) <= near * max(1.0, abs(float(b)))
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class Condition:
    """One comparison of the variable a clause writes: (op, the value or a letter)."""

    op: str
    value: Any


def conditions(text: str, variables: frozenset[str] = frozenset("x")) -> list[Condition]:
    """The comparisons of the variable ``text`` writes, each with the variable on the left
    ("-5 < x <= -2" is x > -5 and x <= -2; "0 ≤ t ≤ 4"; "x ≠ 1"). A value may be a letter
    ("x < a"), which a question leaves to its working."""
    found: list[Condition] = []
    for lhs, op, rhs in written_relations(text.replace("!=", " neq ")):
        if isinstance(lhs, Symbol) and str(lhs) in variables and (rhs.is_number or rhs.is_Symbol):
            found.append(Condition(op, rhs))
        elif isinstance(rhs, Symbol) and str(rhs) in variables and (lhs.is_number or lhs.is_Symbol):
            found.append(Condition(_FLIPPED[op], lhs))
    for part in text.split("!=")[1:]:
        value = number(part.strip().split(" ")[0])
        if value is not None:
            found.append(Condition("!=", value))
    return found


def parts(text: str) -> list[str]:
    """The clauses ``text`` is written in: split at ";", a new line, LaTeX's row break, a
    sentence's end, and wherever a function is defined again ("f(x) = 2^x if x <= 1, and
    f(x) = 1 + 1/x if x > 1")."""
    found: list[str] = []
    for part in re.split(r"[;\n]|\\\\|\.\s(?=[A-Z])", text):
        starts = [m.start() for m in DEFINES.finditer(part)][1:]
        for start, end in zip([0, *starts], [*starts, len(part)], strict=True):
            found.append(part[start:end])
    return found
