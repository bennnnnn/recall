"""When a chat turn should hit pre-stream SymPy."""

from __future__ import annotations

from app.services.math_text_match.calculus import calc_op, parse_limit, parse_series
from app.services.math_text_match.discrete import (
    combinatorics_signal,
    matrix_signal,
    number_theory_signal,
    stats_signal,
)
from app.services.math_text_match.geometry import (
    parse_solid,
    triangle_angles_signal,
    triangle_sides_signal,
)
from app.services.math_text_match.graph import (
    bare_coord,
    graph_expr,
    plot_point,
    vertical_line_x,
)
from app.services.math_text_match.scan import (
    first_dim_pair,
    has_draw_shape,
    has_equation,
    has_math_keyword,
    number_after,
    prepare,
)


def needs_symbolic(text: str, *, has_image_attachment: bool = False) -> bool:
    cleaned = prepare(text)
    if cleaned is None:
        return False
    if not cleaned and not has_image_attachment:
        return False
    from app.services.math_image_extract import is_math_camera_prompt

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
    if first_dim_pair(cleaned) is not None:
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
    if "right triangle" in lower and first_dim_pair(cleaned) is not None:
        return True
    if bare_coord(cleaned) is not None or plot_point(cleaned) is not None:
        return True
    if graph_expr(cleaned) is not None:
        return True
    if vertical_line_x(cleaned) is not None:
        return True
    if calc_op(cleaned) is not None:
        return True
    if parse_limit(cleaned) is not None:
        return True
    if parse_series(cleaned) is not None:
        return True
    if "newton" in lower or "numerically" in lower or "root of" in lower:
        return True
    if "solve" in lower and has_equation(cleaned):
        return True
    if stats_signal(cleaned) is not None:
        return True
    if combinatorics_signal(cleaned) is not None:
        return True
    if number_theory_signal(cleaned) is not None:
        return True
    if matrix_signal(cleaned) is not None:
        return True
    if school_homework_cue(cleaned):
        return True
    return has_math_keyword(lower) and has_equation(cleaned)


def school_homework_cue(cleaned: str) -> bool:
    """Bare arithmetic / percent / coord / vectors / convert / binomial / ODE."""
    lower = cleaned.lower()
    if "% of " in lower and any(ch.isdigit() for ch in cleaned):
        return True
    if "convert" in lower and " to " in lower and any(ch.isdigit() for ch in cleaned):
        return True
    if any(w in lower for w in ("midpoint", "distance between", "slope of")) and "(" in cleaned:
        return True
    if any(w in lower for w in ("dot product", "cross product", "magnitude of <")):
        return True
    if "binomial" in lower or "expected value" in lower:
        return True
    if "taylor" in lower or "partial" in lower or "dy/dx" in lower:
        return True
    if "complex" in lower or "modulus" in lower:
        return True
    times = "\u00d7"
    divide = "\u00f7"
    if "what is" in lower and any(op in cleaned for op in ("+", "-", "*", "/", times, divide, "^")):
        if any(ch.isdigit() for ch in cleaned):
            return True
    has_trig_call = any(f"{fn}(" in lower or f"{fn} " in lower for fn in ("sin", "cos", "tan"))
    if has_trig_call and ("\u00b0" in cleaned or any(ch.isdigit() for ch in cleaned)):
        return True
    return False
