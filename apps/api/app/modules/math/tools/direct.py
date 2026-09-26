"""Direct verified-math replies that skip the LLM when language adds nothing."""

from __future__ import annotations

import json
import math
import re

from app.models.schemas.physics.simulation import SIMULATION_SPEC_TYPES
from app.modules.math.tools.lesson import (
    format_equation_lesson_reply,
    lesson_math_text,
    should_render_equation_lesson,
    strip_teaching_signals,
    wants_detailed_math_explanation,
    wants_math_explanation,
)
from app.services.solving import VerifiedMathBlock

# Imperative / polite glue around a closed compute. Two leftover English
# words beyond this ("tell" + "joke") keep the LLM.
_MATH_REQUEST_GLUE = frozenset(
    {
        "solve",
        "isolate",
        "factor",
        "expand",
        "simplify",
        "calculate",
        "compute",
        "evaluate",
        "determine",
        "find",
        "please",
        "thanks",
        "thank",
        "now",
        "quickly",
        "briefly",
        "here",
        "what",
        "whats",
        "the",
        "value",
        "of",
        "for",
        "and",
        "then",
        "is",
        "equals",
        "equal",
        "plus",
        "minus",
        "times",
        "can",
        "you",
        "could",
        "this",
        "that",
    }
)

_MAX_DIRECT_ANSWER_CHARS = 400


def _plot_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        return None
    if isinstance(value, str) and len(value) > 64:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _literal_plot_point(text: str) -> tuple[float, float] | None:
    value = text.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    parts = value.split(",")
    if len(parts) != 2:
        return None
    x, y = (_plot_number(part.strip()) for part in parts)
    return (x, y) if x is not None and y is not None else None


def _can_direct_point_or_vertical(verified: VerifiedMathBlock, user_text: str) -> bool:
    """Match a complete literal plot request, never a coordinate substring."""
    if len(user_text) > 1000:
        return False
    fences = _solver_fences(verified)
    if len(fences) != 1:
        return False
    graph = fences[0]
    if graph.get("expr2") or graph.get("points2") or graph.get("variable", "x") != "x":
        return False
    request = " ".join(user_text.split()).replace("\u2212", "-")
    if request.lower().startswith("please "):
        request = request[7:].lstrip()
    for prefix in ("plot ", "graph ", "mark ", "show ", "draw ", "sketch "):
        if request.lower().startswith(prefix):
            request = request[len(prefix) :].strip().rstrip(".?")
            break
    else:
        return False
    if request.lower().startswith("the "):
        request = request[4:]
    if graph.get("type") == "vertical":
        if verified.canonical_answer:
            return False
        for prefix in ("vertical line ", "line "):
            if request.lower().startswith(prefix):
                request = request[len(prefix) :]
                break
        lhs, separator, rhs = request.partition("=")
        x = _plot_number(graph.get("x"))
        expr_lhs, expr_separator, expr_rhs = str(graph.get("expr") or "").partition("=")
        low, high = _plot_number(graph.get("y_min")), _plot_number(graph.get("y_max"))
        return bool(
            separator
            and lhs.strip().lower() == "x"
            and x is not None
            and _plot_number(rhs.strip()) == x
            and expr_separator
            and expr_lhs.strip().lower() == "x"
            and _plot_number(expr_rhs.strip()) == x
            and low is not None
            and high is not None
            and low < high
        )
    if graph.get("type") != "function" or not request.lower().startswith("point "):
        return False
    points = graph.get("points")
    if not isinstance(points, list) or len(points) != 1:
        return False
    point = points[0]
    if not isinstance(point, list) or len(point) != 2:
        return False
    x, y = (_plot_number(value) for value in point)
    if x is None or y is None:
        return False
    expected = (x, y)
    # All three canonical representations must describe the requested point.
    # Extra prose, a second coordinate, expressions, or unpaired brackets do
    # not parse as one numeric comma pair and retain the model path.
    return (
        _literal_plot_point(request[6:]) == expected
        and _literal_plot_point(str(graph.get("expr") or "")) == expected
        and _literal_plot_point(verified.canonical_answer or "") == expected
    )


