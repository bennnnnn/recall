"""A verified card in the form the reply's own working reaches.

SymPy writes its result in its own form. A reply that worked ∫ sec(2x - π/4) tan(2x - π/4) dx
to ½ sec(2x - π/4) + C carried a checked card of csc(2x + π/4)/2 + C, a form the working
never reaches; ln|1 - cos 2t|/2 + C stood over ln|2 cos 2t - 2|/2 + C, the same
antiderivative shifted by a constant (live round, Grade 12 unit 5, 2026-11-16). Both are
right, and a student reading the card cannot tell.

One rule, for antiderivatives only (a card ending ``+ C``), where a different form is a
different right answer, not unfinished work: the card shows the reply's own form when SymPy
finds it the same antiderivative (equal up to a constant where both are defined). The reply's
Answer line is read first; when it only copies the server's form, the working's last line.
A form that applies a function SymPy would still evaluate (ln 1, sin(π/4), arctan 1, √8,
e^(ln x)) is unfinished and never shown. Every other card (a definite value, a factorisation,
an expansion, a simplification, partial fractions) keeps the server's form: there the form
is the answer, and an equal value written otherwise (x² - 5x + 6 for (x - 2)(x - 3)) answers
nothing (review of 2026-11-16).
"""

from __future__ import annotations

import cmath
import logging
import math
import re
from typing import Any

from app.modules.math.fence_answer import same_spelling
from app.modules.math.solve.latex_normalize import rewrite_abs_bars
from app.modules.math.tool_check import parse_latex_formula
from app.services.answer_fence import answer_fence_value, stated_answers
from app.services.card_text import card_maths, whole_maths
from app.services.latex_groups import map_groups

logger = logging.getLogger(__name__)

# A card of one expression: no relation, list, words or several branches.
_NOT_ONE_EXPRESSION = re.compile(r"=|,|;|\\(?:text|mathrm|quad|pm|mp|approx|begin|cup)\b|\n|≈")
_CONSTANT = re.compile(r"\s*\+\s*C\s*$")
_DECIMAL = re.compile(r"\d\.\d")
# A script TeX reads as one character, written as more: "x^12" is x^1 times 2, "x^-1".
_LOOSE_SCRIPT = re.compile(r"[\^_](?:-|\d{2})")
_STYLE = re.compile(r"\\(?:displaystyle|textstyle)\s*")
# Commands that only size or space what they stand by.
_SIZING = re.compile(r"\\(?:left|right|[bB]igg?[lr]?|displaystyle|textstyle)(?![A-Za-z])")
_SPACING = re.compile(r"\\[,;:! ]|\\q?quad(?![A-Za-z])")
_FRACTION = re.compile(r"\\[dt]frac(?![A-Za-z])")
# A bare \log in an antiderivative is the natural log, as SymPy writes it and calculus
# texts mean it: ∫1/x dx = \log|x| + C (Gemini on #2481). \log_{10} keeps its base.
_BARE_LOG = re.compile(r"\\log(?![A-Za-z_])")
# A function's argument in braces, SymPy's own spelling: \csc{\left(2 x\right)}, \cos^{3}{(x)}.
_BRACED_ARGUMENT = re.compile(
    r"\\(sinh|cosh|tanh|sin|cos|tan|sec|csc|cot|ln|log|exp)(\^\{?-?\d+\}?)?\s*\{"
)
# Irrational, unevenly spaced and not symmetric about 0: no polynomial or trig term a
# reply might add (sin(πx), x(x - 1)) vanishes at all of them.
_SAMPLES = tuple(
    math.sqrt(2) * k + math.e / (k + 3) for k in (-3.1, -1.7, -0.6, 0.2, 0.9, 1.4, 2.3, 3.6)
)
# A derivative this large is left to the samples: simplify may outrun the fence's budget.
_MAX_PROOF_OPS = 80
_MIN_SAMPLES = 4


