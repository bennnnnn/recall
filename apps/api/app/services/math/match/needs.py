"""When a chat turn should hit pre-stream SymPy."""

from __future__ import annotations

import re

from app.services.math.match.calculus import (
    calc_op,
    parse_limit,
    parse_series,
    y_prime_math_cue,
)
from app.services.math.match.discrete import (
    combinatorics_signal,
    matrix_signal,
    number_theory_signal,
    stats_signal,
)
from app.services.math.match.geometry import (
    parse_solid,
    triangle_angles_signal,
    triangle_sides_signal,
)
from app.services.math.match.graph import (
    bare_coord,
    graph_expr,
    plot_point,
    vertical_line_x,
)
from app.services.math.match.scan import (
    bare_arithmetic_expr,
    first_dim_pair,
    geometry_dim_context,
    has_algebraic_equation,
    has_draw_shape,
    has_equation,
    has_math_keyword,
    inequality_signal,
    number_after,
    prepare,
    two_numbers_after,
    word_index,
)
from app.services.math.match.statistics import bivariate_stats_signal


def needs_symbolic(text: str, *, has_image_attachment: bool = False) -> bool:
    cleaned = prepare(text)
    if cleaned is None:
        return False
    if not cleaned and not has_image_attachment:
        return False
    from app.services.math.image_extract import is_math_camera_prompt

    if has_image_attachment and is_math_camera_prompt(cleaned):
        return True
    lower = cleaned.lower()
    if (
        has_draw_shape(lower, "rectangle")
        or has_draw_shape(lower, "right triangle")
        or has_draw_shape(lower, "square")
        or has_draw_shape(lower, "circle")
        or has_draw_shape(lower, "trapezoid")
        or has_draw_shape(lower, "trapezium")
        or has_draw_shape(lower, "parallelogram")
        or has_draw_shape(lower, "sector")
        or has_draw_shape(lower, "pie slice")
        or has_draw_shape(lower, "triangle")
    ):
        return True
    # Shape words alone must NOT trigger verified geometry — bare
    # "what is a trapezoid?" used to invent dimensions and sell them as
    # SymPy-verified. Require printed measures (or the draw gates above).
    if ("trapezoid" in lower or "trapezium" in lower) and (
        number_after(cleaned, "top") is not None
        and number_after(cleaned, "bottom") is not None
        and number_after(cleaned, "height") is not None
    ):
        return True
    if "parallelogram" in lower and (
        number_after(cleaned, "base") is not None and number_after(cleaned, "height") is not None
    ):
        return True
    # "sector" alone is an ordinary English word ("the tech sector") far
    # more often than a circle sector — require geometry context AND both
    # radius + angle (partial dims used to invent the missing one).
    if (
        "sector" in lower
        and any(k in lower for k in ("circle", "radius", "pie", "arc"))
        and number_after(cleaned, "radius") is not None
        and number_after(cleaned, "angle") is not None
    ):
        return True
    if triangle_sides_signal(cleaned) is not None:
        return True
    if triangle_angles_signal(cleaned) is not None:
        return True
    if parse_solid(cleaned) is not None:
        return True
    if has_image_attachment and has_math_keyword(lower):
        return True
    if has_equation(cleaned) and has_math_keyword(lower):
        return True
    # Bare algebraic equation with no verb — "2x+3=7" / "y=x^2". The
    # equation extractor already handles these, but the gate used to require
    # a math keyword too, so a bare equation shipped unverified (or the model
    # emitted its own wrong spec). has_algebraic_equation requires a standalone
    # single-letter variable so prose with an '=' ("meeting = 3pm") is excluded.
    if has_algebraic_equation(cleaned):
        return True
    # Digits + operators with no leftover English — same helper the arithmetic
    # extractor uses. Without this, ``first_dim_pair`` treated ``8*2`` inside
    # ``8-8*2`` as a rectangle size, extract returned None, and the reply
    # stamped *Couldn't verify this with SymPy.* under a correct -8.
    if bare_arithmetic_expr(cleaned) is not None:
        return True
    if "=" in cleaned:
        from app.services.math.tools.helpers import substituted_eval_expr

        if substituted_eval_expr(cleaned) is not None:
            return True
    if geometry_dim_context(lower):
        from app.services.math.match.units import strip_geometry_length_units

        if first_dim_pair(strip_geometry_length_units(cleaned)) is not None:
            return True
    if (
        "circle" in lower
        and "sector" not in lower
        and "pie slice" not in lower
        and (
            number_after(cleaned, "radius") is not None
            or number_after(cleaned, "diameter") is not None
        )
    ):
        return True
    if "triangle" in lower and (
        number_after(cleaned, "base") is not None and number_after(cleaned, "height") is not None
    ):
        return True
    if word_index(lower, "square") != -1:
        from app.services.math.tools.extractors.geometry_graph import _extract_square_intent

        if _extract_square_intent(cleaned) is not None:
            return True
    if "right triangle" in lower and (
        first_dim_pair(cleaned) is not None
        or two_numbers_after(cleaned, "legs") is not None
        or two_numbers_after(cleaned, "leg") is not None
    ):
        return True
    if bare_coord(cleaned) is not None or plot_point(cleaned) is not None:
        return True
    if graph_expr(cleaned) is not None:
        return True
    if vertical_line_x(cleaned) is not None:
        return True
    # 1-variable inequality on a number line ("x > 4", "1 < x < 5") — the
    # inequality extractor already exists, but the gate used to require a
    # math keyword, so bare "X>4" never reached it and the model emitted
    # "Could not render that diagram." with no verified fence.
    if inequality_signal(cleaned):
        return True
    # Domain/range/inverse/composition are not ordinary calculus command words,
    # so route them only when the dedicated extractor can consume the whole ask.
    if any(
        cue in lower
        for cue in ("domain of", "range of", "inverse function", "inverse of", "compose")
    ):
        from app.services.math.tools.extractors.functions import _extract_function_analysis_intent

        if _extract_function_analysis_intent(cleaned) is not None:
            return True
    if calc_op(cleaned) is not None:
        return True
    if any(cue in lower for cue in ("critical point", "extrema", "local max", "local min")):
        from app.services.math.tools.extractors.calculus import _extract_critical_points_intent

        critical = _extract_critical_points_intent(cleaned)
        if critical is not None and critical.expr:
            return True
    if parse_limit(cleaned) is not None:
        return True
    if parse_series(cleaned) is not None:
        return True
    if any(ch.isdigit() for ch in cleaned) and (
        word_index(lower, "newton") != -1
        or word_index(lower, "numerically") != -1
        or word_index(lower, "root of") != -1
    ):
        return True
    if "solve" in lower and has_equation(cleaned):
        return True
    # "find x if 2x + 3 = 7" / "find the value of x in 2x = 10" — "find" + an
    # equation is a solve ask just like "solve …". Without this, a bare
    # "find x when 2x = 10" fell through (no "solve" keyword) and shipped
    # unverified. Requires an equation so prose "find the right moment" is
    # not pulled into SymPy.
    if "find" in lower and has_equation(cleaned):
        return True
    # "roots of x^2 - 4" / "zeros of x^2 - 1" — a polynomial-roots ask with no
    # "=". Require a digit so English "roots of the tree" / "zeros of the
    # array" is not mistaken for algebra (the extractor rewrites these to
    # "solve <expr> = 0" when it runs).
    if ("roots of" in lower or "zeros of" in lower) and any(ch.isdigit() for ch in cleaned):
        return True
    if (
        "evaluate" in lower
        and any(ch.isdigit() for ch in cleaned)
        and any(op in cleaned for op in ("+", "-", "*", "/", "^", "("))
    ):
        return True
    if stats_signal(cleaned) is not None or bivariate_stats_signal(cleaned) is not None:
        return True
    if combinatorics_signal(cleaned) is not None:
        return True
    if number_theory_signal(cleaned) is not None:
        return True
    if matrix_signal(cleaned) is not None:
        return True
    if supported_physics_cue(cleaned):
        return True
    if school_homework_cue(cleaned):
        return True
    return has_math_keyword(lower) and has_equation(cleaned)


