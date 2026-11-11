"""Read a request for one feature of one stated equation into an intent.

The feature, the equation and an optional point must be the whole request, apart
from framing words; otherwise there is no intent and the model answers.
"""

from __future__ import annotations

import re

from app.modules.math.schemas import MathIntent, declined_reading
from app.modules.math.tools.school.equation_features.count_conditions import (
    CountConditions,
    count_region,
    has_condition,
    read_count_conditions,
)

FEATURE_OPS = frozenset(
    {
        "equation_vertex",
        "equation_axis",
        "equation_y_intercept",
        "equation_x_intercepts",
        "equation_intercepts",
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
    # Both axes: "the intercepts", "the x- and y-intercepts".
    (
        "intercepts",
        re.compile(
            r"(?:\b(?:x[\s-]*and[\s-]*y|y[\s-]*and[\s-]*x)[\s-]*|(?<![xy][\s-])(?<![\w-]))"
            r"intercepts\b",
            re.I,
        ),
    ),
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
    # "how many real roots does x^2 + 2x + 5 = 0 have", "how many solutions are there to
    # …", "find the number of real solutions of …"
    (
        "solution_count",
        re.compile(
            r"\b(?:how\s+many|(?:the\s+)?number\s+of)\s+(?:distinct\s+|different\s+)?"
            r"(?:(?:non-?)?(?:positive|negative)\s+)?(?P<real>real\s+)?(?:distinct\s+|different\s+)?"
            r"(?:solutions?|roots?|zeros?|zeroes?)"
            r"\s+(?:does|do|will|has|are\s+there(?:\s+(?:to|for|of|in))?|of|to|for|in)\b",
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
# A count's working solves the equation, so asking to solve it too is answered.
_SOLVE_WORDS = frozenset({"solve", "it", "them", "they", "find", "list"})
# The parameter question about how many solutions there are, in any form: "find k so that
# x^2 + kx + 9 = 0 has exactly one solution ...". "has the solution x = 3" is a value to
# substitute, which the system path reads, and is not this.
_PARAMETER_ASK = re.compile(
    r"^(?:find|determine|calculate|work\s+out|what\s+(?:is|are|must|should))\b"
    r".*\b(?:so\s+that|such\s+that|for\s+which)\b.*=.*\b(?:has|have)\s+"
    r"(?:exactly\s+|only\s+|precisely\s+)?(?:one|two|three|no|[0-9]|a\s+single|a\s+repeated|"
    r"a\s+double|equal|repeated|distinct|different|real|infinitely\s+many)\b"
    r".*\b(?:solutions?|roots?|zeros?|zeroes?)\b",
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
        "show",
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
        return _parameter_intent(parameter) or declined_reading("equation_parameter")
    if _PARAMETER_ASK.match(body):
        # "find k so that ... has exactly one solution for x > 0": a count requirement
        # in a form the rule above does not read; another path would drop it.
        return declined_reading("equation_parameter")
    found = [(op, match) for op, pattern in _FEATURES if (match := pattern.search(body))]
    ops = {op for op, _ in found}
    if "slope_intercept" in ops:
        ops -= {"slope", "y_intercept", "x_intercepts", "intercepts"}
    if "intercepts" in ops:
        ops -= {"y_intercept", "x_intercepts"}
    if "line_through" in ops:
        ops -= {"slope"}
    if len(ops) != 1:
        return None
    (op,) = ops
    match = next(match for name, match in found if name == op)
    if op == "solution_count":
        counted = _count_reading(body)
        if counted is None and has_condition(body):
            # A count over a set it cannot read: another path would drop the set and
            # answer another question (the model's reading certified a condition's set).
            return declined_reading("equation_solution_count")
        return counted
    if has_condition(body):
        # "the x-intercepts of y = x^2 - 4 for x > 0": no feature rule reads a condition,
        # and the feature without it answers another question.
        read = read_count_conditions(body)
        again = dict(_FEATURES)[op].search(read[0]) if read is not None else None
        if read is not None and again is not None and _only_frame_words(read[0], again):
            return declined_reading(f"equation_{op}")
        return None
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
        trial_outcome=match.group("relation").lower() if op == "line_through" else None,
        operation="solve",
    )


def _count_reading(body: str) -> MathIntent | None:
    """A count over the set its conditions name ("in [0, 5]", "for x > 0", "positive"),
    read first; None when any part does not read."""
    read = read_count_conditions(body)
    if read is None:
        return None
    body, conditions = read
    match = dict(_FEATURES)["solution_count"].search(body)
    if match is None or _NUMBERED_POINT.search(body):
        return None
    sides = _one_equation(body, "solution_count")
    # "Solve x^2 = 4. How many solutions are there?": the working solves it too.
    if sides is None or not _only_frame_words(body, match, also=_SOLVE_WORDS):
        return None
    return _count_intent(*sides, match, conditions)


def _count_intent(
    lhs: str, rhs: str, match: re.Match[str], conditions: CountConditions
) -> MathIntent | None:
    """A count over its conditions: the bounds as a bounded solve carries them
    (``integral_lower``/``integral_upper``, ``comparator``/``comparator_upper``; ``?`` for
    "between", either end may count), and what is counted in ``trial_outcome``."""
    from app.modules.math import solve as math_solve

    unknowns = math_solve.guess_variables(f"{lhs} = {rhs}")
    region = count_region(conditions, unknowns[0]) if len(unknowns) == 1 else None
    if region is None:
        return None
    counted = [
        word
        for word, wanted in (
            ("real", match.group("real")),
            ("multiplicity", conditions.multiplicity),
        )
        if wanted
    ]
    return MathIntent(
        kind="arithmetic",
        school_op="equation_solution_count",
        lhs=lhs,
        rhs=rhs,
        integral_lower=region.lower,
        integral_upper=region.upper,
        comparator=_end(region.lower_closed) if region.lower is not None else None,
        comparator_upper=_end(region.upper_closed) if region.upper is not None else None,
        # The points a condition removes ("x != 2"): the only operands a count has.
        arithmetic_operands=list(region.excluded) or None,
        trial_outcome=" ".join(counted) or None,
        operation="solve",
    )


def _end(closed: bool | None) -> str:
    return "?" if closed is None else ("<=" if closed else "<")


def _no_equals_ok(body: str) -> bool:
    """``discriminant of 3x^2 + 2x + 1`` names a quadratic with no ``= 0``."""
    lower = body.lower()
    return any(word in lower for word in ("discriminant", "sum of", "product of"))


def _one_equation(body: str, op: str) -> tuple[str, str] | None:
    from app.modules.math.solve.extract_eq import try_extract_equations_from_text
    from app.modules.math.tools.expr_rewrite import math_expr_or_none

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


def _only_frame_words(
    body: str, feature: re.Match[str], also: frozenset[str] = frozenset()
) -> bool:
    """Nothing but the feature, the equation, a point and framing words (and ``also``)."""
    from app.modules.math.function_names import MATH_FUNCTION_NAMES

    rest = body[: feature.start()] + " " + body[feature.end() :]
    for token in rest.split():
        if re.search(r"[\d=^()+\-*/<>]", token):
            continue
        word = re.sub(r"[^a-z]", "", token.lower())
        if len(word) < 2:
            continue
        if word not in _FRAME_WORDS and word not in also and word not in MATH_FUNCTION_NAMES:
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