def read_tex(tex: str, *, evaluate: bool = True) -> Any | None:
    """``tex`` as one SymPy expression, read the way the solver reads typed LaTeX, with the
    spellings SymPy itself writes (a function's braced argument, |…| after ln); None when
    it does not read."""
    text = _FRACTION.sub(r"\\frac", _SPACING.sub(" ", _SIZING.sub("", tex.replace("$", ""))))
    text = _BARE_LOG.sub(r"\\ln", text)
    for _ in range(4):
        unbraced = map_groups(
            text,
            _BRACED_ARGUMENT,
            lambda outside: outside,
            lambda opened, inside: f"\\{opened.group(1)}{opened.group(2) or ''}({inside})",
        )
        if unbraced == text:
            break
        text = unbraced
    return parse_latex_formula(rewrite_abs_bars(text, apart=True), evaluate=evaluate)


def _value(expr: Any, point: dict[Any, float]) -> complex | None:
    try:
        value = complex(expr.evalf(subs=point))
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    return value if cmath.isfinite(value) else None


def _real(value: complex | None) -> float | None:
    if value is None or abs(value.imag) > 1e-9 * max(1.0, abs(value.real)):
        return None
    return value.real


def same_value(
    server: Any, stated: Any, *, up_to_constant: bool, points: tuple[float, ...] = ()
) -> bool:
    """``stated`` is ``server``: equal where both are real, or with ``up_to_constant`` apart
    by one constant; real at the same sample points (and at ``points``, for one variable),
    and at enough of them."""
    symbols = sorted(server.free_symbols, key=str)
    if set(symbols) != stated.free_symbols:
        return False
    gaps: list[float] = []
    sizes: list[float] = []
    samples = (*_SAMPLES, *points) if len(symbols) == 1 else _SAMPLES
    for sample in samples if symbols else _SAMPLES[:1]:
        point = {symbol: sample + 0.13 * number for number, symbol in enumerate(symbols)}
        mine, theirs = _real(_value(server, point)), _real(_value(stated, point))
        if (mine is None) != (theirs is None):
            return False
        if mine is None or theirs is None:
            continue
        gaps.append(mine - theirs)
        sizes.append(max(1.0, abs(mine)))
    if not gaps or (symbols and len(gaps) < _MIN_SAMPLES):
        return False
    base = gaps[0] if up_to_constant else 0.0
    pairs = zip(gaps, sizes, strict=True)
    return all(math.isclose(gap, base, abs_tol=1e-9 * size) for gap, size in pairs)


def _right_side(value: str) -> str | None:
    """What a stated line of maths gives: after its last ``=`` ("∫ … dx = ½ sec(…) + C").
    None for a sentence ("At $x = 1$: $…$"): only a line that is all maths states a value."""
    plain = value.strip().rstrip(".").strip()
    inside = whole_maths(plain)
    if inside is not None:
        plain = inside  # $…$, $$…$$, \(…\) or \[…\] (Gemini on #2481)
    elif "$" in plain or "\\(" in plain or "\\[" in plain:
        return None
    side = plain.rsplit("=", 1)[-1]
    return _STYLE.sub("", side).strip().rstrip(".").strip()


def in_working_form(reply: str, answer_body: str, *, antiderivative: bool) -> str:
    """``answer_body``, or the antiderivative ``reply`` states in its place (the module's
    rule). ``antiderivative``: the verified block is an indefinite integral's, which only
    its operation says: a "+ C" of the user's own letter ("Expand A(A + 2) + C") is no
    constant of integration. Runs in the SymPy pool, as the fence pass does."""
    value = answer_fence_value(answer_body)
    if not antiderivative or not value or not _CONSTANT.search(value):
        return answer_body
    if _NOT_ONE_EXPRESSION.search(_SPACING.sub(" ", value)) is not None:
        return answer_body
    server = read_tex(_CONSTANT.sub("", value))
    if server is None or "C" in {str(symbol) for symbol in server.free_symbols}:
        return answer_body  # C is one of the question's own letters
    answer, working = stated_answers(reply)
    for stated in (answer, working):
        shown = _right_side(stated) if stated else None
        if not shown:
            continue
        if not _CONSTANT.search(shown):
            shown += " + C"  # a line before its constant is written: the card writes it
        if _copies(shown, value, server):
            continue  # the Answer copies the server's form: the working says it the reply's way
        return card_maths(shown) if _same_antiderivative(shown, server) else answer_body
    return answer_body


