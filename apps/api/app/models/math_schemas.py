"""Structured math I/O — validated before SymPy and fence emission."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EquationInput(BaseModel):
    lhs: str = Field(min_length=1, max_length=256)
    rhs: str = Field(min_length=1, max_length=256)
    variables: list[str] = Field(default_factory=lambda: ["x"], min_length=1, max_length=4)


class SystemOfEquationsInput(BaseModel):
    # Each entry is one equation's (lhs, rhs) pair — bounded the same as
    # EquationInput's individual lhs/rhs fields. 2-4 equations: fewer isn't
    # a system, more isn't realistically something a chat turn hand-solves.
    equations: list[tuple[str, str]] = Field(min_length=2, max_length=4)
    variables: list[str] = Field(default_factory=lambda: ["x", "y"], min_length=1, max_length=4)

    @field_validator("equations")
    @classmethod
    def equation_sides_bounded(cls, value: list[tuple[str, str]]) -> list[tuple[str, str]]:
        for lhs, rhs in value:
            if not lhs.strip() or not rhs.strip() or len(lhs) > 256 or len(rhs) > 256:
                raise ValueError("invalid equation side")
        return value


_VALID_INEQUALITY_COMPARATORS = frozenset({"<", ">", "<=", ">="})


class MathImageExtract(BaseModel):
    """Vision-extracted equation from a photo (validated before SymPy).

    `lhs`/`rhs` always hold the first (or only) equation/inequality side —
    every caller that only ever handled a single equation keeps working
    unchanged. `kind` plus `equations`/`comparator` are additive: a
    photographed SYSTEM or INEQUALITY gets the same SymPy-verified path a
    single equation already does, instead of silently falling back to
    unverified free-text the moment the photo has more than one equation."""

    kind: Literal["equation", "system", "inequality"] = "equation"
    lhs: str = Field(min_length=1, max_length=256)
    rhs: str = Field(min_length=1, max_length=256)
    variables: list[str] = Field(default_factory=lambda: ["x"], min_length=1, max_length=4)
    found: bool = True
    # kind == "system": every equation in the system as (lhs, rhs) pairs,
    # INCLUDING the first (so this is self-contained — callers don't need
    # to merge it with lhs/rhs above).
    equations: list[tuple[str, str]] | None = None
    # kind == "inequality": canonical comparator applied to lhs/rhs above.
    comparator: str | None = None

    @model_validator(mode="after")
    def normalize_kind(self) -> MathImageExtract:
        # Best-effort OCR hint from a vision model — a malformed/incomplete
        # kind must degrade gracefully to the single-equation case (which
        # only needs lhs/rhs, always present) rather than fail the whole
        # extraction and lose the camera-math verified path entirely.
        if self.kind == "system" and (not self.equations or len(self.equations) < 2):
            self.kind = "equation"
        if self.kind == "inequality" and self.comparator not in _VALID_INEQUALITY_COMPARATORS:
            self.kind = "equation"
        return self


class MathSolveResult(BaseModel):
    solutions_latex: list[str]
    steps: list[str] = Field(default_factory=list)
    lhs_latex: str = ""
    rhs_latex: str = ""
    # "none"/"infinite" only apply when solutions_latex is empty — distinguishes
    # a genuine contradiction (no solution) from a tautology (every value
    # satisfies the equation), which used to collapse into one ambiguous string.
    solution_kind: Literal["finite", "none", "infinite"] = "finite"


class MathSystemSolveResult(BaseModel):
    # One dict of {variable: value_latex} per solution set — usually one for
    # a linear system, but sympy.solve on a nonlinear system can return
    # several (e.g. two intersection points).
    solutions: list[dict[str, str]] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    solution_kind: Literal["finite", "none", "infinite"] = "finite"


class NewtonMethodInput(BaseModel):
    expr: str = Field(min_length=1, max_length=256)
    variable: str = Field(default="x", min_length=1, max_length=8)
    initial_guess: float = Field(default=1.0, ge=-1_000_000, le=1_000_000)
    tolerance: float = Field(default=1e-6, gt=0, le=1)
    # Capped low: this bounds real per-request iteration work, not something
    # a user-supplied "solve to N decimal places" should ever need to raise.
    max_iterations: int = Field(default=50, ge=1, le=200)


class NewtonIterationStep(BaseModel):
    n: int
    x_n: float
    f_x_n: float


class NewtonMethodResult(BaseModel):
    iterations: list[NewtonIterationStep] = Field(default_factory=list)
    converged: bool
    root: float | None = None
    iterations_used: int


class MathExprResult(BaseModel):
    result: str
    latex: str
    # False when SymPy couldn't find a closed form (integrate_expression can
    # return a literal unevaluated Integral(...) rather than raising) — the
    # verified block must not assert an unsolved expression as a fact.
    solved: bool = True


class MathLimitResult(BaseModel):
    result: str
    latex: str
    # True for oo/-oo (diverges) or zoo (two-sided limit doesn't exist
    # because the sides disagree) — lets the verified block render this as
    # \infty explicitly instead of leaving an opaque symbol name.
    is_infinite: bool


class MathSeriesResult(BaseModel):
    result: str
    latex: str
    is_infinite: bool
    # None when SymPy can't determine convergence (rare); otherwise a
    # definite True/False for whether the (typically infinite) series
    # converges, and separately whether it converges absolutely.
    is_convergent: bool | None = None
    is_absolutely_convergent: bool | None = None


class RectangleGeometryInput(BaseModel):
    width: float = Field(gt=0, le=1_000_000)
    height: float = Field(gt=0, le=1_000_000)
    unit: str = Field(default="cm", max_length=16)


class RectangleGeometryResult(BaseModel):
    width: float
    height: float
    unit: str
    diagonal: float
    angle_deg: float
    area: float
    perimeter: float
    labels: dict[str, str] = Field(default_factory=dict)


class SquareGeometryInput(BaseModel):
    side: float = Field(gt=0, le=1_000_000)
    unit: str = Field(default="cm", max_length=16)


class SquareGeometryResult(BaseModel):
    side: float
    unit: str
    diagonal: float
    area: float
    perimeter: float
    labels: dict[str, str] = Field(default_factory=dict)


class TriangleGeometryInput(BaseModel):
    base: float = Field(gt=0, le=1_000_000)
    height: float = Field(gt=0, le=1_000_000)
    unit: str = Field(default="cm", max_length=16)


class TriangleGeometryResult(BaseModel):
    base: float
    height: float
    unit: str
    area: float
    labels: dict[str, str] = Field(default_factory=dict)


class RightTriangleGeometryInput(BaseModel):
    base: float = Field(gt=0, le=1_000_000)
    height: float = Field(gt=0, le=1_000_000)
    unit: str = Field(default="cm", max_length=16)


class RightTriangleGeometryResult(BaseModel):
    base: float
    height: float
    unit: str
    hypotenuse: float
    area: float
    labels: dict[str, str] = Field(default_factory=dict)


class CircleGeometryInput(BaseModel):
    radius: float = Field(gt=0, le=1_000_000)
    unit: str = Field(default="cm", max_length=16)


class CircleGeometryResult(BaseModel):
    radius: float
    unit: str
    diameter: float
    area: float
    circumference: float
    labels: dict[str, str] = Field(default_factory=dict)


class TriangleSidesInput(BaseModel):
    """A triangle given by its three side lengths (SSS) rather than
    base+height — area via Heron's formula, angles via the law of cosines."""

    a: float = Field(gt=0, le=1_000_000)
    b: float = Field(gt=0, le=1_000_000)
    c: float = Field(gt=0, le=1_000_000)
    unit: str = Field(default="cm", max_length=16)

    @model_validator(mode="after")
    def valid_triangle(self) -> TriangleSidesInput:
        a, b, c = self.a, self.b, self.c
        if a + b <= c or a + c <= b or b + c <= a:
            raise ValueError("these three side lengths cannot form a triangle")
        return self


