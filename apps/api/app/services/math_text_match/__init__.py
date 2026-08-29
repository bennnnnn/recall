"""Linear (non-regex / digit-only-regex) matchers for math intent heuristics.

Kept separate so CodeQL py/polynomial-redos cannot taint user chat text into
nested optional/``\\s`` regex pumps in ``math_tools``.
"""

from __future__ import annotations

from app.services.math_text_match.calculus import (
    calc_op,
    integral_bounds,
    parse_limit,
    parse_series,
)
from app.services.math_text_match.discrete import (
    combinatorics_signal,
    matrix_signal,
    number_theory_signal,
    stats_signal,
)
from app.services.math_text_match.geometry import (
    _first_positive_number as _first_positive_number,
)
from app.services.math_text_match.geometry import (
    classify_solid_shape,
    geometry_deferred_for_algebra,
    parse_solid,
    solid_homework_cue,
    triangle_angles_signal,
    triangle_sides_signal,
)
from app.services.math_text_match.graph import (
    _parse_xy_pair as _parse_xy_pair,
)
from app.services.math_text_match.graph import (
    bare_coord,
    graph_domain,
    graph_expr,
    graph_expr_pair,
    plot_point,
    vertical_line_x,
)
from app.services.math_text_match.needs import needs_symbolic, school_homework_cue
from app.services.math_text_match.scan import (
    _NUM as _NUM,
)
from app.services.math_text_match.scan import (
    first_dim_pair,
    first_dim_triple,
    has_draw_shape,
    has_equation,
    has_math_keyword,
    number_after,
    prepare,
    two_numbers_after,
)
from app.services.math_text_match.types import (
    CombinatoricsOp,
    MatrixOp,
    NumberTheoryOp,
    SolidShape,
    StatsOp,
)

__all__ = [
    "CombinatoricsOp",
    "MatrixOp",
    "NumberTheoryOp",
    "SolidShape",
    "StatsOp",
    "bare_coord",
    "calc_op",
    "classify_solid_shape",
    "combinatorics_signal",
    "first_dim_pair",
    "first_dim_triple",
    "geometry_deferred_for_algebra",
    "graph_domain",
    "graph_expr",
    "graph_expr_pair",
    "has_draw_shape",
    "has_equation",
    "has_math_keyword",
    "integral_bounds",
    "matrix_signal",
    "needs_symbolic",
    "number_after",
    "number_theory_signal",
    "parse_limit",
    "parse_series",
    "parse_solid",
    "plot_point",
    "prepare",
    "school_homework_cue",
    "solid_homework_cue",
    "stats_signal",
    "triangle_angles_signal",
    "triangle_sides_signal",
    "two_numbers_after",
    "vertical_line_x",
]