def _as_written(shown: str) -> Any | None:
    """``shown`` read without SymPy evaluating it."""
    return read_tex(_CONSTANT.sub("", shown), evaluate=False)


def _copies(shown: str, value: str, server: Any) -> bool:
    """``shown`` is the server's own form, however it is spaced or bracketed."""
    if same_spelling(shown, value):
        return True
    mine, theirs = _as_written(shown), read_tex(_CONSTANT.sub("", value), evaluate=False)
    return mine is not None and theirs is not None and mine == theirs


def _same_antiderivative(shown: str, server: Any) -> bool:
    """``shown`` is ``server`` up to a constant, written as a finished answer."""
    if _NOT_ONE_EXPRESSION.search(_SPACING.sub(" ", shown)) or "\\int" in shown:
        return False
    if _DECIMAL.search(shown) or _LOOSE_SCRIPT.search(shown):
        return False  # a rounded coefficient, or a script TeX reads otherwise
    mine = read_tex(_CONSTANT.sub("", shown))
    written = _as_written(shown)
    if mine is None or written is None:
        return False
    if _unevaluated(written) or _uncombined(written) or _loose_constant(written):
        return False
    if len(server.free_symbols) != 1:
        return False  # where a form of several letters is real is not sampled: unsure
    try:
        if _proved_constant_apart(server, mine) is False:
            return False
        # A zero derivative is not enough: -arctan(1/x) jumps at 0 where arctan(x) does
        # not, and ln(6 - x) is not real past 6 where ln|x - 6| is (Gemini on #2481). The
        # stated form is held to the server's on both sides of every point where a log,
        # |…|, root or denominator of either changes.
        points = _either_side(_critical_points((server, mine)))
        if points is None:
            return False
        return same_value(server, mine, up_to_constant=True, points=points)
    except Exception:
        logger.info("the working's form was not compared; the card keeps SymPy's", exc_info=True)
        return False


def _proved_constant_apart(server: Any, mine: Any) -> bool | None:
    """True when SymPy proves ``mine`` and ``server`` a constant apart (their difference
    simplifies to a zero derivative); False when they are not in the same variables; None
    when simplify cannot tell (|…| and logs often leave a sign it cannot settle), and the
    samples decide."""
    from sympy import count_ops, diff, simplify

    if server.free_symbols != mine.free_symbols:
        return False
    slopes = [diff(mine - server, symbol) for symbol in sorted(server.free_symbols, key=str)]
    if any(count_ops(slope) > _MAX_PROOF_OPS for slope in slopes):
        return None
    left = [simplify(slope) for slope in slopes]
    if all(slope == 0 for slope in left):
        return True
    return None


_MAX_CRITICAL = 24
# A periodic set of places (the zeros of sin x) is read in this window: the form repeats.
_WINDOW = 20