def _looks_math_token(tok: str) -> bool:
    if not tok:
        return True
    return any(ch.isdigit() or ch in "=^*/+-%" for ch in tok)


def leftover_non_math_request(text: str) -> bool:
    """True when the message asks for something besides the verified value.

    ``Solve x+1=2 and tell me a joke`` must not become an instant ``x = 1``.
    Linear token walk — no regex on user text.
    """
    english = 0
    for raw in text.replace("'", "").split():
        tok = raw.lower().strip(".,?!:;")
        if _looks_math_token(tok) or len(tok) < 3 or tok in _MATH_REQUEST_GLUE:
            continue
        english += 1
        if english >= 2:
            return True
    return False


def _solver_fences(verified: VerifiedMathBlock) -> list[dict[str, object]]:
    fences: list[dict[str, object]] = []
    if verified.canonical_fence is not None:
        fences.append(verified.canonical_fence)
    for fence in verified.canonical_fences:
        if fence is not None and fence not in fences:
            fences.append(fence)
    return fences


_GEOMETRY_DECLARATION_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "angle",
        "angles",
        "base",
        "bases",
        "bottom",
        "by",
        "circle",
        "cm",
        "cone",
        "cube",
        "cuboid",
        "cylinder",
        "degree",
        "degrees",
        "depth",
        "diameter",
        "draw",
        "edge",
        "edges",
        "feet",
        "foot",
        "ft",
        "height",
        "in",
        "inch",
        "inches",
        "km",
        "leg",
        "legs",
        "length",
        "lengths",
        "m",
        "meter",
        "meters",
        "metre",
        "metres",
        "mm",
        "of",
        "parallelogram",
        "pie",
        "please",
        "prism",
        "pyramid",
        "radius",
        "rect",
        "rectangle",
        "rectangular",
        "right",
        "sector",
        "show",
        "side",
        "sides",
        "sketch",
        "slice",
        "sphere",
        "square",
        "the",
        "top",
        "trapezium",
        "trapezoid",
        "triangle",
        "unit",
        "units",
        "visualise",
        "visualize",
        "width",
        "with",
        "x",
    }
)
_GEOMETRY_SHAPE_ALIASES: dict[str, tuple[str, ...]] = {
    "rectangle": ("rectangle", "rect"),
    "square": ("square",),
    "triangle": ("triangle",),
    "right_triangle": ("right triangle",),
    "triangle_sides": ("triangle",),
    "parallelogram": ("parallelogram",),
    "trapezoid": ("trapezoid", "trapezium"),
    "circle": ("circle",),
    "sector": ("circle sector", "sector", "pie slice"),
}
_GEOMETRY_QUESTIONS = {
    "rectangle": "Do you want the area, perimeter, or diagonal?",
    "square": "Do you want the area, perimeter, or diagonal?",
    "triangle": "Do you want the area, or only a labeled diagram?",
    "right_triangle": "Do you want the area, perimeter, hypotenuse, or angles?",
    "triangle_sides": "Do you want the area, perimeter, or angles?",
    "parallelogram": "Do you want the area or perimeter?",
    "trapezoid": "Do you want the area, or only a labeled diagram?",
    "circle": "Do you want the area, circumference, or diameter?",
    "sector": "Do you want the area or arc length?",
}
_DRAW_WORDS = frozenset({"draw", "show", "sketch", "visualize", "visualise"})
_GEOMETRY_NUMBER_COUNTS: dict[str, frozenset[int]] = {
    "rectangle": frozenset({2}),
    "square": frozenset({1}),
    "triangle": frozenset({2}),
    "right_triangle": frozenset({2}),
    "triangle_sides": frozenset({3}),
    "parallelogram": frozenset({2, 3}),
    "trapezoid": frozenset({3}),
    "circle": frozenset({1}),
    "sector": frozenset({2}),
    "cube": frozenset({1}),
    "rectangular_prism": frozenset({3}),
    "cylinder": frozenset({2}),
    "cone": frozenset({2}),
    "sphere": frozenset({1}),
    "pyramid": frozenset({2}),
}


