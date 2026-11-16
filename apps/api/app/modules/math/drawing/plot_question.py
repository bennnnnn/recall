"""What a question states that a graph may draw: its formulas, its values and its pieces.

A curve is drawn only from a formula the question writes ("f(x) = x²|9 - x²|/(3 - x)",
"x = 9 - 2y²", "the line y = 3"), compared with SymPy, never from one the reply worked out
(a salary's pieces written only in words draw nothing). A bound, a point of contact or the
end of an interval is a value the question says of x (``plot_x``) unless the server finds
it (``plot_check``). A function defined in pieces is held clause by clause: each piece's
formula and its condition ("-5 < x <= -2") are written together, so a piece never takes a
neighbour's formula or an end it does not have; a formula written with its own domain
("defined for 0 ≤ x ≤ 3", "for t ≥ 0") is drawn on it.

The question is read in a plain spelling first (``plot_reading.plain``), so x⁵, eˣ, √x and
|x² - 1| read as they are written.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sympy import Expr, Rational, Symbol

from app.modules.math.drawing.plot_reading import (
    Condition,
    conditions,
    number,
    parts,
    plain,
)
from app.modules.math.drawing.plot_x import Interval, intervals, named_values, revolution_axis
from app.modules.math.figure.grounding import written_numbers, written_pairs
from app.modules.math.match.numerical_methods import (
    interval_counts,
    named_numerical_method,
    sums_named,
)
from app.modules.math.solve.parse import parse_expression
from app.modules.math.tool_check import (
    parse_formula,
    same_value,
    written_expressions,
    written_relations,
)
from app.services.solving import SolveServiceError

# Where a formula written after "=" ends: a clause's punctuation or a word of English.
_ENDS = frozenset(
    "if for when on from and is at which that has where with between to in then over about "
    "find show sketch draw defined only".split()
)
# "f(1) = 5": a value the question gives a function at a point.
_POINT_VALUE = re.compile(r"\b[a-z]\(\s*([-+]?[\w./]{1,12})\s*\)\s*=\s*([-+]?[\w./]{1,12})")
_NUMBER = r"([-+]?\d+(?:\.\d+)?(?:/\d+)?)"
_SLOPE = re.compile(r"\b(?:slope|gradient)\s(?:of\s|is\s|=\s?)?" + _NUMBER)
# A line a tangent is parallel to, or a line the question says is tangent ("the line
# y = -8x + k is tangent to the curve"): its slope is one the question states.
_TANGENT_SLOPES = re.compile(
    r"\bparallel\s+to\s+(?:the\s+line\s+)?y\s?=\s?([^,;]{1,30}?)(?=[,;.]|\s+(?:and|at)\b|$)"
    r"|\bline\s+y\s?=\s?([^,;]{1,30}?)\s+is\s+(?:a\s+)?tangent\b"
)
# "f(x)" names a function of its variable; "f(2)" its value at a point.
_DEFINES_NAME = re.compile(r"[a-zA-Z]\(\s?[a-z]\s?\)")
_AT_A_POINT = re.compile(r"[a-zA-Z]\([^a-zA-Z)]{1,12}\)")
_WIDTH = re.compile(
    r"(?:\bwidths?|\u0394\s?x|\bdelta\s?x|\bh)\s?(?:of\s|=\s?|is\s)?" + _NUMBER + r"(?![/\w])"
)
_ANTIDERIVATIVES = re.compile(
    r"\banti-?derivatives?\b|\bprimitives?\b|\bindefinite\s+integrals?\b|\bfamil(?:y|ies)\b"
)


@dataclass(frozen=True)
class Written:
    """A formula the question writes: what it names ("y", "x", "f") and its right side."""

    name: str
    expr: Any
    # Named y, or a function of the variable ("f(x) ="): a number it equals is a level line.
    # "a = 3", "A = 9" and "f(2) = 4" name values, never a curve.
    defines: bool = False
    # The formula as written, unsimplified: e^(ln x) and (√x)² have no value below 0, and
    # x/x none at 0, though SymPy reads each as x or 1 (``plot_pieces.formula_shape``).
    raw: Any = None


@dataclass(frozen=True)
class Clause:
    formulas: tuple[Any, ...]
    conditions: tuple[Condition, ...]
    # "f(1) = 5": (1, 5).
    point_values: tuple[tuple[Any, Any], ...]


@dataclass(frozen=True)
class PlotQuestion:
    formulas: tuple[Written, ...]
    # Every value written outside a formula ("a slope of -3", "5 subintervals").
    values: tuple[Any, ...]
    # A value the question names a slope ("a slope of -3", "gradient 2", "parallel to
    # y = 2x + 1"), and a count of rectangles ("5 subintervals", "n = 4"): a number
    # elsewhere ("the area is 9") is neither.
    slopes: tuple[Any, ...]
    counts: tuple[int, ...]
    pairs: frozenset[tuple[Any, Any]]
    clauses: tuple[Clause, ...]
    words: str
    # The intervals it says of x, the lines it names (x = -1/2, x ≥ 0, the y-axis; y = 3)
    # and the points it is said of ("at x = 3", "where y = 4") (``plot_x``).
    intervals: tuple[Interval, ...] = ()
    edges: tuple[Any, ...] = ()
    x_points: tuple[Any, ...] = ()
    y_points: tuple[Any, ...] = ()
    # The axis a region turns about, read after "about" or "around": ("y", 0) the x-axis,
    # ("x", 0) the y-axis, ("y", -1) the line y = -1.
    revolution_axis: tuple[str, Any] | None = None
    # A rectangle's width the question gives ("of width 0.5", "Δx = 0.5"), the numerical
    # rule it names (``match.numerical_methods``), and whether it asks for antiderivatives.
    width: Any | None = None
    rule: str | None = None
    sums: frozenset[str] = frozenset()
    antiderivatives: bool = False

    @property
    def x_values(self) -> tuple[Any, ...]:
        """Every value it says of x: its intervals' ends, its lines and its points."""
        ends = [end for interval in self.intervals for end in (interval.low, interval.high)]
        return (*ends, *self.edges, *self.x_points, *(x for x, _y in self.pairs))

    def domain_of(self, expr: Any) -> tuple[Condition, ...] | None:
        """The conditions the question writes ``expr`` with in one clause ("defined for
        0 ≤ x ≤ 3", "for t ≥ 0", one piece's "if x < 1"): its domain, when that is the only
        clause that writes it and every bound is a number."""
        found = [
            tuple(c for c in clause.conditions if c.op != "=")
            for clause in self.clauses
            if any(same_value(f, expr) for f in clause.formulas)
        ]
        # "x = 0" in its clause is a value it is said at, no domain.
        found = [conditions for conditions in found if conditions]
        if len(found) != 1 or not all(c.value.is_number for c in found[0]):
            return None
        return found[0]


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
        if _AT_A_POINT.fullmatch(name) or not (name.isalpha() or _DEFINES_NAME.fullmatch(name)):
            continue  # "f(2) = 4" is a value at a point; "f'(x) =" a derivative, not f
        parsed = parse_formula(_without_unit(formula))
        if isinstance(parsed, Expr):
            defines = name == "y" or _DEFINES_NAME.fullmatch(name) is not None
            found.append(Written(name[0], parsed, defines, _as_written(formula, parsed)))
    for lhs, op, rhs in written_relations(text):
        if op == "=" and isinstance(lhs, Symbol):
            found.append(Written(str(lhs), rhs, str(lhs) == "y"))
        elif op == "=" and lhs.is_Mul and len(lhs.free_symbols) == 2:
            found.append(Written(str(min(lhs.free_symbols, key=str)), rhs))
    found += [Written("", expr) for expr in written_expressions(text)]
    return found