# A handful of verified questions carry no number at all, because the numbers
# are the body's own: "what is the escape velocity from earth". The digit rule
# below is what keeps the physics cues cheap, so this is an explicit short list
# rather than a relaxation of it - each phrase is unambiguous physics, and the
# extractor still refuses anything it cannot resolve.
_DIGIT_FREE_PHYSICS_RE = re.compile(
    r"\b(?:escape velocity|escape speed|orbital velocity|orbital speed|"
    r"surface gravity|gravitational field strength)\b"
    r"[^.?!]{0,60}?\b(?:earth|moon|mars|jupiter|sun)\b"
    r"|\b(?:earth|moon|mars|jupiter|sun)\b[^.?!]{0,60}?"
    r"\b(?:escape velocity|escape speed|orbital velocity|orbital speed|"
    r"surface gravity|gravitational field strength)\b",
    re.IGNORECASE,
)


def supported_physics_cue(cleaned: str) -> bool:
    """A numeric problem supported by the narrow verified physics solver."""
    if not any(ch.isdigit() for ch in cleaned):
        return _DIGIT_FREE_PHYSICS_RE.search(cleaned) is not None
    from app.services.physics.extract import has_supported_physics_cue

    # Not lowercased: a few physics cues mean the SI symbols `V` and `A` and
    # are case-sensitive on purpose. Lowercasing here made them dead in the
    # pre-filter while the extractor kept honouring them.
    return has_supported_physics_cue(cleaned)


