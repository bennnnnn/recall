"""Structured math I/O — validated before SymPy and fence emission."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class MathIntent(BaseModel):
    kind: Literal[
        "equation",
        "rectangle",
        "square",
        "triangle",
        "right_triangle",
        "circle",
        "point",
        "graph",
        "vertical",
        "calculus",
        "limit",
        "series",
        "system",
        "numerical_method",
        "inequality",
        "statistics",
        "combinatorics",
        "number_theory",
        "matrix",
        "triangle_sides",
        "trapezoid",
        "parallelogram",
        "sector",
        "graph_pair",
        "solid",
        "arithmetic",
        "trig",
        "coord",
        "vector",
        "probability",
        "complex",
        "unit",
    ]
    lhs: str | None = None
    rhs: str | None = None
    expr: str | None = None
    variable: str = "x"
    # Inequality comparator (canonical: "<", ">", "<=", ">=") — only set when
    # kind == "inequality". For compound ``low OP mid OP high``, ``comparator``
    # is the lower op and ``comparator_upper`` the upper; ``lower`` holds the
    # low bound and ``lhs``/``rhs`` are mid/high.
    comparator: str | None = None
    comparator_upper: str | None = None
    lower: str | None = None
    width: float | None = None
    height: float | None = None
    base: float | None = None
    side: float | None = None
    radius: float | None = None
    point_x: float | None = None
    point_y: float | None = None
    unit: str = "cm"
    operation: (
        Literal[
            "solve",
            "simplify",
            "differentiate",
            "integrate",
            "factor",
            "expand",
            "graph",
            "limit",
            "series",
            "newton",
            "taylor",
            "partial",
            "dsolve",
        ]
        | None
    ) = None
    # Limit/series bounds — strings, not float, since "infinity"/"oo" is a
    # valid bound alongside a plain number (see
    # math_service._parse_infinity_aware_point).
    limit_point: str | None = None
    series_start: str | None = None
    series_end: str | None = None
    # Definite-integral bounds — strings (infinity-aware, like limit_point).
    integral_lower: str | None = None
    integral_upper: str | None = None
    # System of equations — list of (lhs, rhs) pairs; `lhs`/`rhs`/`variable`
    # above stay single-equation-only for every other kind.
    system_equations: list[tuple[str, str]] | None = None
    system_variables: list[str] | None = None
    # Newton's method starting point — `expr` above holds f(x) (already
    # converted from "lhs = rhs" to "lhs - rhs" if needed).
    newton_guess: float | None = None
    # Which rectangle quantities the user's own wording actually asked for —
    # lets the rectangle augmentation only annotate the diagram with what was
    # requested instead of always drawing a diagonal + angle.
    wants_diagonal: bool = False
    wants_angle: bool = False
    wants_area: bool = False
    wants_perimeter: bool = False
    # Same idea for circles: only annotate diameter/circumference when asked.
    wants_diameter: bool = False
    wants_circumference: bool = False
    # Statistics — a raw data list (mean/median/mode/stdev/variance). The
    # sample_* variants use the (n-1) divisor; the bare "stdev"/"variance"
    # ops use the population divisor (the historical default).
    stats_op: (
        Literal["mean", "median", "mode", "variance", "stdev", "sample_stdev", "sample_variance"]
        | None
    ) = None
    stats_numbers: list[float] | None = None
    # Combinatorics — factorial (k unused) / combinations / permutations.
    combo_op: Literal["factorial", "combinations", "permutations"] | None = None
    combo_n: int | None = None
    combo_k: int | None = None
    # Number theory — gcd/lcm/mod take a and b; factorize/is_prime take a only.
    numtheory_op: Literal["gcd", "lcm", "factorize", "is_prime", "mod"] | None = None
    numtheory_a: int | None = None
    numtheory_b: int | None = None
    # Matrix — determinant/inverse of a small square matrix.
    matrix_op: Literal["determinant", "inverse"] | None = None
    matrix_rows: list[list[float]] | None = None
    # Triangle by three side lengths (SSS) — `base`/`side` above stay
    # base+height-only for the existing "triangle"/"right_triangle" kinds.
    tri_a: float | None = None
    tri_b: float | None = None
    tri_c: float | None = None
    # Trapezoid — reuses `height` above; top/bottom are new.
    trapezoid_top: float | None = None
    trapezoid_bottom: float | None = None
    # Parallelogram/sector reuse `base`/`height`/`side`/`radius` above.
    sector_angle_deg: float | None = None
    # Second function for a "graph y=x^2 and y=2x" comparison plot — `expr`/
    # `variable` above hold the first curve, unchanged for every other kind.
    expr2: str | None = None
    # Graph domain the user named ("graph y=x^2 from 0 to 100"). When set, the
    # verified graph block samples on this x-range instead of the [-10, 10]
    # default. None means "use the default window".
    graph_x_min: float | None = None
    graph_x_max: float | None = None
    # 3D solids — volume / surface area. Reuses width/height/side/radius;
    # depth is the third prism (or rectangular-pyramid) edge.
    solid_shape: (
        Literal["cube", "rectangular_prism", "cylinder", "cone", "sphere", "pyramid"] | None
    ) = None
    depth: float | None = None
    wants_volume: bool = False
    wants_surface_area: bool = False
    # School extras (arithmetic / coord / vectors / probability / units).
    school_op: str | None = None
    x2: float | None = None
    y2: float | None = None
    vec_a: list[float] | None = None
    vec_b: list[float] | None = None
    percent_rate: float | None = None
    percent_base: float | None = None
    unit_from: str | None = None
    unit_to: str | None = None
    taylor_n: int | None = None