def _as_written(formula: str, parsed: Any) -> Any | None:
    """``formula`` read as it is written, SymPy's simplifications left undone."""
    letters = sorted(str(symbol) for symbol in parsed.free_symbols)
    try:
        raw = parse_expression(_without_unit(formula), letters, evaluate=False)
    except (SolveServiceError, SyntaxError, TypeError, ValueError, AttributeError):
        return None
    return raw if isinstance(raw, Expr) else None


def _clauses(text: str, letters: frozenset[str]) -> list[Clause]:
    clauses: list[Clause] = []
    for part in parts(text):
        points = [
            (a, b)
            for a, b in ((number(x), number(y)) for x, y in _POINT_VALUE.findall(part))
            if a is not None and b is not None
        ]
        formulas = tuple(w.expr for w in _formulas(part) if w.name != "x")
        clauses.append(Clause(formulas, tuple(conditions(part, letters)), tuple(points)))
    return clauses


def _values(original: str) -> list[Any]:
    """The values ``original`` writes outside its formulas, with their signs: the 2 of x²
    is no value."""
    values: list[Any] = [
        Rational(n.value.numerator, n.value.denominator)
        for n in written_numbers(original)
        if not n.in_formula
    ]
    return values


def _named(pattern: re.Pattern[str], text: str) -> list[Any]:
    found = [number(group) for match in pattern.finditer(text) for group in match.groups() if group]
    return [value for value in found if value is not None]


def _parallel_slopes(text: str) -> list[Any]:
    """The slope of a line the question says a tangent is parallel to, or says is tangent:
    never any linear formula it writes."""
    found: list[Any] = []
    for match in _TANGENT_SLOPES.finditer(text):
        line = parse_formula((match.group(1) or match.group(2)).strip().rstrip("."))
        if isinstance(line, Expr):
            slope = line.diff(Symbol("x"))
            if slope.is_number and slope.is_real:
                found.append(slope)
    return found


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
    xs = [named_values(text, "x", letters) for text in readable]
    ys = [named_values(text, "y", letters) for text in readable]
    return PlotQuestion(
        formulas=formulas,
        values=tuple(v for text in own for v in _values(text)),
        slopes=tuple(
            v for text in readable for v in [*_named(_SLOPE, text), *_parallel_slopes(text)]
        ),
        counts=tuple(n for text in readable for n in interval_counts(text) if n > 0),
        pairs=frozenset(pair for text in own for pair in written_pairs(text)),
        clauses=tuple(clause for text in readable for clause in _clauses(text, letters)),
        words=" ".join(readable).lower(),
        intervals=tuple(i for text in readable for i in intervals(text, letters)),
        edges=tuple(v for lines, _points in xs for v in lines),
        x_points=tuple(v for _lines, points in xs for v in points),
        y_points=tuple(v for lines, points in ys for v in points if v not in lines),
        revolution_axis=next(
            (axis for text in readable if (axis := revolution_axis(text)) is not None), None
        ),
        width=next(iter(v for text in readable for v in _named(_WIDTH, text)), None),
        rule=next((named.rule for text in own if (named := named_numerical_method(text))), None),
        sums=frozenset(side for text in own for side in sums_named(text)),
        antiderivatives=any(_ANTIDERIVATIVES.search(text.lower()) for text in readable),
    )