def _geometry_shape_mentions(lower: str) -> list[str]:
    """Return semantic shape mentions, collapsing compound shape names."""
    normalized = lower
    compounds = (
        (r"\bsector\s+of\s+(?:a\s+)?circle\b", "sector"),
        (r"\bcircle\s+sector\b", "sector"),
        (r"\bpie\s+slice\b", "sector"),
        (r"\bright\s+triangle\b", "right_triangle"),
        (r"\brectangular\s+prism\b", "rectangular_prism"),
        (r"\bsquare\s+pyramid\b", "pyramid"),
    )
    mentions: list[str] = []
    for pattern, kind in compounds:
        matches = re.findall(pattern, normalized)
        mentions.extend(kind for _ in matches)
        normalized = re.sub(pattern, " ", normalized)
    aliases = {
        "rect": "rectangle",
        "trapezium": "trapezoid",
    }
    for shape in re.findall(
        r"\b(?:rectangle|rect|square|triangle|parallelogram|trapezoid|trapezium|"
        r"circle|sector|cube|cuboid|cylinder|cone|sphere|pyramid)\b",
        normalized,
    ):
        mentions.append(aliases.get(shape, shape))
    return mentions


def _plain_geometry_description(
    user_text: str, aliases: tuple[str, ...], kind: str
) -> tuple[bool, bool]:
    """Return (is plain shape description, explicitly asks for a drawing)."""
    if len(user_text) > 1000 or any(char in user_text for char in "+=^;!-"):
        return False, False
    lower = " ".join(user_text.lower().split()).strip().rstrip(".?")
    words = re.findall(r"[a-z]+", lower)
    if not words or any(word not in _GEOMETRY_DECLARATION_WORDS for word in words):
        return False, False
    draw = any(word in _DRAW_WORDS for word in words)
    if len(_geometry_shape_mentions(lower)) != 1:
        return False, False
    number_count = len(re.findall(r"(?:\d+(?:\.\d+)?|\.\d+)", lower))
    expected_counts = _GEOMETRY_NUMBER_COUNTS[kind]
    if number_count not in expected_counts and not (draw and number_count == 0):
        return False, False
    request = lower
    if request.startswith("please "):
        request = request[7:].lstrip()
    if draw:
        for verb in _DRAW_WORDS:
            if request.startswith(verb + " "):
                request = request[len(verb) + 1 :].lstrip()
                break
    for article in ("a ", "an ", "the "):
        if request.startswith(article):
            request = request[len(article) :].lstrip()
            break
    starts_with_shape = any(
        request == alias or request.startswith(alias + " ") for alias in aliases
    )
    return starts_with_shape and (any(char.isdigit() for char in lower) or draw), draw


