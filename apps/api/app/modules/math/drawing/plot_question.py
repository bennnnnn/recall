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
from app.modules.math.match.numerical_methods import interval_counts, named_numerical_method
from app.modules.math.solve.latex_normalize import rewrite_abs_bars
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
    r"\b(?:from|between)\s(?:[a-z]\s?=\s?)?([-+]?[\w./()*^]{1,12})\s(?:to|and)\s(?:[a-z]\s?=\s?)?([-+]?[\w./()*^]{1,12})"
)
_NUMBER = r"([-+]?\d+(?:\.\d+)?(?:/\d+)?)"
_SLOPE = re.compile(r"\b(?:slope|gradient)\s(?:of\s|is\s|=\s?)?" + _NUMBER)
# "f(x)" names a function of its variable; "f(2)" its value at a point.
_DEFINES_NAME = re.compile(r"[a-zA-Z]\(\s?[a-z]\s?\)")
_AT_A_POINT = re.compile(r"[a-zA-Z]\([^a-zA-Z)]{1,12}\)")
# A differential after an integrand: the "dx" of "∫ sin x dx".
_DIFFERENTIAL = re.compile(r"(?<=\S)\s+d[a-z](?![\w/])")
_COMPARISONS = ("<=", ">=", "!=", "<", ">", "=")
_LOWER_OR_UPPER = frozenset({"<", "<=", ">", ">="})
_OPERATORS = str.maketrans(OPERATOR_GLYPHS)
_FLIPPED = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "=": "=", "!=": "!="}


def plain(text: str) -> str:
    """``text`` in the spelling the formula reader reads: the solver's own rewrites of
    operators, superscripts and roots (``solve.unicode_normalize``), |…| as Abs(…) as the
    solver reads it (``solve.latex_normalize``), and no differential after an integrand."""
    out = text.translate(_OPERATORS)
    for glyph, written in _READER_GLYPHS.items():
        out = out.replace(glyph, written)
    out = rewrite_unicode_sqrts(rewrite_unicode_script_runs(out))
    return _DIFFERENTIAL.sub("", rewrite_abs_bars(out))


@dataclass(frozen=True)
class Written:
    """A formula the question writes: what it names ("y", "x", "f") and its right side."""

    name: str
    expr: Any
    # Named y, or a function of the variable ("f(x) ="): a number it equals is a level line.
    # "a = 3", "A = 9" and "f(2) = 4" name values, never a curve.
    defines: bool = False


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
    # The intervals of x it writes ("[0, 3]", "from x = 0 to x = 2", "0 ≤ x ≤ 2"), and the
    # single values that edge a region ("the lines x = -1/2 and x = 3", "x ≥ 0", the
    # y-axis): what an area, rectangles or an average may stand between. "The gradient at
    # x = 3" and "between 2 and 3" said of an answer edge nothing.
    intervals: tuple[tuple[Any, Any], ...] = ()
    edges: tuple[Any, ...] = ()
    # The axis a region turns about, read after "about" or "around": ("y", 0) the x-axis,
    # ("x", 0) the y-axis, ("y", -1) the line y = -1.
    revolution_axis: tuple[str, Any] | None = None
    # A rectangle's width the question gives ("of width 0.5", "Δx = 0.5"), the numerical
    # rule it names (``match.numerical_methods``), and whether it asks for antiderivatives.
    width: Any | None = None
    rule: str | None = None
    antiderivatives: bool = False


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
        if _AT_A_POINT.fullmatch(name):
            continue  # "f(2) = 4": the value at a point, no formula
        parsed = parse_formula(_without_unit(formula))
        if isinstance(parsed, Expr):
            defines = name == "y" or _DEFINES_NAME.fullmatch(name) is not None
            found.append(Written(name[0], parsed, defines))
    for lhs, op, rhs in written_relations(text):
        if op == "=" and isinstance(lhs, Symbol):
            found.append(Written(str(lhs), rhs, str(lhs) == "y"))
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