def _has_ordinal_term_cue(lower: str) -> bool:
    i = 0
    n = len(lower)
    while i < n:
        if lower[i].isdigit():
            if i > 0 and lower[i - 1] == ".":
                i += 1
                continue
            j = i
            while j < n and lower[j].isdigit():
                j += 1
            if lower[j : j + 2] in {"st", "nd", "rd", "th"}:
                k = j + 2
                while k < n and lower[k].isspace():
                    k += 1
                if lower.startswith("term", k):
                    return True
            i = j
        else:
            i += 1
    return False


def school_homework_cue(cleaned: str) -> bool:
    """Bare arithmetic / percent / coord / vectors / convert / binomial / ODE."""
    lower = cleaned.lower()
    if "% of " in lower and any(ch.isdigit() for ch in cleaned):
        return True
    has_digit = any(ch.isdigit() for ch in cleaned)
    if (
        has_digit
        and "%" in cleaned
        and any(
            word_index(lower, word) != -1
            for word in ("increase", "increased", "decrease", "decreased")
        )
    ):
        return True
    if has_digit and ("what percent" in lower or "what percentage" in lower):
        return True
    if (
        has_digit
        and "ratio" in lower
        and ":" in cleaned
        and any(word_index(lower, word) != -1 for word in ("split", "share", "divide"))
    ):
        return True
    if has_digit and _has_ordinal_term_cue(lower):
        return True
    if "sum of the first" in lower or "sum of first" in lower:
        if word_index(lower, "even") != -1 or word_index(lower, "odd") != -1:
            return True
        if "," in cleaned:
            return True
    if (
        has_digit
        and "%" in cleaned
        and (
            "compound interest" in lower or "simple interest" in lower or "compound amount" in lower
        )
    ):
        return True
    if "{" in cleaned and any(
        word_index(lower, word) != -1 for word in ("union", "intersection", "difference")
    ):
        return True
    if has_equation(cleaned) and (
        "identity" in lower
        or "show that" in lower
        or "prove that" in lower
        or "verify that" in lower
    ):
        return True
    compact = lower.replace(" ", "")
    polar_plot = any(
        word_index(lower, word) != -1 for word in ("graph", "plot", "polar", "sketch", "draw")
    )
    if "r=" in compact and ("polar" in lower or "theta" in lower or "θ" in cleaned) and polar_plot:
        return True
    if (
        "x=" in compact
        and "y=" in compact
        and (
            "parametric" in lower
            or word_index(lower, "graph") != -1
            or word_index(lower, "plot") != -1
        )
    ):
        return True
    if word_index(lower, "together") != -1 and "hour" in lower and has_digit:
        return True
    if (
        has_digit
        and cleaned.count("%") == 2
        and "% of " not in lower
        and any(word_index(lower, word) != -1 for word in ("mix", "mixed", "mixture"))
    ):
        return True
    if (
        has_digit
        and ("twice as many" in lower or "2 times as many" in lower)
        and (word_index(lower, "together") != -1)
    ):
        return True
    if (
        has_digit
        and "%" in cleaned
        and (
            word_index(lower, "tax") != -1
            or word_index(lower, "tip") != -1
            or word_index(lower, "discount") != -1
            or word_index(lower, "off") != -1
            or word_index(lower, "markup") != -1
        )
    ):
        return True
    if has_digit and ("percent change from" in lower or "percentage change from" in lower):
        return True
    if has_digit and ("direct proportion" in lower or "inverse proportion" in lower):
        return True
    if has_digit and word_index(lower, "cost") != -1 and word_index(lower, "if") != -1:
        return True
    if (
        has_digit
        and word_index(lower, "round") != -1
        and ("decimal" in lower or "significant" in lower)
    ):
        return True
    if "present value" in lower and has_digit:
        return True
    if ("infinity" in lower or "infinite" in lower) and ("sum" in lower or "series" in lower):
        return True
    if "equation of" in lower and "line" in lower and "(" in cleaned:
        return True
    if word_index(lower, "distance") != -1 and "(" in cleaned and "=" in cleaned:
        return True
    if (
        any(w in lower for w in ("unit vector", "projection of", "angle between"))
        and "<" in cleaned
    ):
        return True
    if "geometric" in lower and "k=" in lower.replace(" ", ""):
        return True
    if "poisson" in lower:
        return True
    if word_index(lower, "bayes") != -1 or word_index(lower, "complement") != -1:
        return True
    if any(
        word_index(lower, word) != -1
        for word in ("quartiles", "percentile", "iqr", "interquartile")
    ):
        return True
    if "range of" in lower and "," in cleaned:
        return True
    if "modular inverse" in lower or ("totient" in lower and has_digit):
        return True
    if "chinese remainder" in lower or word_index(lower, "crt") != -1:
        return True
    if "transpose" in lower and "[[" in cleaned:
        return True
    if word_index(lower, "add") != -1 and "[[" in cleaned:
        return True
    if any(
        word in lower
        for word in (
            "gradient",
            "directional derivative",
            "divergence",
            "curl",
            "average value",
            "linear approximation",
            "implicit",
            "triple integral",
        )
    ):
        return True
    if "area" in lower and "triangle" in lower and "angle" in lower and "sides" in lower:
        return True
    if "average speed" in lower or "average velocity" in lower:
        from app.services.math.tools.school import _extract_average_speed_intent

        if _extract_average_speed_intent(cleaned) is not None:
            return True
    if "convert" in lower and " to " in lower and any(ch.isdigit() for ch in cleaned):
        return True
    if any(w in lower for w in ("midpoint", "distance between", "slope of")) and "(" in cleaned:
        return True
    if any(w in lower for w in ("dot product", "cross product", "magnitude of <")):
        return True
    if "binomial" in lower or "expected value" in lower:
        return True
    if "taylor of " in lower or "maclaurin" in lower or ("taylor" in lower and "series" in lower):
        return True
    if "partial of " in lower or "partial derivative" in lower or " wrt" in lower:
        return True
    if "dy/dx" in lower or "day/dx" in lower or y_prime_math_cue(cleaned):
        return True
    if "modulus" in lower or "imaginary" in lower or "complex number" in lower:
        return True
    if bare_arithmetic_expr(cleaned) is not None:
        return True
    has_trig_call = any(f"{fn}(" in lower or f"{fn} " in lower for fn in ("sin", "cos", "tan"))
    if has_trig_call and ("\u00b0" in cleaned or any(ch.isdigit() for ch in cleaned)):
        return True
    return False