def _nonmeasurement_geometry_reply(verified: VerifiedMathBlock, user_text: str) -> str | None:
    """Clarify a dimension-only shape instead of inventing area/volume.

    Explicit draw/show requests are complete as written and return only their
    solver-owned diagram. The narrow vocabulary check keeps mixed requests on
    the normal language path.
    """
    from app.modules.math.match.literal_geometry import measurement_request

    # Never reinterpret an answering block as a draw/clarification request.
    # This also prevents a stale verified measurement from being hidden by a
    # later, less specific drawing phrase.
    if verified.canonical_answer is not None:
        return None

    requested_measurement = measurement_request(user_text)
    fences = _solver_fences(verified)
    if len(fences) == 1:
        # Angle-only triangles already have a strict whole-request validator.
        # Let it reject added sides, shapes, calculations, or explanations.
        if fences[0].get("relative_lengths") is True:
            return None
        kind = fences[0].get("type")
        aliases = _GEOMETRY_SHAPE_ALIASES.get(str(kind))
        if aliases is not None:
            plain, draw = _plain_geometry_description(user_text, aliases, str(kind))
            if not plain:
                return None
            if draw:
                return f"```geometry\n{json.dumps(fences[0], separators=(',', ':'))}\n```\n"
            question = _GEOMETRY_QUESTIONS[str(kind)]
            diagram = json.dumps(fences[0], separators=(",", ":"))
            return (
                f"You gave the dimensions, but not what to calculate. {question}\n\n"
                f"```geometry\n{diagram}\n```\n"
            )
        if requested_measurement is not None:
            return None

    if verified.canonical_answer is None and not fences:
        for kind, aliases in _GEOMETRY_SHAPE_ALIASES.items():
            # Both SSS and base-height inputs say "triangle". Preserve the
            # more specific choices when the user supplied all three sides.
            if kind == "triangle" and re.search(r"\bsides?\b", user_text, re.IGNORECASE):
                continue
            if kind == "triangle_sides" and not re.search(r"\bsides?\b", user_text, re.IGNORECASE):
                continue
            plain, draw = _plain_geometry_description(user_text, aliases, kind)
            if plain and not draw:
                return (
                    "You gave the dimensions, but not what to calculate. "
                    f"{_GEOMETRY_QUESTIONS[kind]}"
                )

    if requested_measurement is not None:
        return None

    from app.modules.math.match.geometry import parse_solid

    solid = parse_solid(user_text)
    if solid is None or solid.wants_volume or solid.wants_surface_area:
        return None
    aliases = {
        "cube": ("cube",),
        "rectangular_prism": ("rectangular prism", "cuboid"),
        "cylinder": ("cylinder",),
        "cone": ("cone",),
        "sphere": ("sphere",),
        "pyramid": ("square pyramid", "pyramid"),
    }[solid.shape]
    plain, draw = _plain_geometry_description(user_text, aliases, solid.shape)
    if not plain or draw:
        return None
    return (
        "You gave the dimensions, but not what to calculate. "
        "Do you want the volume or surface area?"
    )


def _plain_prime_factorization_request(text: str) -> bool:
    """Match the complete one-integer ask; extra clauses still need language."""
    if len(text) > 1000:
        return False
    request = " ".join(text.lower().split()).rstrip(".?")
    for prefix in ("please ", "can you ", "could you "):
        if request.startswith(prefix):
            request = request[len(prefix) :]
            break
    for prefix in ("find ", "calculate ", "compute ", "determine ", "what is ", "what's "):
        if request.startswith(prefix):
            request = request[len(prefix) :]
            break
    if request.startswith("the "):
        request = request[4:]
    for prefix in ("prime factorization of ", "prime factors of ", "factorize "):
        if request.startswith(prefix):
            number = request[len(prefix) :]
            if number.endswith(" please"):
                number = number[:-7]
            return bool(number and number.isascii() and number.isdecimal())
    return False


