"""Verified area, arc-length, and volume-of-revolution coverage."""

from __future__ import annotations

from app.core.config import Settings
from app.services.math import tools as math_tools
from app.services.math.solve.advanced import compute_calculus_application


def test_area_between_curves() -> None:
    answer, steps = compute_calculus_application(
        "area_between_curves",
        "x",
        "x",
        "0",
        "1",
        expr2="x**2",
    )
    assert answer == r"A = \frac{1}{6}"
    assert steps[-1] == answer


def test_arc_length_of_line() -> None:
    answer, _steps = compute_calculus_application(
        "arc_length",
        "x",
        "x",
        "0",
        "1",
    )
    assert answer == r"L = \sqrt{2}"


def test_volume_of_revolution_about_x_axis() -> None:
    answer, _steps = compute_calculus_application(
        "volume_revolution_x",
        "x",
        "x",
        "0",
        "1",
    )
    assert answer == r"V = \frac{\pi}{3}"


def test_area_between_curves_extracts_and_verifies() -> None:
    text = "find the area between y=x and y=x^2 from x=0 to 1"
    assert math_tools.needs_symbolic_math(text)
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.school_op == "area_between_curves"
    settings = Settings(math_tools_enabled=True)
    block = math_tools._build_verified_block(intent, settings)
    assert block is not None
    assert block.canonical_answer == r"A = \frac{1}{6}"


def test_arc_length_extracts() -> None:
    text = "find the arc length of y=x from x=0 to 1"
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "calculus"
    assert intent.school_op == "arc_length"


def test_volume_revolution_extracts() -> None:
    text = "find the volume of revolution of y=x from x=0 to 1 about the x-axis"
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "calculus"
    assert intent.school_op == "volume_revolution_x"


def test_y_axis_volume_is_not_mislabeled_as_x_axis_template() -> None:
    text = "find the volume of revolution of y=x from x=0 to 1 about the y-axis"
    intent = math_tools.extract_math_intent(text)
    assert intent is None or intent.school_op != "volume_revolution_x"