class TriangleSidesResult(BaseModel):
    a: float
    b: float
    c: float
    unit: str
    area: float
    perimeter: float
    # Angle opposite the side of the same letter.
    angle_a_deg: float
    angle_b_deg: float
    angle_c_deg: float
    labels: dict[str, str] = Field(default_factory=dict)


class TrapezoidInput(BaseModel):
    top: float = Field(gt=0, le=1_000_000)
    bottom: float = Field(gt=0, le=1_000_000)
    height: float = Field(gt=0, le=1_000_000)
    unit: str = Field(default="cm", max_length=16)


class TrapezoidResult(BaseModel):
    top: float
    bottom: float
    height: float
    unit: str
    area: float
    labels: dict[str, str] = Field(default_factory=dict)


class ParallelogramInput(BaseModel):
    base: float = Field(gt=0, le=1_000_000)
    height: float = Field(gt=0, le=1_000_000)
    side: float = Field(gt=0, le=1_000_000)
    unit: str = Field(default="cm", max_length=16)

    @model_validator(mode="after")
    def side_at_least_height(self) -> ParallelogramInput:
        # The slant side is the hypotenuse of the right triangle formed by
        # the height, so it can never be shorter than the height itself.
        if self.side < self.height:
            raise ValueError("side must be at least as long as height")
        return self