def _can_direct_graph(verified: VerifiedMathBlock, user_text: str) -> bool:
    """Match the whole plot request, not an expression extracted from one clause."""
    from app.modules.math.match import graph_domain, prepare
    from app.modules.math.match.graph import _GRAPH_PAIR_TRAILING_FILLER

    if len(user_text) > 1000 or verified.canonical_answer:
        return False
    fences = _solver_fences(verified)
    if len(fences) != 1 or fences[0].get("type") not in {"function", "inequality"}:
        return False
    graph = fences[0]
    points, expr = graph.get("points"), graph.get("expr")
    expr2, points2 = graph.get("expr2"), graph.get("points2")
    paired = bool(expr2 or points2)
    if not isinstance(expr, str) or not expr.strip() or graph.get("variable", "x") != "x":
        return False
    if graph.get("type") == "function" and (not isinstance(points, list) or len(points) < 2):
        return False
    if paired and (
        graph.get("type") != "function"
        or not isinstance(expr2, str)
        or not expr2.strip()
        or not isinstance(points2, list)
        or len(points2) < 2
        or graph.get("variable2") != "x"
    ):
        return False
    request = prepare(user_text)
    if not request:
        return False
    if request.lower().startswith("please "):
        request = request[7:].lstrip()
    for prefix in ("graph ", "plot ", "draw ", "sketch ", "visualize ", "visualise "):
        if request.lower().startswith(prefix):
            # Keep !: it may be a factorial that extraction did not preserve.
            request = request[len(prefix) :].strip().rstrip(".?")
            break
    else:
        return False
    from app.modules.math.tools.extract import is_graph_followup

    # Pronoun follow-ups ("graph it") reuse the verified samples from a prior
    # equation; the current line has no f(x) to string-match.
    if is_graph_followup(user_text):
        return True
    domain = graph_domain(request)
    if domain is not None:
        lo, hi, request = domain
        # A range ignored by extraction or narrowed by sampling needs language.
        if graph.get("x_min") != lo or graph.get("x_max") != hi:
            return False
    if paired:
        for suffix in _GRAPH_PAIR_TRAILING_FILLER:
            if request.lower().endswith(suffix):
                request = request[: -len(suffix)].rstrip()
                break
        split_at = request.lower().find(" and ")
        if split_at < 0:
            return False
        clauses = (request[:split_at].strip(), request[split_at + 5 :].strip())
        for clause, sampled_expr in zip(clauses, (expr, expr2), strict=True):
            if "=" in clause:
                lhs, _, clause = clause.partition("=")
                if lhs.strip().lower() != "y":
                    return False
            # Reuse the exact sampled expressions, preserving any extra
            # request, third curve, factorial, or ignored domain as a mismatch.
            if clause.replace(" ", "").replace("^", "**") != str(sampled_expr).replace(
                " ", ""
            ).replace("^", "**"):
                return False
        return True
    if (
        graph.get("type") == "function"
        and "=" in expr
        and request.replace(" ", "").replace("^", "**") == expr.replace(" ", "").replace("^", "**")
    ):
        # The verified circle/ellipse sampler preserves the whole relation
        # and closes its parametric loop; it is not a y=f(x) expression.
        return isinstance(points, list) and len(points) >= 3 and points[0] == points[-1]
    if graph.get("type") == "function" and "=" in request:
        original = request
        lhs, _, rhs = request.partition("=")
        if lhs.strip().lower() == "y":
            request = rhs
        elif "y" not in original.lower():
            rhs_c = rhs.replace(" ", "").replace("^", "**")
            lhs_c = lhs.replace(" ", "").replace("^", "**")
            if rhs_c in {"0", "0.0"}:
                request = lhs
            elif lhs_c in {"0", "0.0"}:
                request = rhs
            else:
                return False
        else:
            return False
    # The verified sampler preserves its input expr. Requiring the entire
    # remaining request to match it keeps "and solve/explain/tell me..." and
    # additional formulas on the model path, without another SymPy parse.
    return request.replace(" ", "").replace("^", "**") == expr.replace(" ", "").replace("^", "**")


