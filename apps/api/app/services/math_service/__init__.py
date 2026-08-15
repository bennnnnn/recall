"""Symbolic math via SymPy — server-side only."""

from __future__ import annotations

from app.services.math_service.algebra import (
    compute_limit,
    differentiate_expression,
    evaluate_series_sum,
    expand_expression,
    factor_expression,
    integrate_definite,
    integrate_expression,
    newton_method,
    simplify_expression,
    solve_compound_inequality,
    solve_equation,
    solve_inequality,
    solve_system,
)
from app.services.math_service.discrete import (
    compute_combinatorics,
    compute_matrix,
    compute_number_theory,
    compute_statistics,
    guess_variables,
)
from app.services.math_service.extract_eq import (
    try_extract_compound_inequality_from_text,
    try_extract_equation_from_text,
    try_extract_equations_from_text,
    try_extract_inequality_from_text,
)
from app.services.math_service.geometry import (
    circle_geometry,
    format_degree_label,
    parallelogram_geometry,
    rectangle_geometry,
    right_triangle_geometry,
    sector_geometry,
    sides_from_interior_angles,
    solid_geometry,
    square_geometry,
    trapezoid_geometry,
    triangle_geometry,
    triangle_sides_geometry,
)
from app.services.math_service.graph import (
    build_ellipse_graph_spec,
    expr_looks_like_inequality,
    number_line_spec_from_expr,
    parse_ellipse_relation,
    sample_ellipse,
    sample_function,
)
from app.services.math_service.parse import (
    _SAFE_EXPR_CHARS as _SAFE_EXPR_CHARS,
)
from app.services.math_service.parse import (
    MathServiceError as MathServiceError,
)
from app.services.math_service.parse import (
    _normalize_latex_to_sympy as _normalize_latex_to_sympy,
)
from app.services.math_service.parse import (
    _parse_expression as _parse_expression,
)
from app.services.math_service.parse import (
    parse_equation as parse_equation,
)

__all__ = [
    "_SAFE_EXPR_CHARS",
    "MathServiceError",
    "_normalize_latex_to_sympy",
    "_parse_expression",
    "build_ellipse_graph_spec",
    "circle_geometry",
    "compute_combinatorics",
    "compute_limit",
    "compute_matrix",
    "compute_number_theory",
    "compute_statistics",
    "differentiate_expression",
    "evaluate_series_sum",
    "expand_expression",
    "expr_looks_like_inequality",
    "factor_expression",
    "format_degree_label",
    "guess_variables",
    "integrate_definite",
    "integrate_expression",
    "newton_method",
    "number_line_spec_from_expr",
    "parallelogram_geometry",
    "parse_ellipse_relation",
    "parse_equation",
    "rectangle_geometry",
    "right_triangle_geometry",
    "sample_ellipse",
    "sample_function",
    "sector_geometry",
    "sides_from_interior_angles",
    "simplify_expression",
    "solid_geometry",
    "solve_compound_inequality",
    "solve_equation",
    "solve_inequality",
    "solve_system",
    "square_geometry",
    "trapezoid_geometry",
    "triangle_geometry",
    "triangle_sides_geometry",
    "try_extract_compound_inequality_from_text",
    "try_extract_equation_from_text",
    "try_extract_equations_from_text",
    "try_extract_inequality_from_text",
]