class ParallelogramResult(BaseModel):
    base: float
    height: float
    side: float
    unit: str
    area: float
    perimeter: float
    labels: dict[str, str] = Field(default_factory=dict)


class SectorInput(BaseModel):
    radius: float = Field(gt=0, le=1_000_000)
    angle_deg: float = Field(gt=0, le=360)
    unit: str = Field(default="cm", max_length=16)


class SectorResult(BaseModel):
    radius: float
    angle_deg: float
    unit: str
    arc_length: float
    area: float
    labels: dict[str, str] = Field(default_factory=dict)


class GraphSampleInput(BaseModel):
    expr: str = Field(min_length=1, max_length=256)
    variable: str = Field(default="x", min_length=1, max_length=8)
    x_min: float = -10.0
    x_max: float = 10.0
    n: int = Field(default=200, ge=10, le=500)


class GraphSampleResult(BaseModel):
    expr: str
    variable: str
    x_min: float
    x_max: float
    points: list[list[float]]
    # points split at likely vertical-asymptote gaps (see
    # math_service._split_into_segments) so a renderer can draw each as its
    # own polyline instead of one continuous line straight across a
    # discontinuity (e.g. tan(x) at pi/2). Kept alongside `points` (not
    # instead of) for back-compat with fences the model already knows how
    # to emit with only `points`.
    segments: list[list[list[float]]] = Field(default_factory=list)


class TriangleGeometryBlockSpec(BaseModel):
    type: Literal["triangle"] = "triangle"
    base: float = Field(gt=0, le=1_000_000)
    height: float = Field(gt=0, le=1_000_000)
    unit: str = "cm"
    show_labels: bool = True
    area: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class RightTriangleGeometryBlockSpec(BaseModel):
    type: Literal["right_triangle"] = "right_triangle"
    base: float = Field(gt=0, le=1_000_000)
    height: float = Field(gt=0, le=1_000_000)
    unit: str = "cm"
    show_labels: bool = True
    show_hypotenuse: bool = True
    show_angle: bool = True
    hypotenuse: float | None = None
    area: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class TriangleSidesGeometryBlockSpec(BaseModel):
    type: Literal["triangle_sides"] = "triangle_sides"
    a: float = Field(gt=0, le=1_000_000)
    b: float = Field(gt=0, le=1_000_000)
    c: float = Field(gt=0, le=1_000_000)
    unit: str = "cm"
    show_labels: bool = True
    area: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_triangle(self) -> TriangleSidesGeometryBlockSpec:
        a, b, c = self.a, self.b, self.c
        if a + b <= c or a + c <= b or b + c <= a:
            raise ValueError("these three side lengths cannot form a triangle")
        return self


