"""Structured math I/O — validated before SymPy and fence emission."""

from __future__ import annotations

import math
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
_VALID_CAMERA_CALC_OPS = frozenset({"simplify", "differentiate", "integrate", "factor", "expand"})
_VALID_CAMERA_STATS_OPS = frozenset({"mean", "median", "mode", "variance", "stdev"})


class MathImageExtract(BaseModel):
    """Vision-extracted math from a photo (validated before SymPy).

    `lhs`/`rhs` hold the first (or only) equation/inequality side — callers
    that only handled a single equation keep working. Structured kinds
    (system, inequality, calculus, limit, graph, rectangle, circle,
    triangle_sides, statistics) are additive so photographed homework beyond
    ``lhs=rhs`` still gets a verified SymPy path instead of unverified
    free-text."""

    kind: Literal[
        "equation",
        "system",
        "inequality",
        "calculus",
        "limit",
        "graph",
        "rectangle",
        "circle",
        "triangle_sides",
        "statistics",
    ] = "equation"
    # Defaults "0" let structured kinds omit equation sides in the vision JSON.
    lhs: str = Field(default="0", min_length=1, max_length=256)
    rhs: str = Field(default="0", min_length=1, max_length=256)
    variables: list[str] = Field(default_factory=lambda: ["x"], min_length=1, max_length=4)
    found: bool = True
    # kind == "system": every equation in the system as (lhs, rhs) pairs,
    # INCLUDING the first (so this is self-contained — callers don't need
    # to merge it with lhs/rhs above).
    equations: list[tuple[str, str]] | None = None
    # kind == "inequality": canonical comparator applied to lhs/rhs above.
    comparator: str | None = None
    # kind == "calculus" | "limit" | "graph": expression on the page.
    expr: str | None = Field(default=None, max_length=256)
    # kind == "calculus": simplify / differentiate / integrate / factor / expand.
    operation: str | None = None
    # kind == "limit": point approached (number or "infinity" / "oo").
    limit_point: str | None = Field(default=None, max_length=32)
    # kind == "calculus" + integrate: definite bounds (both required, or neither).
    integral_lower: str | None = Field(default=None, max_length=32)
    integral_upper: str | None = Field(default=None, max_length=32)
    # kind == "rectangle" | "circle": printed dimensions (never invent).
    width: float | None = Field(default=None, ge=0, le=1_000_000)
    height: float | None = Field(default=None, ge=0, le=1_000_000)
    radius: float | None = Field(default=None, ge=0, le=1_000_000)
    unit: str = Field(default="cm", max_length=16)
    # kind == "triangle_sides": printed SSS side lengths (never invent).
    tri_a: float | None = Field(default=None, ge=0, le=1_000_000)
    tri_b: float | None = Field(default=None, ge=0, le=1_000_000)
    tri_c: float | None = Field(default=None, ge=0, le=1_000_000)
    # kind == "statistics": printed data list + which summary was asked.
    stats_op: str | None = None
    stats_numbers: list[float] | None = Field(default=None, max_length=40)

    def _has_equation_sides(self) -> bool:
        return self.lhs.strip() not in ("", "0") or self.rhs.strip() not in ("", "0")

    @model_validator(mode="after")
    def normalize_kind(self) -> MathImageExtract:
        # Best-effort OCR hint from a vision model — a malformed/incomplete
        # kind must degrade gracefully rather than fail the whole extraction.
        if self.kind == "system" and (not self.equations or len(self.equations) < 2):
            self.kind = "equation"
        if self.kind == "inequality" and self.comparator not in _VALID_INEQUALITY_COMPARATORS:
            self.kind = "equation"
        # Defaults are "0"/"0" so structured kinds can omit sides. A bare
        # equation claim with both sides still at the placeholder is "not
        # found" (matches the vision prompt: found=false + lhs/rhs of "0").
        if (
            self.kind == "equation"
            and self.lhs.strip() in ("", "0")
            and self.rhs.strip() in ("", "0")
        ):
            self.found = False
        if self.kind == "calculus":
            op = (self.operation or "").strip().lower()
            if not (self.expr and self.expr.strip() and op in _VALID_CAMERA_CALC_OPS):
                self.kind = "equation" if self._has_equation_sides() else self.kind
                if self.kind == "calculus":
                    self.found = False
            else:
                self.operation = op
                # Definite integrals need BOTH bounds. A half-filled OCR
                # guess must not invent the missing endpoint — drop to
                # indefinite (same as heuristic when bounds parse fails).
                lower = (self.integral_lower or "").strip()
                upper = (self.integral_upper or "").strip()
                if op == "integrate" and lower and upper:
                    self.integral_lower = lower
                    self.integral_upper = upper
                else:
                    self.integral_lower = None
                    self.integral_upper = None
        if self.kind == "limit":
            if not (
                self.expr and self.expr.strip() and self.limit_point and self.limit_point.strip()
            ):
                self.kind = "equation" if self._has_equation_sides() else self.kind
                if self.kind == "limit":
                    self.found = False
        if self.kind == "graph":
            if not (self.expr and self.expr.strip()):
                self.kind = "equation" if self._has_equation_sides() else self.kind
                if self.kind == "graph":
                    self.found = False
        if self.kind == "rectangle":
            if self.width is None or self.height is None or self.width <= 0 or self.height <= 0:
                self.kind = "equation" if self._has_equation_sides() else self.kind
                if self.kind == "rectangle":
                    self.found = False
        if self.kind == "circle":
            if self.radius is None or self.radius <= 0:
                self.kind = "equation" if self._has_equation_sides() else self.kind
                if self.kind == "circle":
                    self.found = False
        if self.kind == "triangle_sides":
            sides = (self.tri_a, self.tri_b, self.tri_c)
            if any(s is None or s <= 0 for s in sides):
                self.kind = "equation" if self._has_equation_sides() else self.kind
                if self.kind == "triangle_sides":
                    self.found = False
        if self.kind == "statistics":
            op = (self.stats_op or "mean").strip().lower()
            nums = self.stats_numbers or []
            if op not in _VALID_CAMERA_STATS_OPS or len(nums) < 2:
                self.kind = "equation" if self._has_equation_sides() else self.kind
                if self.kind == "statistics":
                    self.found = False
            else:
                self.stats_op = op
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


