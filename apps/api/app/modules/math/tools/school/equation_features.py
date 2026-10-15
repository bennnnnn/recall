"""A feature of one stated equation: vertex, intercepts, discriminant, roots, lines.

"find the vertex of y = x^2 - 6x + 5" used to be solved for x, and the
verified card read ``x = 3 - sqrt(y + 4) or ...``. The same happened to the
y-intercept, the axis of symmetry, the discriminant, the sum of the roots,
"find k so that ... has exactly one solution", and the line through a point
parallel to another. Each rule here reads one asked feature and the one
equation it is about, and the whole request has to be read: anything left
over, a second feature, or an equation of the wrong shape verifies nothing,
and the model answers. ``request_consumption`` refuses the equation solver
for the same words, so a declined feature never falls through to "solve".
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.modules.math.schemas import MathIntent
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.services.workout import Workout, math_line, render_workout

FEATURE_OPS = frozenset(
    {
        "equation_vertex",
        "equation_axis",
        "equation_y_intercept",
        "equation_x_intercepts",
        "equation_discriminant",
        "equation_root_sum",
        "equation_root_product",
        "equation_slope",
        "equation_slope_intercept",
        "equation_line_through",
        "equation_parameter",
        "equation_period",
        "equation_amplitude",
        "equation_solution_count",
    }
)

_FEATURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "slope_intercept",
        re.compile(r"\bslope[\s-]+intercept(?:\s+form)?\b", re.I),
    ),
    ("vertex", re.compile(r"\b(?:the\s+)?(?:vertex|turning\s+point)\b", re.I)),
    ("axis", re.compile(r"\b(?:the\s+)?(?:axis|line)\s+of\s+symmetry\b", re.I)),
    ("y_intercept", re.compile(r"\b(?:the\s+)?y[\s-]?intercepts?\b", re.I)),
    ("x_intercepts", re.compile(r"\b(?:the\s+)?x[\s-]?intercepts?\b", re.I)),
    ("discriminant", re.compile(r"\b(?:the\s+)?discriminant\b", re.I)),
    (
        "root_sum",
        re.compile(r"\bsum\s+of\s+(?:the\s+|its\s+)?(?:roots|zeros|zeroes|solutions)\b", re.I),
    ),
    (
        "root_product",
        re.compile(r"\bproduct\s+of\s+(?:the\s+|its\s+)?(?:roots|zeros|zeroes|solutions)\b", re.I),
    ),
    ("line_through", re.compile(r"\b(?P<relation>parallel|perpendicular)\s+to\b", re.I)),
    ("slope", re.compile(r"\b(?:the\s+)?(?:slope|gradient)\b", re.I)),
    ("period", re.compile(r"\b(?:the\s+)?period\b", re.I)),
    ("amplitude", re.compile(r"\b(?:the\s+)?amplitude\b", re.I)),
    # "how many real roots does x^2 + 2x + 5 = 0 have"
    (
        "solution_count",
        re.compile(
            r"\bhow\s+many\s+(?P<real>real\s+)?(?:solutions?|roots?|zeros?|zeroes?)\s+"
            r"(?:does|do|will)\b",
            re.I,
        ),
    ),
)

# "find k so that x^2 + kx + 9 = 0 has exactly one solution".
_PARAMETER = re.compile(
    r"^(?:find|determine|calculate|work\s+out|what\s+(?:is|are|must|should))\s+"
    r"(?:the\s+(?:possible\s+)?values?\s+of\s+|all\s+(?:possible\s+)?values\s+of\s+)?"
    r"(?P<param>[a-z])(?:\s+(?:be|is))?\s*,?\s*"
    r"(?:so\s+that|such\s+that|if|for\s+which|given\s+that|when|where)\s+(?:the\s+equation\s+)?"
    r"(?P<equation>[^,;]+?)\s+(?:has|have)\s+"
    r"(?P<count>exactly\s+one|only\s+one|one|1|a\s+single|a\s+repeated|a\s+double|"
    r"two\s+equal|equal|repeated|two\s+distinct|2\s+distinct|two\s+different|two|2|no)"
    r"\s+(?:real\s+)?(?:solutions?|roots?|zeros?|zeroes?)(?:\s+in\s+x)?$",
    re.I,
)
_COUNT_RELATION = {
    "exactly one": "=",
    "only one": "=",
    "one": "=",
    "1": "=",
    "a single": "=",
    "a repeated": "=",
    "a double": "=",
    "two equal": "=",
    "equal": "=",
    "repeated": "=",
    "two distinct": ">",
    "2 distinct": ">",
    "two different": ">",
    "two": ">",
    "2": ">",
    "no": "<",
}
_POINT = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")
_NUMBERED_POINT = re.compile(r"\(\s*-?\d")
# Words that only frame the question. Anything else is part of the request
# that no rule here reads, so nothing is verified.
_FRAME_WORDS = frozenset(
    {
        "find",
        "the",
        "of",
        "what",
        "whats",
        "is",
        "are",
        "a",
        "an",
        "determine",
        "calculate",
        "compute",
        "give",
        "me",
        "please",
        "line",
        "parabola",
        "graph",
        "curve",
        "quadratic",
        "function",
        "equation",
        "its",
        "for",
        "coordinates",
        "coordinate",
        "point",
        "value",
        "work",
        "out",
        "state",
        "write",
        "to",
        "through",
        "passing",
        "passes",
        "that",
        "which",
        "goes",
        "going",
        "in",
        "form",
        "can",
        "you",
        "could",
        "tell",
        "get",
        "now",
        "and",
        "at",
        "containing",
        "have",
        "has",
    }
)


def extract_equation_feature_intent(cleaned: str) -> MathIntent | None:
    body = " ".join(cleaned.split()).strip().rstrip("?.!").strip()
    if not body or len(body) > 300 or ("=" not in body and not _no_equals_ok(body)):
        return None
    parameter = _PARAMETER.fullmatch(body)
    if parameter is not None:
        return _parameter_intent(parameter)
    found = [(op, match) for op, pattern in _FEATURES if (match := pattern.search(body))]
    ops = {op for op, _ in found}
    if "slope_intercept" in ops:
        ops -= {"slope", "y_intercept", "x_intercepts"}
    if "line_through" in ops:
        ops -= {"slope"}
    if len(ops) != 1:
        return None
    (op,) = ops
    match = next(match for name, match in found if name == op)
    if op in {"slope", "slope_intercept"} and len(_POINT.findall(body)) >= 2:
        # A slope between two points belongs to the coordinate rules.
        return None
    point: tuple[float, float] | None = None
    if op == "line_through":
        points = _POINT.findall(body)
        if len(points) != 1:
            return None
        point = (float(points[0][0]), float(points[0][1]))
    elif op in {"period", "amplitude"}:
        # "sin(2x)" opens a bracket with a digit; only a written point is extra.
        if _POINT.search(body):
            return None
    elif _NUMBERED_POINT.search(body):
        return None
    sides = _one_equation(body, op)
    if sides is None:
        return None
    lhs, rhs = sides
    if not _only_frame_words(body, match):
        return None
    return MathIntent(
        kind="arithmetic",
        school_op=f"equation_{op}",
        lhs=lhs,
        rhs=rhs,
        point_x=point[0] if point else None,
        point_y=point[1] if point else None,
        trial_outcome=(
            match.group("relation").lower()
            if op == "line_through"
            else ("real" if op == "solution_count" and match.group("real") else None)
        ),
        operation="solve",
    )


def _no_equals_ok(body: str) -> bool:
    """``discriminant of 3x^2 + 2x + 1`` names a quadratic with no ``= 0``."""
    lower = body.lower()
    return any(word in lower for word in ("discriminant", "sum of", "product of"))


def _one_equation(body: str, op: str) -> tuple[str, str] | None:
    from app.modules.math.solve.extract_eq import try_extract_equations_from_text
    from app.modules.math.tools.helpers import math_expr_or_none

    found = try_extract_equations_from_text(_without_point(body))
    pairs = {(lhs.strip(), rhs.strip()) for lhs, rhs in found}
    if len(pairs) == 1:
        lhs, rhs = next(iter(pairs))
        lhs = _after_last_of(lhs)
        rhs = _before_frame_words(rhs)
        if math_expr_or_none(lhs) is None or math_expr_or_none(rhs) is None:
            return None
        return lhs, rhs
    if pairs or op not in {"discriminant", "root_sum", "root_product"}:
        return None
    of_at = body.lower().rfind(" of ")
    if of_at == -1:
        return None
    expression = math_expr_or_none(body[of_at + 4 :])
    return (expression, "0") if expression is not None else None


def _without_point(body: str) -> str:
    return _POINT.sub(" ", body)


def _after_last_of(side: str) -> str:
    """``the vertex of y`` → ``y``: the extractor may keep words before the equation."""
    words = side.split()
    while words and words[0].lower() in _FRAME_WORDS | {"vertex", "parabola"}:
        words = words[1:]
    return " ".join(words) if words else side


def _before_frame_words(side: str) -> str:
    """``6 in`` (of "= 6 in slope-intercept form") → ``6``."""
    words = side.split()
    while len(words) > 1 and words[-1].lower() in _FRAME_WORDS:
        words = words[:-1]
    return " ".join(words)


def _only_frame_words(body: str, feature: re.Match[str]) -> bool:
    """Nothing but the feature, the equation, a point and framing words."""
    from app.modules.math.function_names import MATH_FUNCTION_NAMES

    rest = body[: feature.start()] + " " + body[feature.end() :]
    for token in rest.split():
        if re.search(r"[\d=^()+\-*/<>]", token):
            continue
        word = re.sub(r"[^a-z]", "", token.lower())
        if len(word) < 2:
            continue
        if word not in _FRAME_WORDS and word not in MATH_FUNCTION_NAMES:
            return False
    return True


def _parameter_intent(match: re.Match[str]) -> MathIntent | None:
    from app.modules.math.solve.extract_eq import try_extract_equations_from_text

    pairs = try_extract_equations_from_text(match["equation"])
    if len(pairs) != 1:
        return None
    lhs, rhs = pairs[0]
    count = " ".join(match["count"].lower().split())
    return MathIntent(
        kind="arithmetic",
        school_op="equation_parameter",
        lhs=lhs.strip(),
        rhs=rhs.strip(),
        variable=match["param"],
        comparator=_COUNT_RELATION[count],
        operation="solve",
    )


# --- the block -------------------------------------------------------------------------


def equation_feature_block(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    from sympy.polys.polyerrors import BasePolynomialError

    op = (intent.school_op or "").removeprefix("equation_")
    try:
        solved = _SOLVERS[op](intent)
    except (
        BasePolynomialError,
        KeyError,
        ValueError,
        TypeError,
        ZeroDivisionError,
        AttributeError,
    ):
        # Not a polynomial or a line of the expected shape: nothing to verify.
        return None
    if solved is None:
        return None
    workout, answer, record = solved
    lines.extend(record)
    block = _finish_with_answer(lines, answer)
    return replace(block, worked_reply=render_workout(workout, answer))


def _parse(text: str, names: list[str]) -> Any:
    from app.modules.math import solve as math_solve

    parsed = math_solve._parse_expression(text, names)
    if isinstance(parsed, tuple):
        raise ValueError("not one expression")
    from sympy import nsimplify

    return nsimplify(parsed, rational=True)


def _symbols(*names: str) -> tuple[Any, ...]:
    from sympy import Symbol

    return tuple(Symbol(name) for name in names)


def _by_name(expr: Any, name: str) -> Any:
    from sympy import Symbol

    return next((s for s in expr.free_symbols if str(s) == name), Symbol(name))


def _plain(expr: Any) -> Any:
    """The same expression over plain symbols, whatever assumptions the parser set."""
    from sympy import Symbol

    return expr.xreplace({s: Symbol(str(s)) for s in expr.free_symbols})


def _sides(intent: MathIntent, names: list[str]) -> tuple[Any, Any]:
    return _plain(_parse(intent.lhs or "", names)), _plain(_parse(intent.rhs or "", names))


_NAMED_LHS = re.compile(r"^\s*(?:y|[a-z]\s*\(\s*x\s*\))\s*$")


def _explicit(intent: MathIntent) -> Any | None:
    """``y = F(x)`` or ``f(x) = F(x)``: F, in x only."""
    lhs_text, rhs_text = intent.lhs or "", intent.rhs or ""
    if _NAMED_LHS.match(lhs_text):
        side = rhs_text
    elif _NAMED_LHS.match(rhs_text):
        side = lhs_text
    else:
        return None
    (x,) = _symbols("x")
    expr = _plain(_parse(side, ["x"]))
    return expr if expr.free_symbols <= {x} else None


def _linear(intent: MathIntent) -> tuple[Any, Any, Any] | None:
    """``ax + by = c`` (or ``y = mx + b``) as (a, b, c) with ax + by = c."""
    from sympy import Poly

    x, y = _symbols("x", "y")
    explicit = _explicit(intent)
    if explicit is not None:
        expression = y - explicit
    else:
        if re.search(r"[a-z]\s*\(", intent.lhs or "") or re.search(r"[a-z]\s*\(", intent.rhs or ""):
            return None
        lhs, rhs = _sides(intent, ["x", "y"])
        expression = lhs - rhs
    if not expression.free_symbols or not expression.free_symbols <= {x, y}:
        return None
    poly = Poly(expression, x, y)
    if poly.total_degree() != 1:
        return None
    a, b = poly.coeff_monomial(x), poly.coeff_monomial(y)
    c = -poly.coeff_monomial(1)
    return a, b, c


def _quadratic(intent: MathIntent, *, explicit_only: bool) -> tuple[Any, Any, Any, Any] | None:
    """(a, b, c, F) for ``y = ax^2 + bx + c``; unless ``explicit_only``, ``P(x) = Q(x)`` too."""
    from sympy import Poly

    (x,) = _symbols("x")
    expression = _explicit(intent)
    if expression is None:
        if explicit_only:
            return None
        lhs, rhs = _sides(intent, ["x"])
        expression = lhs - rhs
        if not expression.free_symbols <= {x}:
            return None
    if x not in expression.free_symbols:
        return None
    poly = Poly(expression, x)
    if poly.degree() != 2:
        return None
    a, b, c = poly.all_coeffs()
    return a, b, c, expression


def _tex(value: Any) -> str:
    from sympy import latex

    return str(latex(value))


def _num(value: Any) -> str:
    """``-\\frac{1}{2}`` (no space after the sign), ``3``, ``\\sqrt{2} - 1``."""
    tex = _tex(value)
    return "-" + tex[2:] if tex.startswith("- ") else tex


def _at(expression: Any, value: Any) -> str:
    """``x^2 - 6x + 5`` at 3 → ``\\left(3\\right)^{2} - 6 \\cdot 3 + 5``."""
    from sympy import sympify

    from app.modules.math.tools.school.function_value import _substituted_tex

    return _substituted_tex(expression, "x", sympify(value))


def _point(x_value: Any, y_value: Any) -> str:
    return rf"\left({_num(x_value)}, {_num(y_value)}\right)"


def _bracket(value: Any) -> str:
    tex = _num(value)
    return rf"\left({tex}\right)" if tex.startswith("-") else tex


def _line_tex(slope: Any, intercept: Any) -> str:
    from sympy import Rational

    if slope == 0:
        return f"y = {_num(intercept)}"
    if slope == 1:
        term = "x"
    elif slope == -1:
        term = "-x"
    else:
        term = f"{_num(slope)}x"
    if intercept == 0:
        return f"y = {term}"
    sign = "-" if intercept < Rational(0) else "+"
    return f"y = {term} {sign} {_num(abs(intercept))}"


_Solved = tuple[Workout, str, list[str]]


def _vertex(intent: MathIntent) -> _Solved | None:
    quadratic = _quadratic(intent, explicit_only=True)
    if quadratic is None:
        return None
    a, b, _c, expression = quadratic
    (x,) = _symbols("x")
    h = -b / (2 * a)
    k = expression.subs(x, h)
    answer = _point(h, k)
    workout = Workout(
        given=(math_line(f"y = {_tex(expression)}"),),
        find=(math_line(r"\left(h, k\right)", "vertex"),),
        formula=(math_line(r"h = -\frac{b}{2a}, \quad k = y(h)", "Vertex of a parabola"),),
        substitution=(
            math_line(rf"h = -\frac{{{_num(b)}}}{{2 \cdot {_bracket(a)}}} = {_num(h)}"),
            math_line(rf"k = {_at(expression, h)} = {_num(k)}", f"y at x = {_num(h)}"),
        ),
    )
    return workout, answer, [f"Vertex: ({h}, {k})"]


def _axis(intent: MathIntent) -> _Solved | None:
    quadratic = _quadratic(intent, explicit_only=True)
    if quadratic is None:
        return None
    a, b, _c, expression = quadratic
    h = -b / (2 * a)
    answer = f"x = {_num(h)}"
    workout = Workout(
        given=(math_line(f"y = {_tex(expression)}"),),
        find=(math_line("x = ?", "axis of symmetry"),),
        formula=(math_line(r"x = -\frac{b}{2a}", "Axis of symmetry"),),
        substitution=(math_line(rf"x = -\frac{{{_num(b)}}}{{2 \cdot {_bracket(a)}}} = {_num(h)}"),),
    )
    return workout, answer, [f"Axis of symmetry: x = {h}"]


def _y_intercept(intent: MathIntent) -> _Solved | None:
    (x,) = _symbols("x")
    explicit = _explicit(intent)
    if explicit is not None:
        value = explicit.subs(x, 0)
        given = f"y = {_tex(explicit)}"
        working = rf"y = {_at(explicit, 0)} = {_num(value)}"
    else:
        line = _linear(intent)
        if line is None:
            return None
        a, b, c = line
        if b == 0:
            return None
        value = c / b
        given = f"{_tex(a * x + b * _symbols('y')[0])} = {_num(c)}"
        working = rf"{_num(b)}y = {_num(c)} \Rightarrow y = {_num(value)}"
    if not value.is_number or not value.is_finite or not value.is_real:
        return None
    answer = _point(0, value)
    workout = Workout(
        given=(math_line(given),),
        find=(math_line(r"\left(0, y\right)", "y-intercept"),),
        formula=(math_line("x = 0", "on the y-axis"),),
        substitution=(math_line(working),),
    )
    return workout, answer, [f"y-intercept: (0, {value})"]


def _x_intercepts(intent: MathIntent) -> _Solved | None:
    from sympy import Poly, S, solveset

    x, y = _symbols("x", "y")
    explicit = _explicit(intent)
    if explicit is not None:
        if not explicit.free_symbols or Poly(explicit, x).degree() not in {1, 2}:
            return None
        roots = sorted(solveset(explicit, x, domain=S.Reals), key=lambda value: float(value))
        given = f"y = {_tex(explicit)}"
        working = f"0 = {_tex(explicit)}"
    else:
        line = _linear(intent)
        if line is None:
            return None
        a, b, c = line
        if a == 0:
            return None
        roots = [c / a]
        given = f"{_tex(a * x + b * y)} = {_num(c)}"
        working = rf"{_num(a)}x = {_num(c)}"
    if not roots:
        return None
    answer = r",\ ".join(_point(root, 0) for root in roots)
    solved = r" \text{ or } ".join(f"x = {_num(root)}" for root in roots)
    workout = Workout(
        given=(math_line(given),),
        find=(math_line(r"\left(x, 0\right)", "x-intercept" + ("s" if len(roots) > 1 else "")),),
        formula=(math_line("y = 0", "on the x-axis"),),
        substitution=(math_line(working), math_line(solved)),
    )
    return workout, answer, [f"x-intercepts: {', '.join(str(root) for root in roots)}"]


def _discriminant(intent: MathIntent) -> _Solved | None:
    quadratic = _quadratic(intent, explicit_only=False)
    if quadratic is None:
        return None
    a, b, c, expression = quadratic
    value = b**2 - 4 * a * c
    answer = f"b^{{2}} - 4ac = {_num(value)}"
    workout = Workout(
        given=(math_line(f"{_tex(expression)} = 0"),),
        find=(math_line(r"\Delta", "discriminant"),),
        formula=(math_line(r"\Delta = b^2 - 4ac", "Discriminant"),),
        substitution=(
            math_line(
                rf"\Delta = {_bracket(b)}^2 - 4 \cdot {_bracket(a)} \cdot {_bracket(c)}"
                rf" = {_num(value)}"
            ),
        ),
    )
    return workout, answer, [f"Discriminant: {value}"]


def _roots_sum_or_product(intent: MathIntent, *, product: bool) -> _Solved | None:
    quadratic = _quadratic(intent, explicit_only=False)
    if quadratic is None:
        return None
    a, b, c, expression = quadratic
    if b**2 - 4 * a * c == 0:
        # One repeated root: "the sum of the roots" is 2r or r depending on who asks.
        return None
    if product:
        value = c / a
        answer = f"x_{{1}} x_{{2}} = {_num(value)}"
        formula = math_line(r"x_1 x_2 = \frac{c}{a}", "Product of the roots")
        working = rf"x_1 x_2 = \frac{{{_num(c)}}}{{{_num(a)}}} = {_num(value)}"
    else:
        value = -b / a
        answer = f"x_{{1}} + x_{{2}} = {_num(value)}"
        formula = math_line(r"x_1 + x_2 = -\frac{b}{a}", "Sum of the roots")
        working = rf"x_1 + x_2 = -\frac{{{_num(b)}}}{{{_num(a)}}} = {_num(value)}"
    workout = Workout(
        given=(math_line(f"{_tex(expression)} = 0"),),
        find=(math_line(r"x_1 x_2" if product else r"x_1 + x_2"),),
        formula=(formula,),
        substitution=(math_line(working),),
    )
    return workout, answer, [f"{'Product' if product else 'Sum'} of the roots: {value}"]


def _slope_of(intent: MathIntent) -> tuple[Any, Any, str] | None:
    """(slope, intercept, the line as given) for a non-vertical straight line."""
    line = _linear(intent)
    if line is None:
        return None
    a, b, c = line
    if b == 0:
        return None
    x, y = _symbols("x", "y")
    return -a / b, c / b, f"{_tex(a * x + b * y)} = {_num(c)}"


def _slope(intent: MathIntent) -> _Solved | None:
    found = _slope_of(intent)
    if found is None:
        return None
    slope, intercept, given = found
    answer = f"m = {_num(slope)}"
    workout = Workout(
        given=(math_line(given),),
        find=(math_line("m", "slope"),),
        formula=(math_line("y = mx + c", "Slope-intercept form"),),
        substitution=(math_line(_line_tex(slope, intercept)),),
    )
    return workout, answer, [f"Slope: {slope}"]


def _slope_intercept(intent: MathIntent) -> _Solved | None:
    found = _slope_of(intent)
    if found is None:
        return None
    slope, intercept, given = found
    answer = _line_tex(slope, intercept)
    workout = Workout(
        given=(math_line(given),),
        find=(math_line("y = mx + c"),),
        steps=(math_line(answer, "solve for y"),),
    )
    return workout, answer, [f"Slope-intercept form: {answer}"]


def _line_through(intent: MathIntent) -> _Solved | None:
    from sympy import Rational, nsimplify

    line = _linear(intent)
    if line is None or intent.point_x is None or intent.point_y is None:
        return None
    a, b, c = line
    px, py = nsimplify(intent.point_x, rational=True), nsimplify(intent.point_y, rational=True)
    relation = intent.trial_outcome
    x, y = _symbols("x", "y")
    given = (
        math_line(f"{_tex(a * x + b * y)} = {_num(c)}", "the line"),
        math_line(_point(px, py), "the point"),
    )
    if b == 0:
        # A vertical line: parallel lines are vertical, perpendicular ones horizontal.
        answer = f"x = {_num(px)}" if relation == "parallel" else f"y = {_num(py)}"
        workout = Workout(given=given, steps=(math_line(answer, f"{relation} to a vertical line"),))
        return workout, answer, [f"Line: {answer}"]
    slope = -a / b
    if relation == "parallel":
        new = slope
        rule = math_line(r"m_{\parallel} = m", "Parallel lines have equal slopes")
    elif slope == 0:
        answer = f"x = {_num(px)}"
        workout = Workout(given=given, steps=(math_line(answer, "perpendicular to a flat line"),))
        return workout, answer, [f"Line: {answer}"]
    else:
        new = Rational(-1) / slope
        rule = math_line(r"m_{\perp} = -\frac{1}{m}", "Perpendicular slopes multiply to -1")
    intercept = py - new * px
    answer = _line_tex(new, intercept)
    workout = Workout(
        given=given,
        find=(math_line("y = mx + c"),),
        formula=(rule, math_line(r"y - y_1 = m\left(x - x_1\right)", "Point-slope form")),
        substitution=(
            math_line(f"m = {_num(slope)}", "slope of the given line"),
            math_line(f"m = {_num(new)}", f"slope of the {relation} line"),
            math_line(rf"y - {_bracket(py)} = {_num(new)}\left(x - {_bracket(px)}\right)"),
            math_line(answer),
        ),
    )
    return workout, answer, [f"Line: {answer}"]


def _parameter(intent: MathIntent) -> _Solved | None:
    from sympy import Poly, S, expand, solveset

    from app.modules.math import solve as math_solve

    name = intent.variable
    if name in {"x", "e", "i"}:
        return None
    x, k = _symbols("x", name)
    lhs, rhs = _sides(intent, ["x", name])
    expression = expand(lhs - rhs)
    if not expression.free_symbols <= {x, k} or k not in expression.free_symbols:
        return None
    poly = Poly(expression, x)
    if poly.degree() != 2:
        return None
    a, b, c = poly.all_coeffs()
    if k in a.free_symbols or a == 0:
        # With the parameter in front of x^2 the equation can turn linear;
        # that case needs its own reading.
        return None
    discriminant = expand(b**2 - 4 * a * c)
    if k not in discriminant.free_symbols:
        return None
    relation = intent.comparator or "="
    if relation == "=":
        values = sorted(solveset(discriminant, k, domain=S.Reals), key=lambda v: float(v))
        if not values:
            return None
        answer = r" \text{ or } ".join(f"{name} = {_num(value)}" for value in values)
    else:
        result = math_solve.solve_inequality(str(discriminant), "0", name, relation)
        if len(result.solutions_latex) != 1:
            return None
        answer = result.solutions_latex[0]
    symbol = {"=": "=", ">": ">", "<": "<"}[relation]
    workout = Workout(
        given=(math_line(f"{_tex(expression)} = 0"),),
        find=(math_line(name),),
        formula=(math_line(rf"b^2 - 4ac {symbol} 0", "the condition on the discriminant"),),
        substitution=(
            math_line(
                rf"{_bracket(b)}^2 - 4 \cdot {_bracket(a)} \cdot {_bracket(c)} "
                rf"= {_tex(discriminant)} {symbol} 0"
            ),
            math_line(answer),
        ),
    )
    return workout, answer, [f"Discriminant {_tex(discriminant)} {symbol} 0: {answer}"]


def _sinusoid(intent: MathIntent) -> tuple[Any, Any, Any, Any] | None:
    """``y = A sin(Bx + C) + D`` (or cos, tan) as (A, B, the function, F), checked exactly."""
    from sympy import Wild, cos, simplify, sin, tan

    (x,) = _symbols("x")
    expression = _explicit(intent)
    if expression is None or x not in expression.free_symbols:
        return None
    amplitude, frequency = Wild("A", exclude=[x]), Wild("B", exclude=[x])
    phase, shift = Wild("C", exclude=[x]), Wild("D", exclude=[x])
    for function in (sin, cos, tan):
        found = expression.match(amplitude * function(frequency * x + phase) + shift)
        if not found:
            continue
        a, b = found[amplitude], found[frequency]
        c, d = found.get(phase, 0), found.get(shift, 0)
        if not all(value.is_number and value.is_real for value in (a, b, c, d)):
            return None
        if a == 0 or b == 0:
            return None
        if simplify(expression - (a * function(b * x + c) + d)) != 0:
            return None
        return a, b, function, expression
    return None


def _period(intent: MathIntent) -> _Solved | None:
    from sympy import Abs, pi, tan

    found = _sinusoid(intent)
    if found is None:
        return None
    _a, b, function, expression = found
    base = pi if function is tan else 2 * pi
    period = base / Abs(b)
    answer = _tex(period)
    rule = r"\frac{\pi}{|B|}" if function is tan else r"\frac{2\pi}{|B|}"
    workout = Workout(
        given=(math_line(f"y = {_tex(expression)}"),),
        find=(math_line("T", "period"),),
        formula=(math_line(rf"T = {rule}", f"period of {function.__name__}(Bx + C)"),),
        substitution=(math_line(rf"T = \frac{{{_tex(base)}}}{{{_tex(Abs(b))}}} = {answer}"),),
    )
    return workout, answer, [f"Period: {period}"]


def _amplitude(intent: MathIntent) -> _Solved | None:
    from sympy import Abs, tan

    found = _sinusoid(intent)
    if found is None or found[2] is tan:
        # A tangent has no amplitude.
        return None
    a, _b, function, expression = found
    answer = _tex(Abs(a))
    workout = Workout(
        given=(math_line(f"y = {_tex(expression)}"),),
        find=(math_line("A", "amplitude"),),
        formula=(math_line("|A|", f"amplitude of A {function.__name__}(Bx + C) + D"),),
        substitution=(math_line(rf"|{_tex(a)}| = {answer}"),),
    )
    return workout, answer, [f"Amplitude: {Abs(a)}"]


_MAX_COUNT_DEGREE = 4


def _solution_count(intent: MathIntent) -> _Solved | None:
    """How many solutions one polynomial equation in x has.

    Without "real", the count must be the same over the reals and the complex
    numbers (``x^2 + 1 = 0`` has none or two, so it is declined).
    """
    from sympy import Poly, S, solveset

    (x,) = _symbols("x")
    lhs, rhs = _sides(intent, ["x"])
    expression = lhs - rhs
    if not expression.free_symbols <= {x}:
        return None
    poly = Poly(expression, x)
    if poly.degree() > _MAX_COUNT_DEGREE:
        return None
    real = intent.trial_outcome == "real"
    reals = solveset(expression, x, domain=S.Reals)
    complexes = solveset(expression, x, domain=S.Complexes)
    if reals == S.Reals:
        if not real and complexes != S.Complexes:
            return None
        answer = r"\text{infinitely many}"
        working = r"\text{true for every } x"
    else:
        if not hasattr(reals, "__len__") or not hasattr(complexes, "__len__"):
            return None
        if not real and len(reals) != len(complexes):
            return None
        answer = str(len(reals))
        listed = r"\varnothing" if not len(reals) else _tex(reals)
        working = rf"\text{{{'real ' if real else ''}solutions: }} {listed}"
    rows: list[str] = []
    if rhs != 0 or lhs != poly.as_expr():
        constant = poly.degree() == 0 and poly.as_expr() != 0
        note = "never true, whatever x is" if constant else "everything on one side"
        rows.append(math_line(f"{_tex(poly.as_expr())} = 0", note))
    if poly.degree() == 2:
        a, b, c = poly.all_coeffs()
        discriminant = b**2 - 4 * a * c
        sign = ">" if discriminant > 0 else ("=" if discriminant == 0 else "<")
        rows.append(
            math_line(rf"\Delta = b^2 - 4ac = {_num(discriminant)} {sign} 0", "discriminant")
        )
    rows.append(math_line(working))
    workout = Workout(
        given=(math_line(f"{_tex(lhs)} = {_tex(rhs)}"),),
        find=(math_line(r"\text{number of " + ("real " if real else "") + "solutions}"),),
        steps=tuple(rows),
    )
    return workout, answer, [f"Number of solutions: {answer}"]


_SOLVERS = {
    "vertex": _vertex,
    "axis": _axis,
    "y_intercept": _y_intercept,
    "x_intercepts": _x_intercepts,
    "discriminant": _discriminant,
    "root_sum": lambda intent: _roots_sum_or_product(intent, product=False),
    "root_product": lambda intent: _roots_sum_or_product(intent, product=True),
    "slope": _slope,
    "slope_intercept": _slope_intercept,
    "line_through": _line_through,
    "parameter": _parameter,
    "period": _period,
    "amplitude": _amplitude,
    "solution_count": _solution_count,
}