class TrapezoidGeometryBlockSpec(BaseModel):
    type: Literal["trapezoid"] = "trapezoid"
    top: float = Field(gt=0, le=1_000_000)
    bottom: float = Field(gt=0, le=1_000_000)
    height: float = Field(gt=0, le=1_000_000)
    unit: str = "cm"
    show_labels: bool = True
    area: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class ParallelogramGeometryBlockSpec(BaseModel):
    type: Literal["parallelogram"] = "parallelogram"
    base: float = Field(gt=0, le=1_000_000)
    height: float = Field(gt=0, le=1_000_000)
    side: float = Field(gt=0, le=1_000_000)
    unit: str = "cm"
    show_labels: bool = True
    area: float | None = None
    perimeter: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class SectorGeometryBlockSpec(BaseModel):
    type: Literal["sector"] = "sector"
    radius: float = Field(gt=0, le=1_000_000)
    angle_deg: float = Field(gt=0, le=360)
    unit: str = "cm"
    show_labels: bool = True
    arc_length: float | None = None
    area: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class CircleGeometryBlockSpec(BaseModel):
    type: Literal["circle"] = "circle"
    radius: float = Field(gt=0, le=1_000_000)
    unit: str = "cm"
    show_labels: bool = True
    show_diameter: bool = False
    show_area: bool = False
    show_circumference: bool = False
    diameter: float | None = None
    area: float | None = None
    circumference: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class GeometryBlockSpec(BaseModel):
    type: Literal["rectangle", "rect", "square"] = "rectangle"
    width: float | None = Field(default=None, gt=0, le=1_000_000)
    height: float | None = Field(default=None, gt=0, le=1_000_000)
    side: float | None = Field(default=None, gt=0, le=1_000_000)
    unit: str = "cm"
    show_diagonal: bool = False
    show_angle: bool = False
    show_area: bool = False
    show_perimeter: bool = False
    diagonal: float | None = None
    angle_deg: float | None = None
    area: float | None = None
    perimeter: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_dimensions(self) -> GeometryBlockSpec:
        if self.type == "square":
            edge = self.side or self.width or self.height
            if edge is None:
                raise ValueError("square requires side or width/height")
            self.side = edge
            self.width = edge
            self.height = edge
            return self
        if self.width is None or self.height is None:
            raise ValueError("rectangle requires width and height")
        return self


class GraphBlockSpec(BaseModel):
    type: Literal["function", "vertical"] = "function"
    # Same bounds as every other math input model in this file (EquationInput,
    # GraphSampleInput, MathImageExtract) — this one was missing them, an
    # inconsistency worth closing even though this field is currently
    # display-only (math_fence.py never re-parses it through SymPy).
    expr: str = Field(default="", max_length=256)
    variable: str = Field(default="x", min_length=1, max_length=8)
    x_min: float = -10.0
    x_max: float = 10.0
    # Vertical-line fences (`type: "vertical"`) use `x` + y-range instead of
    # sampling y=f(x). Kept optional so ordinary function fences remain unchanged.
    x: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    title: str | None = None
    # Matches GraphSampleInput.n's upper bound (le=500) — the model never
    # legitimately needs more points than the canonical sample it was given.
    points: list[list[float]] = Field(default_factory=list, max_length=500)
    # points split at likely vertical-asymptote gaps — optional and kept
    # alongside `points` (not instead of) so a fence the model emits with
    # only `points` (the common case — most functions have no asymptote)
    # still validates and renders exactly as before.
    segments: list[list[list[float]]] = Field(default_factory=list, max_length=500)
    # Optional second curve for a direct comparison plot ("graph y=x^2 and
    # y=2x on the same axes") — entirely optional so every existing
    # single-function fence (no expr2) still validates and renders unchanged.
    expr2: str | None = Field(default=None, max_length=256)
    variable2: str | None = Field(default=None, max_length=8)
    points2: list[list[float]] | None = Field(default=None, max_length=500)
    segments2: list[list[list[float]]] | None = Field(default=None, max_length=500)
    # Short legend labels (e.g. "y = x^2") for the two curves — only
    # meaningful once expr2/points2 make this a two-curve plot.
    label: str | None = Field(default=None, max_length=64)
    label2: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def vertical_or_function_shape(self) -> GraphBlockSpec:
        if self.type == "vertical":
            if self.x is None:
                raise ValueError("vertical graph requires x")
            y_lo = -10.0 if self.y_min is None else float(self.y_min)
            y_hi = 10.0 if self.y_max is None else float(self.y_max)
            if y_hi <= y_lo:
                raise ValueError("vertical graph requires y_max > y_min")
            self.y_min = y_lo
            self.y_max = y_hi
            self.x_min = float(self.x) - 5.0
            self.x_max = float(self.x) + 5.0
            if not self.expr.strip():
                self.expr = f"x = {float(self.x):g}"
            if not self.title:
                self.title = self.expr
            if len(self.points) < 2:
                self.points = [[float(self.x), y_lo], [float(self.x), y_hi]]
            self.segments = []
            return self
        if not self.expr.strip():
            raise ValueError("function graph requires expr")
        if len(self.points) < 1:
            raise ValueError("graph points need at least one coordinate")
        has_expr2 = bool(self.expr2 and self.expr2.strip())
        has_points2 = bool(self.points2)
        if has_expr2 != has_points2:
            raise ValueError("expr2 and points2 must both be provided together, or neither")
        return self