# "x = 2" names an edge ("bounded by ... and x = 2", "the lines x = -1/2 and x = 3"); after
# these words it names a point of x ("the gradient at x = 3", "f(x) = 3 if x = -5").
_X_EQUALS = re.compile(r"\bx\s?=\s?([-+]?[\w./()*^]{1,12})")
_POINT_WORDS = frozenset("at when where whenever if for of point then".split())
_LINE_WORDS = frozenset("the line lines vertical".split())
_PIECE_WORDS = re.compile(r"\b(?:if|when|otherwise)\b")
_ABOUT = re.compile(r"\b(?:about|around)\s+", re.IGNORECASE)
_AXIS_LINE = re.compile(
    r"\s*(?:the\s+)?(?:(?P<axis>[xy])[-\s]?axis\b"
    r"|(?:line\s+)?(?P<name>[xy])\s?=\s?(?P<at>[-+]?[\w./()*^]{1,12}))",
    re.IGNORECASE,
)
_WIDTH = re.compile(
    r"(?:\bwidths?|\u0394\s?x|\bdelta\s?x|\bh)\s?(?:of\s|=\s?|is\s)?" + _NUMBER + r"(?![/\w])"
)
_ANTIDERIVATIVES = re.compile(
    r"\banti-?derivatives?\b|\bprimitives?\b|\bindefinite\s+integrals?\b|\bfamil(?:y|ies)\b"
)


def _edge_values(text: str, variables: frozenset[str]) -> list[Any]:
    """The single values ``text`` gives x that edge a region: an equation of x not said of a
    point, a one-sided condition outside a piece ("for x ≥ 0"), 0 for the y-axis."""
    edges: list[Any] = []
    for match in _X_EQUALS.finditer(text):
        before = [w for w in text[: match.start()].lower().split() if w not in _LINE_WORDS]
        if before and before[-1].strip(",;:") in _POINT_WORDS:
            continue
        number = _number(match.group(1).rstrip(".,;:)"))
        if number is not None:
            edges.append(number)
    for part in _parts(text):
        if _PIECE_WORDS.search(part.lower()):
            continue
        one_sided = [c for c in _conditions(part, variables) if c.op in _LOWER_OR_UPPER]
        if len(one_sided) == 1 and one_sided[0].value.is_number:
            edges.append(one_sided[0].value)
    if "y-axis" in text.lower():
        edges.append(Rational(0))
    return edges


def _intervals(text: str, variables: frozenset[str]) -> list[tuple[Any, Any]]:
    """The intervals of x ``text`` writes: in brackets, in words, and as a double comparison
    in one clause ("0 ≤ x ≤ 2π", "-5 < x ≤ -2")."""
    found: list[tuple[Any, Any]] = []
    for low, high in [*_INTERVAL.findall(text), *_FROM_TO.findall(text)]:
        ends = (_number(low.rstrip(".,;:")), _number(high.rstrip(".,;:")))
        if ends[0] is not None and ends[1] is not None and ends[0] != ends[1]:
            found.append((min(ends, key=float), max(ends, key=float)))
    for part in _parts(text):
        sided = [c for c in _conditions(part, variables) if c.value.is_number]
        lows = [c.value for c in sided if c.op in {">", ">="}]
        highs = [c.value for c in sided if c.op in {"<", "<="}]
        if len(lows) == 1 and len(highs) == 1 and float(lows[0]) < float(highs[0]):
            found.append((lows[0], highs[0]))
    return found


def axis_line(text: str) -> tuple[str, Any] | None:
    """The axis line ``text`` begins with: ("y", 0) for "the x-axis" or "y = 0", ("x", 0)
    for "the y-axis", ("y", -1) for "the line y = -1"."""
    found = _AXIS_LINE.match(text)
    if found is None:
        return None
    if found.group("axis"):
        return ("y" if found.group("axis").lower() == "x" else "x"), Rational(0)
    at = _number(found.group("at").rstrip(".,;:"))
    return None if at is None else (found.group("name").lower(), at)


def _revolution_axis(text: str) -> tuple[str, Any] | None:
    """The axis a region turns about: the line named right after "about" or "around"."""
    for found in _ABOUT.finditer(text):
        axis = axis_line(text[found.end() :])
        if axis is not None:
            return axis
    return None


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
        counts=tuple(n for text in readable for n in interval_counts(text) if n > 0),
        pairs=frozenset(pair for text in own for pair in written_pairs(text)),
        clauses=tuple(clause for text in readable for clause in _clauses(text)),
        words=" ".join(readable).lower(),
        intervals=tuple(pair for text in readable for pair in _intervals(text, letters)),
        edges=tuple(v for text in readable for v in _edge_values(text, letters)),
        revolution_axis=next(
            (axis for text in readable if (axis := _revolution_axis(text)) is not None), None
        ),
        width=next(iter(v for text in readable for v in _named(_WIDTH, text)), None),
        rule=next((named.rule for text in own if (named := named_numerical_method(text))), None),
        antiderivatives=any(_ANTIDERIVATIVES.search(text.lower()) for text in readable),
    )