class SolidGeometryInput(BaseModel):
    shape: Literal["cube", "rectangular_prism", "cylinder", "cone", "sphere", "pyramid"]
    width: float | None = Field(default=None, gt=0, le=1_000_000)
    height: float | None = Field(default=None, gt=0, le=1_000_000)
    depth: float | None = Field(default=None, gt=0, le=1_000_000)
    side: float | None = Field(default=None, gt=0, le=1_000_000)
    radius: float | None = Field(default=None, gt=0, le=1_000_000)
    unit: str = Field(default="cm", max_length=16)


class SolidGeometryResult(BaseModel):
    shape: Literal["cube", "rectangular_prism", "cylinder", "cone", "sphere", "pyramid"]
    volume: float
    surface_area: float
    unit: str
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
    show_ticks: bool = True
    show_altitude: bool = True
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
    show_ticks: bool = True
    show_altitude: bool = True
    show_median: bool = False
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
    show_ticks: bool = True
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


class NumberLineInterval(BaseModel):
    """One piece of a 1-variable inequality on a number line.

    ``start``/``end`` of ``None`` mean -inf / +inf. A closed (filled) circle is
    ``inclusive``; an open circle is not.
    """

    start: float | None = None
    end: float | None = None
    start_inclusive: bool = False
    end_inclusive: bool = False

    @model_validator(mode="after")
    def ordered_bounds(self) -> NumberLineInterval:
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("interval start must be <= end")
        return self


class GraphBlockSpec(BaseModel):
    type: Literal["function", "vertical", "number_line"] = "function"
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
    # 1-variable inequality on a number line (`type: "number_line"`). Empty
    # on function/vertical fences so existing dumps stay valid.
    intervals: list[NumberLineInterval] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def vertical_or_function_shape(self) -> GraphBlockSpec:
        if self.type == "number_line":
            if not self.expr.strip():
                raise ValueError("number_line requires expr")
            if not self.title:
                self.title = self.expr
            self.points = []
            self.segments = []
            return self
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

    @field_validator("numbers")
    @classmethod
    def reject_non_finite(cls, value: list[float]) -> list[float]:
        # nan/inf propagate silently through max-min/fsum and produce a
        # meaningless result; the matcher parses digits so this is mainly a
        # guard against OCR/structured stats carrying a non-finite value.
        for n in value:
            if not math.isfinite(n):
                raise ValueError("statistics values must be finite numbers")
        return value


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
    operation: Literal["determinant", "inverse", "multiply", "rref", "eigenvalues"]
    rows: list[list[float]] = Field(min_length=2, max_length=4)
    rows_b: list[list[float]] | None = Field(default=None, min_length=2, max_length=4)

    @field_validator("rows")
    @classmethod
    def rows_bounded(cls, value: list[list[float]]) -> list[list[float]]:
        width = len(value[0])
        if width < 1 or width > 4 or any(len(row) != width for row in value):
            raise ValueError("matrix rows must be rectangular and at most 4 wide")
        return value

    @model_validator(mode="after")
    def square_when_required(self) -> MatrixInput:
        if self.operation in {"determinant", "inverse", "eigenvalues"}:
            size = len(self.rows)
            if any(len(row) != size for row in self.rows):
                raise ValueError("matrix must be square for determinant/inverse/eigenvalues")
        return self


class MatrixResult(BaseModel):
    operation: Literal["determinant", "inverse", "multiply", "rref", "eigenvalues"]
    determinant: float | None = None
    inverse_latex: str | None = None
    result_latex: str | None = None
    steps: list[str] = Field(default_factory=list)


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
    matrix_op: Literal["determinant", "inverse", "multiply", "rref", "eigenvalues"] | None = None
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
    matrix_rows_b: list[list[float]] | None = None