class StatisticsInput(BaseModel):
    numbers: list[float] = Field(min_length=1, max_length=200)


class StatisticsResult(BaseModel):
    count: int
    numbers: list[float]
    sum: float
    mean: float
    median: float
    # Every value tied for the highest frequency — empty when every value in
    # the set appears exactly once (no meaningful "mode" to report).
    modes: list[float]
    range: float
    variance_population: float
    stdev_population: float
    # Sample variance/stdev use Bessel's correction (n-1) and are undefined
    # for a single data point.
    variance_sample: float | None = None
    stdev_sample: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class CombinatoricsInput(BaseModel):
    operation: Literal["factorial", "combinations", "permutations"]
    # Capped at 1000, not just "positive": math.comb/math.perm on an
    # unbounded n (e.g. a chat message asking for "1000000 choose 500000")
    # returns a correct but enormous integer — bounded here to keep the
    # verified block (and the model's reply) a sane size.
    n: int = Field(ge=0, le=1000)
    k: int | None = Field(default=None, ge=0, le=1000)


class CombinatoricsResult(BaseModel):
    operation: Literal["factorial", "combinations", "permutations"]
    n: int
    k: int | None
    result: int
    steps: list[str] = Field(default_factory=list)


class NumberTheoryInput(BaseModel):
    operation: Literal["gcd", "lcm", "factorize", "is_prime", "mod"]
    # factorize/is_prime bound to 1e8 specifically to keep sympy.factorint's
    # worst case (a large semiprime) fast — trial division up to sqrt(1e8)
    # is ~10k iterations, not a stall risk. gcd/lcm/mod share the same bound
    # for a single simple schema rather than a second near-identical one.
    a: int = Field(ge=-100_000_000, le=100_000_000)
    b: int | None = Field(default=None, ge=-100_000_000, le=100_000_000)


class NumberTheoryResult(BaseModel):
    operation: Literal["gcd", "lcm", "factorize", "is_prime", "mod"]
    a: int
    b: int | None
    result_int: int | None = None
    result_bool: bool | None = None
    # Prime -> exponent (e.g. 60 -> {2: 2, 3: 1, 5: 1}) — only set for "factorize".
    factors: dict[int, int] | None = None
    steps: list[str] = Field(default_factory=list)


class MatrixInput(BaseModel):
    operation: Literal["determinant", "inverse"]
    rows: list[list[float]] = Field(min_length=2, max_length=4)

    @field_validator("rows")
    @classmethod
    def rows_must_be_square(cls, value: list[list[float]]) -> list[list[float]]:
        size = len(value)
        if any(len(row) != size for row in value):
            raise ValueError("matrix must be square for determinant/inverse")
        return value


class MatrixResult(BaseModel):
    operation: Literal["determinant", "inverse"]
    determinant: float | None = None
    inverse_latex: str | None = None
    steps: list[str] = Field(default_factory=list)


class MathIntent(BaseModel):
    kind: Literal[
        "equation",
        "expression",
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
    ]
    lhs: str | None = None
    rhs: str | None = None
    expr: str | None = None
    variable: str = "x"
    # Inequality comparator (canonical: "<", ">", "<=", ">=") — only set when
    # kind == "inequality".
    comparator: str | None = None
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
    # Statistics — a raw data list (mean/median/mode/stdev/variance).
    stats_op: Literal["mean", "median", "mode", "variance", "stdev"] | None = None
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
