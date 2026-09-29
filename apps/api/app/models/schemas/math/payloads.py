"""Nested requests for the five math kinds that already carry a closed operation.

Extractors still fill the flat ``MathIntent`` fields. ``MathIntent`` copies
those fields into one of these models at validation time.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ArithmeticOp = Literal[
    "eval",
    "eval_exact_decimal",
    "symbolic_power",
    "column_addition",
    "column_subtraction",
    "column_multiplication",
    "long_division",
    "z_score",
    "set_union",
    "set_intersection",
    "set_difference",
    "sequence_sum",
    "sequence_nth",
    "ratio",
    "ratio_split",
    "work_together",
    "mixture",
    "twice_as_many",
    "percent",
    "percent_increase",
    "percent_decrease",
    "percent_is",
    "simple_interest",
    "compound_amount",
    "compound_interest",
    "fraction_simplify",
    "fraction_add",
    "fraction_subtract",
    "fraction_multiply",
    "fraction_divide",
    "fraction_of_quantity",
    "fraction_mixed_to_improper",
    "fraction_improper_to_mixed",
    "fraction_equivalent",
    "fraction_compare",
    "discount",
    "percent_change_from",
    "inverse_proportion",
    "direct_proportion",
    "round_decimal",
    "round_sigfigs",
    "present_value",
    "infinite_gp",
    "place_value",
    "number_bond",
    "ten_frame",
    "array",
    "base_ten",
    "number_line_move",
    "fraction_line",
    "decimal_compare",
    "round_place",
    "polynomial_division",
    "synthetic_division",
    "unit_circle",
    "box_plot",
    "frequency_table",
    "stem_leaf",
    "histogram",
    "scatter",
    "probability_tree",
    "transformation",
]

ProbabilityOp = Literal[
    "dice_conditional_sum",
    "binomial",
    "expected",
    "geometric",
    "poisson",
    "bayes",
    "complement",
]

StatisticsOp = Literal[
    "mean",
    "median",
    "mode",
    "variance",
    "stdev",
    "sample_stdev",
    "sample_variance",
    "range",
    "iqr",
    "quartiles",
    "percentile",
    "correlation",
    "covariance",
    "sample_covariance",
    "linear_regression",
]

TrigOp = Literal[
    "sin",
    "cos",
    "tan",
    "expression",
    "bounded_degree_equation",
    "bounded_radian_equation",
    "sas_area",
]

UnitOp = Literal["convert", "temperature_twice_compare"]

DivisionAnswerMode = Literal["remainder", "fraction", "decimal", "round_up", "discard"]


class ArithmeticRequest(BaseModel):
    operation: ArithmeticOp
    expr: str | None = None
    arithmetic_operands: list[str] | None = None
    division_answer_mode: DivisionAnswerMode | None = None
    fraction_operands: list[str] | None = None
    fraction_target: int | None = None
    percent_rate: float | None = None
    percent_base: float | None = None
    point_x: float | None = None
    combo_n: int | None = None
    teaching_payload: str | None = None


class ProbabilityRequest(BaseModel):
    operation: ProbabilityOp
    comparator: str | None = None
    combo_n: int | None = None
    combo_k: int | None = None
    percent_base: float | None = None
    stats_numbers: list[float] | None = None
    stats_numbers_b: list[float] | None = None
    vec_a: list[float] | None = None


class StatisticsRequest(BaseModel):
    operation: StatisticsOp
    stats_numbers: list[float] | None = None
    stats_numbers_b: list[float] | None = None
    combo_n: int | None = None


class TrigRequest(BaseModel):
    operation: TrigOp
    expr: str | None = None
    lhs: str | None = None
    rhs: str | None = None
    variable: str = "x"
    comparator: str | None = None
    comparator_upper: str | None = None
    integral_lower: str | None = None
    integral_upper: str | None = None
    percent_base: float | None = None
    percent_rate: float | None = None
    point_x: float | None = None


class UnitRequest(BaseModel):
    operation: UnitOp
    percent_base: float | None = None
    unit_from: str | None = None
    unit_to: str | None = None
    temperature_compare_value: float | None = None
    temperature_compare_unit: str | None = None
