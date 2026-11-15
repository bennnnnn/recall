"""What a question states that a graph may draw: its formulas, its values and its pieces.

A curve is drawn only from a formula the question writes ("f(x) = x²|9 - x²|/(3 - x)",
"x = 9 - 2y²", "the line y = 3"), compared with SymPy, never from one the reply worked out
(a salary's pieces written only in words draw nothing). A bound, a point of contact or the
end of an interval is a value the question writes ("x = e", "from x = -1/2 to x = 3/2",
"[1, 2]") unless the server finds it (``plot_check``). A function defined in pieces is held
clause by clause: each piece's formula and its condition ("-5 < x <= -2") are written
together, so a piece never takes a neighbour's formula or an end it does not have.

The question is read in a plain spelling first (``plain``), so x⁵, eˣ, √x and |x² - 1|
read as they are written.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sympy import Expr, Rational, Symbol

from app.modules.math.figure.grounding import written_numbers, written_pairs
from app.modules.math.solve.unicode_normalize import (
    rewrite_unicode_script_runs,
    rewrite_unicode_sqrts,
)
from app.modules.math.tool_check import parse_formula, written_expressions, written_relations
from app.services.glyphs import OPERATOR_GLYPHS

# The reader's own glyphs, on top of the shared operator table (services/glyphs).
_READER_GLYPHS = {"\u2264": "<=", "\u2265": ">=", "\u2260": " != ", "\u03c0": "pi"}
# Where a formula written after "=" ends: a clause's punctuation or a word of English.
_ENDS = frozenset(
    "if for when on from and is at which that has where with between to in then over about "
    "find show sketch draw".split()
)
# "f(1) = 5": a value the question gives a function at a point.
_POINT_VALUE = re.compile(r"\b[a-z]\(\s*([-+]?[\w./]{1,12})\s*\)\s*=\s*([-+]?[\w./]{1,12})")
# "[1, 2]" or "[-2, 2]": an interval the question writes.
_INTERVAL = re.compile(r"\[\s*([^\[\],]{1,16}),\s*([^\[\],]{1,16})\]")
# A function defined: "f(x) =", "g(t)=".
_DEFINES = re.compile(r"\b[a-zA-Z]\(\s?[a-z]\s?\)\s?=")
# An interval written in words: "from -π/2 to π/2", "between x = 1 and x = 2".
_FROM_TO = re.compile(
    r"\b(?:from|between)\s(?:[a-z]\s?=\s?)?([-+]?[\w./()]{1,12})\s(?:to|and)\s(?:[a-z]\s?=\s?)?([-+]?[\w./()]{1,12})"
)
_NUMBER = r"([-+]?\d+(?:\.\d+)?(?:/\d+)?)"
_SLOPE = re.compile(r"\b(?:slope|gradient)\s(?:of\s|is\s|=\s?)?" + _NUMBER)
_COUNT = re.compile(
    _NUMBER + r"\s(?:equal\s)?(?:sub)?(?:intervals|rectangles|strips)\b|\bn\s?=\s?" + _NUMBER
)
# A differential after an integrand: the "dx" of "∫ sin x dx".
_DIFFERENTIAL = re.compile(r"(?<=\S)\s+d[a-z](?![\w/])")
_COMPARISONS = ("<=", ">=", "!=", "<", ">", "=")
_OPERATORS = str.maketrans(OPERATOR_GLYPHS)
_FLIPPED = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "=": "=", "!=": "!="}


def plain(text: str) -> str:
    """``text`` in the spelling the formula reader reads: the solver's own rewrites of
    operators, superscripts and roots (``solve.unicode_normalize``), then |…| as abs(…)
    and no differential after an integrand."""
    out = text.translate(_OPERATORS)
    for glyph, written in _READER_GLYPHS.items():
        out = out.replace(glyph, written)
    out = rewrite_unicode_sqrts(rewrite_unicode_script_runs(out))
    return _DIFFERENTIAL.sub("", _bars(out))


def _bars(text: str) -> str:
    """|A| as abs(A): a bar opens where nothing is open or after an operator, else closes."""
    out: list[str] = []
    depth = 0
    for ch in text:
        if ch != "|":
            out.append(ch)
            continue
        before = "".join(out).rstrip()[-1:]
        if depth == 0 or before in {"", "(", "+", "-", "*", "/", "^", "=", ","}:
            # A word apart from what stands before it: ln|x| is ln abs(x), never the name
            # "lnabs", and x²|9 - x²| a product, never a power 2·|9 - x²|.
            out.append(" abs(" if before.isalnum() or before == ")" else "abs(")
            depth += 1
        else:
            out.append(")")
            depth -= 1
    return "".join(out) + ")" * depth


@dataclass(frozen=True)
class Written:
    """A formula the question writes: what it names ("y", "x", "f") and its right side."""

    name: str
    expr: Any


@dataclass(frozen=True)
class Condition:
    """One comparison of the variable a clause writes: (op, the value or a letter)."""

    op: str
    value: Any


@dataclass(frozen=True)
class Clause:
    formulas: tuple[Any, ...]
    conditions: tuple[Condition, ...]
    # "f(1) = 5": (1, 5).
    point_values: tuple[tuple[Any, Any], ...]


@dataclass(frozen=True)
class PlotQuestion:
    formulas: tuple[Written, ...]
    # Every value written outside a formula ("a slope of -3", "5 subintervals"), and the
    # values it gives x ("at x = e", "from x = 0 to x = π/2", "[1, 2]").
    values: tuple[Any, ...]
    x_values: tuple[Any, ...]
    # A value the question names a slope ("a slope of -3", "gradient 2"), and a count of
    # rectangles ("5 subintervals", "n = 4"): a number elsewhere ("the area is 9") is
    # neither.
    slopes: tuple[Any, ...]
    counts: tuple[int, ...]
    pairs: frozenset[tuple[Any, Any]]
    clauses: tuple[Clause, ...]
    words: str


def _number(text: str) -> Any | None:
    parsed = parse_formula(text)
    return parsed if isinstance(parsed, Expr) and not parsed.free_symbols else None


def _equals_spans(text: str) -> list[tuple[str, str]]:
    """Each "name = formula" the text writes, the formula cut at a clause's end."""
    found: list[tuple[str, str]] = []
    for at in [i for i, ch in enumerate(text) if ch == "="]:
        if text[at - 1 : at] in {"<", ">", "!", "="} or text[at + 1 : at + 2] == "=":
            continue
        head = text[:at].rstrip()
        name = head[-4:] if head.endswith(")") and head[-4:-3].isalpha() else head[-1:]
        words: list[str] = []
        for word in text[at + 1 :].split(" "):
            bare = word.strip().lower().rstrip(".,;:")
            if bare in _ENDS or any(mark in word for mark in ";\n"):
                if any(mark in word for mark in ";\n"):
                    words.append(re.split(r"[;\n]", word)[0])
                break
            words.append(word)
            if word.rstrip().endswith((",", ".")) and not word.rstrip()[-2:-1].isdigit():
                break
        formula = " ".join(words).strip().rstrip(".,;:")
        if name.strip() and formula:
            found.append((name.strip(), formula))
    return found