def _can_direct_number_line(
    verified: VerifiedMathBlock, user_text: str, *, require_solve: bool = True
) -> bool:
    """A whole inequality solve can display its answer and solution set directly.

    ``require_solve=False`` is for a lesson request whose teaching words were
    already stripped ("show steps for 2x+3<7" leaves the bare inequality).
    """
    from app.modules.math.match import prepare
    from app.modules.math.solve.parse import _rewrite_bare_abs_bars

    answer = (verified.canonical_answer or "").strip()
    fences = _solver_fences(verified)
    if (
        len(user_text) > 1000
        or not answer
        or len(answer) > _MAX_DIRECT_ANSWER_CHARS
        or len(fences) != 1
        or fences[0].get("type") != "number_line"
    ):
        return False
    expr = fences[0].get("expr")
    request = prepare(user_text)
    if not isinstance(expr, str) or not expr.strip() or not request:
        return False
    if request.lower().startswith("please "):
        request = request[7:].lstrip()
    if request.lower().startswith("solve "):
        request = request[6:].strip()
    elif require_solve:
        return False
    if request.lower().startswith("the inequality "):
        request = request[15:].lstrip()
    # Keep factorials and all remaining prose/domain clauses intact. Only
    # spelling-equivalent operators and whitespace can differ from the exact
    # inequality the solver used; no new symbolic parsing or prose whitelist.
    request = request.rstrip(".?")

    def compact(value: str) -> str:
        return (
            _rewrite_bare_abs_bars(value)
            .replace(" ", "")
            .replace("^", "**")
            .replace("≤", "<=")
            .replace("≥", ">=")
            .replace("\u2212", "-")
        )

    return compact(request) == compact(expr.rstrip(".?"))


def _underdetermined_triangle_measurement(
    verified: VerifiedMathBlock, user_text: str
) -> str | None:
    """A complete AAA measurement has a known shape, but no physical scale."""
    from app.modules.math.match.literal_geometry import measurement_request
    from app.modules.math.tools.direct_geometry import can_direct_triangle_angles

    if verified.canonical_answer is not None:
        return None
    parsed = measurement_request(user_text)
    if parsed is None or parsed[0] not in {"area", "perimeter"}:
        return None
    quantity, triangle = parsed
    # The existing whole-draw grammar validates all three literal angles and
    # their agreement with the one relative diagram; extra clauses cannot pass.
    if not can_direct_triangle_angles(f"Draw a {triangle}", _solver_fences(verified)):
        return None
    return quantity


