"""Verified calculus applications added after the broader math expansion."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.math import tools as math_tools
from app.services.math.calculus_applications import solve_calculus_application


def test_area_between_curves_exact() -> None:
    answer = solve_calculus_application(
        "area_between_curves",
        "x",
        "0",
        "1",
        "x^2",
    )
    assert answer == r"\frac{1}{6}"


def test_arc_length_exact() -> None:
    answer = solve_calculus_application("arc_length", "x", "0", "1")
    assert answer == r"\sqrt{2}"


def test_volume_about_x_axis_exact() -> None:
    answer = solve_calculus_application("volume_revolution_x", "x", "0", "1")
    assert answer == r"\frac{\pi}{3}"


def test_volume_about_y_axis_exact() -> None:
    answer = solve_calculus_application("volume_revolution_y", "x", "0", "1")
    assert answer == r"\frac{2 \pi}{3}"


def test_y_axis_shell_volume_refuses_interval_crossing_axis() -> None:
    from app.services.math.solve import MathServiceError

    with pytest.raises(MathServiceError, match="one side of the axis"):
        solve_calculus_application("volume_revolution_y", "x", "-1", "1")


@pytest.mark.parametrize(
    "text,school_op,answer",
    [
        (
            "find the area between x and x^2 on [0,1]",
            "area_between_curves",
            r"\frac{1}{6}",
        ),
        ("find the arc length of y=x from 0 to 1", "arc_length", r"\sqrt{2}"),
        (
            "find the volume of revolution of y=x from 0 to 1 about the x-axis",
            "volume_revolution_x",
            r"\frac{\pi}{3}",
        ),
        (
            "find the volume of revolution of y=x from 0 to 1 about the y-axis",
            "volume_revolution_y",
            r"\frac{2 \pi}{3}",
        ),
    ],
)
def test_calculus_application_routes_to_verified_block(
    text: str,
    school_op: str,
    answer: str,
) -> None:
    assert math_tools.needs_symbolic_math(text)
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "calculus"
    assert intent.school_op == school_op
    block = math_tools._build_verified_block(intent, Settings())
    assert block is not None
    assert block.canonical_answer == answer


def test_unsupported_revolution_axis_fails_closed() -> None:
    text = "find the volume of revolution of y=x from 0 to 1 about the line y=2"
    assert math_tools.extract_math_intent(text) is None


def test_statistics_range_route_is_preserved() -> None:
    text = "range of 1,2,3,4"
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "statistics"
    assert intent.stats_op == "range"


def test_projectile_launch_angle_route_is_preserved() -> None:
    text = "what launch angle gives a range of 35 m at 20 m/s"
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "projectile"
    assert intent.physics_op == "launch_angle"