def _without_unit(formula: str) -> str:
    """ "t² - 4t + 3 m/s" without its unit: the last word when it is letters and a slash or
    two or more letters, after a number."""
    head, _, last = formula.rpartition(" ")
    bare = last.replace("/", "").replace("^", "")
    if head and head.rstrip()[-1:].isdigit() and bare.isalpha() and (len(bare) > 1 or "/" in last):
        return head.rstrip()
    return formula


def _formulas(text: str) -> list[Written]:
    found: list[Written] = []
    for name, formula in _equals_spans(text):
        parsed = parse_formula(_without_unit(formula))
        if isinstance(parsed, Expr):
            found.append(Written(name[0], parsed))
    for lhs, op, rhs in written_relations(text):
        if op == "=" and isinstance(lhs, Symbol):
            found.append(Written(str(lhs), rhs))
        elif op == "=" and lhs.is_Mul and len(lhs.free_symbols) == 2:
            found.append(Written(str(min(lhs.free_symbols, key=str)), rhs))
    found += [Written("", expr) for expr in written_expressions(text)]
    return found


def _conditions(text: str, variables: frozenset[str] = frozenset("x")) -> list[Condition]:
    """The comparisons of the variable ("-5 < x <= -2", "0 ≤ t ≤ 4", "x ≠ 1")."""
    found: list[Condition] = []
    for lhs, op, rhs in written_relations(text.replace("!=", " neq ")):
        if isinstance(lhs, Symbol) and str(lhs) in variables and (rhs.is_number or rhs.is_Symbol):
            found.append(Condition(op, rhs))
        elif isinstance(rhs, Symbol) and str(rhs) in variables and (lhs.is_number or lhs.is_Symbol):
            found.append(Condition(_FLIPPED[op], lhs))
    for part in text.split("!=")[1:]:
        value = _number(part.strip().split(" ")[0].rstrip(".,;:"))
        if value is not None:
            found.append(Condition("!=", value))
    return found