def can_direct_verified_math_reply(
    verified: VerifiedMathBlock,
    user_text: str,
    *,
    has_image_attachment: bool = False,
    response_style: str = "balanced",
) -> bool:
    """Skip the LLM for a short closed answer or an explicit verified function plot.

    Geometry, camera homework, mixed leftover requests, and explanations that
    have no verified trace keep the inject+stream path. Detailed / "show steps"
    take the direct path when ``key_steps`` exist so the lesson cannot drift
    from the chip.
    """
    if has_image_attachment:
        return False
    if _nonmeasurement_geometry_reply(verified, user_text) is not None:
        return True
    lesson = should_render_equation_lesson(verified, user_text, response_style)
    if wants_math_explanation(user_text) and not lesson:
        return False
    if verified.physics_intent is not None:
        from app.modules.physics import can_direct_physics

        return can_direct_physics(verified, user_text, _solver_fences(verified))
    if not verified.allow_direct:
        return False
    from app.modules.math.tools.direct_newton import can_direct_newton, has_newton_request

    if verified.newton_input is not None or has_newton_request(user_text):
        return can_direct_newton(verified, user_text, _solver_fences(verified))
    if _underdetermined_triangle_measurement(verified, user_text) is not None:
        return True
    from app.modules.math.tools.direct_geometry import (
        can_direct_curved_or_slanted_geometry,
        can_direct_rectangle,
        can_direct_square_or_triangle,
        can_direct_triangle_angles,
    )

    geometry_fences = _solver_fences(verified)
    if can_direct_curved_or_slanted_geometry(verified, user_text, geometry_fences):
        return True
    if can_direct_triangle_angles(user_text, geometry_fences):
        return True
    if can_direct_rectangle(verified, user_text, geometry_fences) or can_direct_square_or_triangle(
        verified, user_text, geometry_fences
    ):
        return True
    if _can_direct_point_or_vertical(verified, user_text):
        return True
    if _can_direct_graph(verified, user_text):
        return True
    if _can_direct_number_line(verified, user_text):
        return True
    if lesson and _can_direct_number_line(
        verified, lesson_math_text(user_text), require_solve=False
    ):
        return True
    # Prime factorization has two operation words, which the generic prose
    # counter rejects. Require a whole-request match instead of whitelisting
    # them globally; even "factorize 60 and 2+2" must retain the model path.
    from app.modules.math.match.coordinate_vector import (
        has_coordinate_vector_request,
        is_closed_coordinate_vector_request,
    )
    from app.modules.math.tools.direct_calculus import calculus_direct_request
    from app.modules.math.tools.direct_solids import solid_direct_request
    from app.modules.math.tools.direct_statistics import statistics_direct_request
    from app.modules.math.tools.direct_units import unit_direct_request

    statistics_request = statistics_direct_request(user_text)
    unit_request = unit_direct_request(user_text)
    solid_request = solid_direct_request(user_text)
    calculus_request = calculus_direct_request(user_text, answer=verified.canonical_answer)
    if (
        statistics_request is False
        or unit_request is False
        or solid_request is False
        or calculus_request is False
    ):
        return False
    if statistics_request or unit_request or solid_request or calculus_request:
        fences = _solver_fences(verified)
        if (
            len(fences) != 1
            or fences[0].get("type") != "answer"
            or fences[0].get("content") != verified.canonical_answer
        ):
            return False
    lower = user_text.lower()
    coordinate_vector_request = has_coordinate_vector_request(user_text)
    if coordinate_vector_request and not is_closed_coordinate_vector_request(user_text):
        return False
    factorization_request = "prime factor" in lower or "factorize" in lower
    if factorization_request and not _plain_prime_factorization_request(user_text):
        return False
    if not (
        factorization_request
        or coordinate_vector_request
        or statistics_request
        or unit_request
        or solid_request
        or calculus_request
    ) and leftover_non_math_request(strip_teaching_signals(user_text)):
        return False
    answer = (verified.canonical_answer or "").strip()
    if calculus_request and any(
        token in answer
        for token in (r"\lim", r"\int", r"\sum", r"\frac{d}{d", r"\langle", "Derivative", "NaN")
    ):
        return False
    if not answer or len(answer) > _MAX_DIRECT_ANSWER_CHARS:
        return False
    fences = _solver_fences(verified)
    if not fences:
        return True
    return all(fence.get("type") == "answer" for fence in fences)


def format_direct_math_reply(verified: VerifiedMathBlock, user_text: str = "") -> str:
    """Display a verified value, diagram, or the missing scale for an AAA request."""
    geometry_reply = _nonmeasurement_geometry_reply(verified, user_text)
    if geometry_reply is not None:
        return geometry_reply
    if verified.newton_input is not None:
        from app.modules.math.tools.direct_newton import format_newton_reply

        return format_newton_reply(verified)
    quantity = _underdetermined_triangle_measurement(verified, user_text)
    if quantity is not None:
        return f"The {quantity} cannot be determined from angles alone. What is one side length?"
    fences = _solver_fences(verified)
    # A P14 scene rides alongside the answering fence rather than replacing it,
    # so it is set aside before the `len(fences) == 1` branches below and put
    # back at the end. Leaving it in the list matched none of them and silently
    # reduced every projectile to a bare answer pill — the graph the fast path
    # had always shown simply stopped appearing.
    scenes = [f for f in fences if f.get("type") in SIMULATION_SPEC_TYPES]
    fences = [f for f in fences if f not in scenes]
    answer = (verified.canonical_answer or "").strip()
    display_answer = (verified.display_answer or answer).strip()
    physics_working: str | None = None
    if verified.physics_intent is not None:
        from app.modules.physics import format_direct_physics_working

        physics_working = format_direct_physics_working(verified)
    if scenes:
        body = _format_direct_math_body(verified, user_text, fences, answer, display_answer)
        if physics_working:
            body = f"{physics_working}\n\n{body}"
        scene_fence = f"```simulation\n{json.dumps(scenes[0], separators=(',', ':'))}\n```\n"
        return f"{body}\n{scene_fence}" if body.endswith("\n") else f"{body}\n\n{scene_fence}"
    body = _format_direct_math_body(verified, user_text, fences, answer, display_answer)
    return f"{physics_working}\n\n{body}" if physics_working else body


