"""A figure is the question's own shape, sized by the question's own lengths.

Round 3 (2026-11-14) drew four wrong pictures from the figure read and the tools: a cone
labelled 2 cm from "increasing at 2 cm/min" and 3 cm from "when r = 3 cm" (h = 3r), a
plain cone for "the frustum of a right circular cone", a default triangle for one whose
vertices the question gives as coordinates, and a circle card (area and circumference)
for "the sphere whose equation is (x - 1)^2 + (y + 2)^2 + z^2 = 1". Each is now refused:
a rate is no length, the size at one moment of a changing shape is no size of its figure,
a shape the question does not name, or names as part of another, is never drawn, and a
polygon placed at coordinates is drawn there or not at all.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.math.figure.build import figure_fence
from app.modules.math.figure.grounding import changing_values, written_numbers
from app.modules.math.figure.request import FigureRequest
from app.modules.math.figure.shape_names import names_shape
from app.modules.math.tool_check import matched_user_text


@pytest.mark.parametrize(
    ("text", "unit"),
    [
        ("The radius is increasing at a rate of 2 cm/min.", "other"),
        ("Gas flows in at 20 cm³/min.", "other"),
        ("The plane flies north at 600 km/h.", "other"),
        ("The level rises by 2 cm per minute.", "other"),
        ("A cone has a radius of 2 cm.", "cm"),
        ("A cone 2 cm across and 5 cm tall.", "cm"),
    ],
)
def test_a_rate_is_no_length(text: str, unit: str) -> None:
    assert written_numbers(text)[0].unit == unit


@pytest.mark.parametrize(
    ("text", "changing"),
    [
        ("Its height is always h = 3r. Find dV/dt when (a) r = 3 cm (b) r = 6 cm.", {3, 6}),
        ("Find dr/dt when r = 1 cm and when r = 2 cm.", {1, 2}),
        ("A cone with r = 3 cm and h = 4 cm. Find its volume.", set()),
        ("A box is 3 m by 4 m. Draw it.", set()),
    ],
)
def test_a_changing_quantity_has_no_size(text: str, changing: set[int]) -> None:
    assert changing_values([text]) == changing


def _fence(request: dict[str, Any], question: str) -> str | None:
    return figure_fence(FigureRequest.model_validate(request), [question])


_CONE = "The radius r of a right circular cone is increasing at a rate of 2 cm/min, and its height is always h = 3r. Find the rate of change of the volume when (a) r = 3 cm (b) r = 6 cm. Draw the cone."


@pytest.mark.parametrize(
    ("request_", "question", "drawn"),
    [
        # The rate and a moment's radius: never the figure's sizes.
        (
            {"kind": "solid", "shape": "cone", "measures": [{"what": "radius", "value": 2}]},
            _CONE,
            False,
        ),
        (
            {"kind": "solid", "shape": "cone", "measures": [{"what": "height", "value": 3}]},
            _CONE,
            False,
        ),
        ({"kind": "solid", "shape": "cone"}, _CONE, True),
        # A frustum is no cone; a cone is.
        (
            {"kind": "solid", "shape": "cone"},
            "Prove that the volume of a frustum of a right circular cone with radii R and r and height h is (π/3)h(R² + rR + r²). Draw the frustum.",
            False,
        ),
        (
            {"kind": "solid", "shape": "cone", "measures": [{"what": "radius", "value": 3}]},
            "Draw a conical funnel of radius 3 cm.",
            True,
        ),
        # A sphere's equation draws no circle; a circle does.
        (
            {"kind": "circle", "shape": "circle", "measures": [{"what": "radius", "value": 1}]},
            "How far is P(3, -1, 2) from the sphere (x - 1)² + (y + 2)² + z² = 1? Draw it.",
            False,
        ),
        (
            {"kind": "circle", "shape": "circle", "measures": [{"what": "radius", "value": 4}]},
            "Draw a circle of radius 4 cm.",
            True,
        ),
        # Corners given as coordinates: no default triangle in their place.
        (
            {"kind": "polygon", "shape": "triangle"},
            "Find the area of the triangle whose vertices are (−4, −1), (0, 0) and (5, 4). Draw it.",
            False,
        ),
        (
            {
                "kind": "polygon",
                "shape": "right_triangle",
                "measures": [{"what": "leg", "value": 3}, {"what": "leg", "value": 4}],
            },
            "Draw a right triangle with legs 3 cm and 4 cm.",
            True,
        ),
        # An open box is never drawn with its lid; any other box is.
        (
            {"kind": "solid", "shape": "cuboid"},
            "Design an open box with a square base and a surface area of 48 square units. Draw the box.",
            False,
        ),
        (
            {"kind": "solid", "shape": "cube", "measures": [{"what": "edge", "value": 4}]},
            "A fish tank is a cube of edge 4 m. Draw it.",
            True,
        ),
    ],
)
def test_the_figure_is_the_questions_shape(
    request_: dict[str, Any], question: str, drawn: bool
) -> None:
    assert (_fence(request_, question) is not None) == drawn


@pytest.mark.parametrize(
    ("words", "shape", "named"),
    [
        ("a semicircle on top of a rectangle", "circle", False),
        ("a circular garden", "circle", True),
        ("a cylindrical can", "cylinder", True),
        ("a hemispherical bowl", "sphere", False),
        ("a spherical balloon", "sphere", True),
        ("the truncated cone of a lampshade", "cone", False),
    ],
)
def test_names_shape_refuses_only(words: str, shape: str, named: bool) -> None:
    assert names_shape([words], shape) == named


@pytest.mark.parametrize(
    ("args", "question", "matched"),
    [
        (
            {"action": "circle", "radius": 1},
            "How far is the point P(3, −1, 2) from the sphere whose equation is (x − 1)² + (y + 2)² + z² = 1?",
            False,
        ),
        ({"action": "circle", "radius": 4}, "Find the area of a circle of radius 4 cm.", True),
        (
            {"action": "circle", "radius": 7},
            "A circular garden has a radius of 7 m. What is its area?",
            True,
        ),
        (
            {"action": "circle", "radius": 3},
            "A cylinder has radius 3 cm and height 10 cm. Find its volume.",
            False,
        ),
    ],
)
def test_a_circle_card_answers_a_circle(args: dict[str, Any], question: str, matched: bool) -> None:
    assert (matched_user_text(json.dumps(args), [question]) is not None) == matched
