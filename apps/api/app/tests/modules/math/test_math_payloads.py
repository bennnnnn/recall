"""Closed math kinds expose a nested operation without changing extractors."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas.math import MathIntent
from app.modules.math.tools.extractors.teaching import extract_teaching_intent


def test_arithmetic_payload_copies_the_school_operation() -> None:
    intent = MathIntent(kind="arithmetic", school_op="eval", expr="1+1", operation="solve")
    assert intent.arithmetic is not None
    assert intent.arithmetic.operation == "eval"
    assert intent.arithmetic.expr == "1+1"
    assert intent.probability is None
    assert intent.statistics is None
    assert intent.trig is None
    assert intent.units is None


def test_arithmetic_rejects_an_undeclared_operation() -> None:
    with pytest.raises(ValidationError):
        MathIntent(kind="arithmetic", school_op="not_a_law", expr="1+1", operation="solve")


def test_equation_school_method_does_not_become_an_arithmetic_payload() -> None:
    intent = MathIntent(
        kind="equation", lhs="2x+3", rhs="11", school_op="substitution", operation="solve"
    )
    assert intent.arithmetic is None
    assert intent.school_op == "substitution"


def test_teaching_picture_uses_its_operation() -> None:
    intent = MathIntent(
        kind="arithmetic",
        teaching_op="number_line_move",
        teaching_payload="-2|6",
        expr="(-2)+(6)",
        operation="solve",
    )
    assert intent.arithmetic is not None
    assert intent.arithmetic.operation == "number_line_move"
    assert intent.arithmetic.teaching_payload == "-2|6"
    extracted = extract_teaching_intent("-2 + 6")
    assert extracted is not None
    assert extracted.arithmetic is not None
    assert extracted.arithmetic.operation == "number_line_move"


def test_statistics_probability_trig_and_units_fill_their_payload() -> None:
    stats = MathIntent(
        kind="statistics", stats_op="mean", stats_numbers=[1, 2, 3], operation="solve"
    )
    assert stats.statistics is not None
    assert stats.statistics.operation == "mean"
    assert stats.statistics.stats_numbers == [1, 2, 3]

    probability = MathIntent(
        kind="probability", school_op="binomial", combo_n=10, combo_k=3, percent_base=0.5
    )
    assert probability.probability is not None
    assert probability.probability.operation == "binomial"
    assert probability.probability.combo_n == 10

    trig = MathIntent(kind="trig", school_op="sin", expr="sin((30)*pi/180)", percent_base=30)
    assert trig.trig is not None
    assert trig.trig.operation == "sin"
    assert trig.trig.percent_base == 30

    units = MathIntent(
        kind="unit", school_op="convert", percent_base=12, unit_from="in", unit_to="cm"
    )
    assert units.units is not None
    assert units.units.operation == "convert"
    assert units.units.unit_to == "cm"