def _format_direct_math_body(
    verified: VerifiedMathBlock,
    user_text: str,
    fences: list[dict[str, object]],
    answer: str,
    display_answer: str,
) -> str:
    if len(fences) == 1 and fences[0].get("relative_lengths") is True:
        return f"```geometry\n{json.dumps(fences[0], separators=(',', ':'))}\n```\n"
    if len(fences) == 1 and fences[0].get("type") in {
        "function",
        "inequality",
        "vertical",
        "trajectory",
    }:
        # The mobile stream scanner needs the newline after the closing fence
        # to render the graph immediately, before the done event arrives.
        graph_reply = f"```graph\n{json.dumps(fences[0], separators=(',', ':'))}\n```\n"
        if answer:
            return f"```answer\n{display_answer}\n```\n\n{graph_reply}"
        return graph_reply
    if len(fences) == 1 and fences[0].get("type") in {
        "rectangle",
        "square",
        "triangle",
        "right_triangle",
        "triangle_sides",
        "parallelogram",
        "trapezoid",
        "circle",
        "sector",
    }:
        from app.modules.math.tools.direct_geometry_working import (
            format_direct_geometry_working,
        )

        working = format_direct_geometry_working(user_text, fences[0], answer)
        prefix = f"{working}\n\n" if working else ""
        return (
            f"{prefix}```answer\n{display_answer}\n```\n\n"
            "**Diagram**\n\n"
            f"```geometry\n{json.dumps(fences[0], separators=(',', ':'))}\n```\n"
        )
    if len(fences) == 1 and fences[0].get("type") == "number_line":
        return (
            f"```answer\n{display_answer}\n```\n\n"
            f"```graph\n{json.dumps(fences[0], separators=(',', ':'))}\n```\n"
        )
    # The answer fence already typesets the result. Emitting a second math
    # paragraph repeats the same answer on the phone. The final newline also
    # lets the streaming client close and render this fence immediately.
    from app.modules.math.tools.direct_geometry_working import format_direct_solid_working

    solid_working = format_direct_solid_working(user_text, answer)
    prefix = f"{solid_working}\n\n" if solid_working else ""
    return f"{prefix}```answer\n{display_answer}\n```\n"


def maybe_direct_math_reply(
    verified: VerifiedMathBlock | None,
    user_text: str,
    *,
    has_image_attachment: bool = False,
    response_style: str = "balanced",
) -> str | None:
    if verified is None:
        return None
    if verified.direct_reply is not None:
        # Rendered by the builder from verified data (check my work). With a
        # photo attached the model reads it, so the image is not ignored.
        return None if has_image_attachment else verified.direct_reply
    if not can_direct_verified_math_reply(
        verified,
        user_text,
        has_image_attachment=has_image_attachment,
        response_style=response_style,
    ):
        return None
    reply = format_direct_math_reply(verified, user_text)
    if should_render_equation_lesson(verified, user_text, response_style):
        reply = format_equation_lesson_reply(
            verified,
            include_check=response_style == "detailed",
            include_reasons=(
                response_style == "detailed" or wants_detailed_math_explanation(user_text)
            ),
        )
    if (
        verified.physics_intent is not None
        and verified.physics_intent.kind == "kinematics"
        and verified.physics_intent.physics_op in {"velocity", "acceleration"}
    ):
        return f"Upward is positive.\n\n{reply}"
    return reply