def _critical_points(exprs: tuple[Any, ...]) -> list[float] | None:
    """Where an argument of a log, |…|, root or inverse tangent, or a denominator, of
    ``exprs`` is zero, wherever it lies (∫1/(x - 25) dx stated as ln(x - 25): Gemini on
    #2481); a periodic set within ±20. None when SymPy cannot list them (the card keeps
    the server's form)."""
    from sympy import (
        Abs,
        FiniteSet,
        Interval,
        Pow,
        S,
        acot,
        atan,
        log,
        preorder_traversal,
        solveset,
    )

    symbol = next(iter(exprs[0].free_symbols))
    places: set[Any] = set()
    for expr in exprs:
        for node in preorder_traversal(expr):
            if isinstance(node, (log, Abs, atan, acot)):
                places.add(node.args[0])
            elif isinstance(node, Pow) and node.free_symbols:
                # A denominator, or a root: where its base is zero the form may change.
                if not node.exp.is_positive or not node.exp.is_Integer:
                    places.add(node.base)
    found: list[float] = []
    for place in places:
        if symbol not in place.free_symbols:
            continue
        zeros = solveset(place, symbol, domain=S.Reals)
        if not isinstance(zeros, FiniteSet):
            zeros = zeros.intersect(Interval(-_WINDOW, _WINDOW))
        if zeros is S.EmptySet:
            continue
        if not isinstance(zeros, FiniteSet) or len(zeros) > _MAX_CRITICAL:
            return None
        found += [float(zero) for zero in zeros if zero.is_real]
    return found


def _either_side(points: list[float] | None) -> tuple[float, ...] | None:
    if points is None:
        return None
    sides: list[float] = []
    for point in points:
        step = 1e-3 * max(1.0, abs(point))
        sides += [point - step, point + step, point - 0.37 * max(1.0, abs(point)), point + 0.41]
    return tuple(sides)


def _loose_constant(expr: Any) -> bool:
    """A constant term beside the + C ("x³/3 + 5 + C"): the constant is C's to carry."""
    from sympy import Add

    return isinstance(expr, Add) and any(not term.free_symbols for term in expr.args)


def _uncombined(expr: Any) -> bool:
    """``expr``, as written, holds numbers still to combine: a sum of numbers
    (``x^{3+1}``), or a product with more than one number, or a fraction not in lowest
    terms (``4·x⁴/4``, ``\\frac{2}{4}x^2``): a working step, never the card's answer
    (Gemini on #2481). ``\\frac{3x^2}{2}`` and ``-\\frac{1}{2}\\cos 2x`` are finished."""
    from math import gcd

    from sympy import Add, Integer, Mul, Pow, preorder_traversal

    def factors(node: Any) -> list[Any]:
        if isinstance(node, Mul):
            return [part for arg in node.args for part in factors(arg)]
        return [node]

    for node in preorder_traversal(expr):
        if isinstance(node, Add) and not node.free_symbols:
            return True
        if not isinstance(node, Mul):
            continue
        parts = factors(node)
        tops = [abs(int(part)) for part in parts if isinstance(part, Integer) and abs(part) != 1]
        bottoms = [
            int(part.base)
            for part in parts
            if isinstance(part, Pow) and isinstance(part.base, Integer) and part.exp == -1
        ]
        if len(tops) > 1 or len(bottoms) > 1:
            return True
        if tops and bottoms and gcd(tops[0], bottoms[0]) != 1:
            return True
    return False


def _unevaluated(expr: Any) -> bool:
    """``expr``, as written, holds a step SymPy would still take: a function or root of a
    number that has a value of its own (ln 1 is 0, sin(π/4) is √2/2, arctan 1 is π/4, √8 is
    2√2), or a function undone by the one inside it (e^(ln x) is x). ln 2, √2 and a trig
    function SymPy only shifts (sec(2x - π/4) is csc(2x + π/4)) are finished forms."""
    from sympy import Function, Pow, preorder_traversal

    def applied(node: Any) -> int:
        return sum(isinstance(part, Function) for part in preorder_traversal(node))

    for node in preorder_traversal(expr):
        if isinstance(node, Function):
            done = node.func(*(arg.doit() for arg in node.args))
            if node.free_symbols:
                if applied(done) < applied(node):
                    return True
            elif not isinstance(done, node.func):
                return True
        elif isinstance(node, Pow) and not node.exp.is_Integer:
            base, power = node.base.doit(), node.exp.doit()
            done = Pow(base, power)
            if node.free_symbols:
                if applied(done) < applied(node):
                    return True  # e^(ln x)
            elif done != Pow(base, power, evaluate=False):
                return True
    return False