def _parts(text: str) -> list[str]:
    """The clauses a function in pieces is written in: split at ";", a new line, LaTeX's
    row break, a sentence's end, and wherever a function is defined again ("f(x) = 2^x if
    x <= 1, and f(x) = 1 + 1/x if x > 1")."""
    parts: list[str] = []
    for part in re.split(r"[;\n]|\\\\|\.\s(?=[A-Z])", text):
        starts = [m.start() for m in _DEFINES.finditer(part)][1:]
        for start, end in zip([0, *starts], [*starts, len(part)], strict=True):
            parts.append(part[start:end])
    return parts


def _clauses(text: str) -> list[Clause]:
    clauses: list[Clause] = []
    for part in _parts(text):
        points = [
            (a, b)
            for a, b in ((_number(x), _number(y)) for x, y in _POINT_VALUE.findall(part))
            if a is not None and b is not None
        ]
        formulas = tuple(w.expr for w in _formulas(part) if w.name != "x")
        clauses.append(Clause(formulas, tuple(_conditions(part)), tuple(points)))
    return clauses


def _x_values(text: str, variables: frozenset[str] = frozenset("x")) -> list[Any]:
    """The values the question gives x: in a comparison or an equation of x, an interval
    in brackets or in words, and 0 where it names the y-axis as an edge."""
    values = [c.value for c in _conditions(text, variables) if c.value.is_number]
    for low, high in [*_INTERVAL.findall(text), *_FROM_TO.findall(text)]:
        values += [v for v in (_number(low), _number(high)) if v is not None]
    if "y-axis" in text.lower():
        values.append(Rational(0))
    return values


def _values(original: str) -> list[Any]:
    """The values ``original`` writes outside its formulas, with their signs: the 2 of x²
    is no value."""
    values: list[Any] = [
        Rational(n.value.numerator, n.value.denominator)
        for n in written_numbers(original)
        if not n.in_formula
    ]
    return values + _x_values(plain(original))


def _named(pattern: re.Pattern[str], text: str) -> list[Any]:
    found = [
        _number(group) for match in pattern.finditer(text) for group in match.groups() if group
    ]
    return [value for value in found if value is not None]


def read_plot_question(texts: Sequence[str]) -> PlotQuestion:
    """What ``texts`` (the last user message first) state for a graph: the last message's,
    or the earlier ones' when it writes no formula ("now draw it")."""
    own = list(texts[:1]) if texts and _formulas(plain(texts[0])) else list(texts)
    readable = [plain(text) for text in own]
    formulas = tuple(w for text in readable for w in _formulas(text))
    # The letter the question's functions are written in ("v(t) = ...": t) is its x.
    letters = frozenset(
        {"x"} | {str(s) for w in formulas if w.name != "x" for s in w.expr.free_symbols}
    )
    return PlotQuestion(
        formulas=formulas,
        values=tuple(v for text in own for v in _values(text)),
        x_values=tuple(v for text in readable for v in _x_values(text, letters)),
        slopes=tuple(v for text in readable for v in _named(_SLOPE, text)),
        counts=tuple(
            int(v) for text in readable for v in _named(_COUNT, text) if v.is_Integer and v > 0
        ),
        pairs=frozenset(pair for text in own for pair in written_pairs(text)),
        clauses=tuple(clause for text in readable for clause in _clauses(text)),
        words=" ".join(readable).lower(),
    )
