"""Structured math I/O — validated before SymPy and fence emission."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EquationInput(BaseModel):
    lhs: str = Field(min_length=1, max_length=256)
    rhs: str = Field(min_length=1, max_length=256)
    variables: list[str] = Field(default_factory=lambda: ["x"], min_length=1, max_length=4)


class MathImageExtract(BaseModel):
    """Vision-extracted equation from a photo (validated before SymPy)."""

    lhs: str = Field(min_length=1, max_length=256)
    rhs: str = Field(min_length=1, max_length=256)
    variables: list[str] = Field(default_factory=lambda: ["x"], min_length=1, max_length=4)
    found: bool = True


class MathSolveResult(BaseModel):
    solutions_latex: list[str]
    steps: list[str] = Field(default_factory=list)
    lhs_latex: str = ""
    rhs_latex: str = ""


class MathExprResult(BaseModel):
    result: str
    latex: str


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
    type: Literal["function"] = "function"
    # Same bounds as every other math input model in this file (EquationInput,
    # GraphSampleInput, MathImageExtract) — this one was missing them, an
    # inconsistency worth closing even though this field is currently
    # display-only (math_fence.py never re-parses it through SymPy).
    expr: str = Field(min_length=1, max_length=256)
    variable: str = Field(default="x", min_length=1, max_length=8)
    x_min: float = -10.0
    x_max: float = 10.0
    title: str | None = None
    points: list[list[float]] = Field(default_factory=list)

    @field_validator("points")
    @classmethod
    def points_need_at_least_two(cls, value: list[list[float]]) -> list[list[float]]:
        if len(value) < 2:
            raise ValueError("graph points need at least two coordinates")
        return value


class MathIntent(BaseModel):
    kind: Literal[
        "equation",
        "expression",
        "rectangle",
        "square",
        "triangle",
        "right_triangle",
        "graph",
        "calculus",
    ]
    lhs: str | None = None
    rhs: str | None = None
    expr: str | None = None
    variable: str = "x"
    width: float | None = None
    height: float | None = None
    base: float | None = None
    side: float | None = None
    unit: str = "cm"
    operation: Literal["solve", "simplify", "differentiate", "integrate", "graph"] | None = None
