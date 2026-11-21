"""Coordinate geometry and transformations, drawn where the question puts them.

The teaching figures drew nothing for a triangle at given vertices, a midpoint, a circle's
equation or a reflection (2026-11-20 corpus: the read said none, and a polygon at
coordinates was "drawn there or not at all"). Each picture here is built from a reading as
the read model gives it: the question's own points labelled with their coordinates, every
other point (a midpoint, a centre from an equation, a transformation's image) worked out
by the server, exactly, and a reading the question does not bear out draws nothing.
"""

from __future__ import annotations

import json
from fractions import Fraction
from typing import Any

import pytest

from app.modules.math.figure.build import figure_fence
from app.modules.math.figure.plane_text import coordinate_text, primed
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import PointsGraphSpec

Pair = tuple[float, float]


def _plane(question: str, reading: dict[str, Any]) -> PointsGraphSpec | None:
    fence = figure_fence(FigureRequest.model_validate(reading), [question])
    if fence is None:
        return None
    lang, _, rest = fence.removeprefix("```").partition("\n")
    assert lang == "graph"
    return PointsGraphSpec.model_validate(json.loads(rest.rsplit("\n```", 1)[0]))


def _drawn(question: str, reading: dict[str, Any]) -> PointsGraphSpec:
    graph = _plane(question, reading)
    assert graph is not None
    return graph


def _points(*pairs: tuple[str, float, float]) -> list[dict[str, Any]]:
    return [{"name": name, "x": x, "y": y} for name, x, y in pairs]


def _labels(graph: PointsGraphSpec, role: str | None = None) -> dict[str, Pair]:
    return {p.label: (p.x, p.y) for p in graph.points if role is None or p.role == role}


def _image(graph: PointsGraphSpec) -> set[Pair]:
    found = {(p.x, p.y) for p in graph.points if p.role == "image"}
    found |= {c for polygon in graph.polygons if polygon.role == "image" for c in polygon.points}
    return found


TRIANGLE = _points(("A", 1, 2), ("B", 4, 2), ("C", 1, 5))
TRIANGLE_Q = "Triangle ABC has vertices A(1, 2), B(4, 2) and C(1, 5)."


def test_a_segment_s_distance_shows_its_legs_by_pythagoras() -> None:
    graph = _drawn(
        "Find the distance between the points A(1, 2) and B(7, 10).",
        {"kind": "points", "join": "segment", "parts": ["distance"],
         "points": _points(("A", 1, 2), ("B", 7, 10))},
    )  # fmt: skip
    assert _labels(graph) == {"A(1, 2)": (1, 2), "B(7, 10)": (7, 10)}
    legs = {s.label: (s.start, s.end) for s in graph.segments if s.role == "guide"}
    assert legs == {"6": ((1, 2), (7, 2)), "8": ((7, 2), (7, 10))}
    assert [mark.at for mark in graph.right_angles] == [(7, 2)]


def test_a_midpoint_is_worked_out_and_its_halves_marked_equal() -> None:
    graph = _drawn(
        "Find the midpoint of the segment joining P(-3, 4) and Q(5, -2).",
        {"kind": "points", "join": "segment", "parts": ["midpoint"],
         "points": _points(("P", -3, 4), ("Q", 5, -2))},
    )  # fmt: skip
    assert _labels(graph) == {"P(−3, 4)": (-3, 4), "Q(5, −2)": (5, -2), "M": (1, 1)}
    halves = [(s.start, s.end, s.ticks) for s in graph.segments]
    assert halves == [((-3, 4), (1, 1), 1), ((1, 1), (5, -2), 1)]


def test_a_gradient_shows_its_run_and_signed_rise() -> None:
    graph = _drawn(
        "What is the gradient of the line segment joining E(-2, 5) and F(4, -7)?",
        {"kind": "points", "join": "segment", "parts": ["gradient"],
         "points": _points(("E", -2, 5), ("F", 4, -7))},
    )  # fmt: skip
    labels = {s.label for s in graph.segments if s.label}
    assert labels == {"Δx = 6", "Δy = −12"}


def test_a_perpendicular_bisector_crosses_the_midpoint_at_a_right_angle() -> None:
    graph = _drawn(
        "Find the equation of the perpendicular bisector of A(2, 4) and B(6, 8).",
        {"kind": "points", "join": "segment", "parts": ["perpendicular_bisector"],
         "points": _points(("A", 2, 4), ("B", 6, 8))},
    )  # fmt: skip
    assert _labels(graph)["M"] == (4, 6)
    (line,) = [s for s in graph.segments if s.role == "guide"]
    (x1, y1), (x2, y2) = line.start, line.end
    assert (x2 - x1) * 4 + (y2 - y1) * 4 == pytest.approx(0)  # square to AB, along (4, 4)
    assert (x1 - 4) * (y2 - 6) == pytest.approx((x2 - 4) * (y1 - 6))  # through M
    assert [mark.at for mark in graph.right_angles] == [(4, 6)]


def test_a_polygon_sits_at_its_vertices_with_its_exact_right_angles_and_equal_sides() -> None:
    graph = _drawn(
        "Show that the triangle with vertices P(-2, 1), Q(2, 3) and R(4, -1) is right-angled.",
        {"kind": "points", "join": "polygon", "points": _points(("P", -2, 1), ("Q", 2, 3), ("R", 4, -1))},
    )  # fmt: skip
    assert graph.polygons[0].points == [(-2, 1), (2, 3), (4, -1)]
    assert [mark.at for mark in graph.right_angles] == [(2, 3)]  # PQ . QR = 0, nowhere else
    assert [s.ticks for s in graph.segments] == [1, 1, 0]  # PQ = QR = sqrt 20


def test_a_parallelogram_s_diagonals_meet_at_one_midpoint() -> None:
    graph = _drawn(
        "ABCD is a parallelogram with A(-3, -1), B(2, -1), C(4, 3) and D(-1, 3). "
        "Show that its diagonals bisect each other.",
        {"kind": "points", "join": "polygon", "parts": ["diagonals", "midpoint"],
         "points": _points(("A", -3, -1), ("B", 2, -1), ("C", 4, 3), ("D", -1, 3))},
    )  # fmt: skip
    assert _labels(graph)["M"] == (0.5, 1)
    assert len([s for s in graph.segments if s.role == "guide"]) == 2
    assert [s.ticks for s in graph.segments if s.role == "shape"] == [1, 2, 1, 2]


def test_a_rhombus_s_diagonals_are_marked_square_where_they_cross() -> None:
    graph = _drawn(
        "The points A(0, 0), B(3, 4), C(8, 4) and D(5, 0) are the vertices of a rhombus. "
        "Show that its diagonals cross at right angles.",
        {"kind": "points", "join": "polygon", "parts": ["diagonals"],
         "points": _points(("A", 0, 0), ("B", 3, 4), ("C", 8, 4), ("D", 5, 0))},
    )  # fmt: skip
    assert [s.ticks for s in graph.segments if s.role == "shape"] == [1, 1, 1, 1]
    assert [mark.at for mark in graph.right_angles] == [(4, 2)]


def test_the_plane_is_square_and_holds_the_origin_and_every_part() -> None:
    graph = _drawn(
        "Find the area of the triangle with vertices A(10, 12), B(16, 12) and C(12, 17).",
        {"kind": "polygon", "shape": "triangle",
         "points": _points(("A", 10, 12), ("B", 16, 12), ("C", 12, 17))},
    )  # fmt: skip
    assert graph.x_max - graph.x_min == graph.y_max - graph.y_min
    assert graph.x_min <= 0 <= graph.x_max and graph.y_min <= 0 <= graph.y_max
    assert graph.x_max > 16 and graph.y_max > 17


@pytest.mark.parametrize(
    "question, equation, centre, radius",
    [
        ("Find the centre and radius of the circle x^2 + y^2 - 6x + 4y - 12 = 0.",
         "x^2 + y^2 - 6x + 4y - 12 = 0", (3, -2), 5),
        ("Write down the centre and radius of the circle (x - 2)^2 + (y + 5)^2 = 49.",
         "(x - 2)^2 + (y + 5)^2 = 49", (2, -5), 7),
        ("Find the centre and radius of 2x^2 + 2y^2 - 8x - 10 = 0.", "x^2 + y^2 - 4x - 5 = 0",
         (2, 0), 3),
        ("Find the centre and radius of the circle x^2 + y^2 = 13.", "x^2 + y^2 = 13", (0, 0),
         13**0.5),
    ],
)  # fmt: skip
def test_a_circle_s_centre_and_radius_are_worked_out_from_its_equation(
    question: str, equation: str, centre: Pair, radius: float
) -> None:
    graph = _drawn(question, {"kind": "points", "equation": equation})
    (circle,) = graph.circles
    assert circle.center == centre and circle.radius == pytest.approx(radius)
    # Worked out from the equation they are the answer: the centre's letter, the radius r.
    assert _labels(graph) == {"C": centre}
    assert [s.label for s in graph.segments] == ["r"]


def test_a_circle_from_its_stated_centre_with_a_radius_or_a_point_on_it() -> None:
    graph = _drawn(
        "Find the equation of the circle with centre (3, -2) and radius 4.",
        {"kind": "points", "points": _points(("", 3, -2)),
         "measures": [{"what": "radius", "value": 4}]},
    )  # fmt: skip
    assert graph.circles[0].center == (3, -2) and graph.circles[0].radius == 4
    assert _labels(graph) == {"C(3, −2)": (3, -2)}
    through = _drawn(
        "A circle has centre O(1, 2) and passes through P(4, 6). Find its equation.",
        {"kind": "points", "points": _points(("O", 1, 2), ("P", 4, 6))},
    )
    assert through.circles[0].radius == 5
    assert set(_labels(through)) == {"O(1, 2)", "P(4, 6)"}
    assert [(s.start, s.end) for s in through.segments] == [((1, 2), (4, 6))]


@pytest.mark.parametrize(
    "mirror, question_line, image",
    [
        ("x-axis", "in the x-axis", {(1, -2), (4, -2), (1, -5)}),
        ("y-axis", "in the y-axis", {(-1, 2), (-4, 2), (-1, 5)}),
        ("y = x", "in the line y = x", {(2, 1), (2, 4), (5, 1)}),
        ("y = -x", "in the line y = -x", {(-2, -1), (-2, -4), (-5, -1)}),
        ("x = -1", "in the line x = -1", {(-3, 2), (-6, 2), (-3, 5)}),
        ("y = 3", "in the line y = 3", {(1, 4), (4, 4), (1, 1)}),
        ("y = x + 1", "in the line y = x + 1", {(1, 2), (1, 5), (4, 2)}),
    ],
)
def test_a_reflection_s_image_is_worked_out_exactly(
    mirror: str, question_line: str, image: set[Pair]
) -> None:
    question = f"{TRIANGLE_Q} Find the vertices of its reflection {question_line}."
    reading = {"kind": "points", "join": "polygon", "points": TRIANGLE,
               "transforms": [{"kind": "reflection", "mirror": mirror}]}  # fmt: skip
    graph = _drawn(question, reading)
    assert _image(graph) == image
    assert set(_labels(graph, "image")) == {"A′", "B′", "C′"}
    assert set(_labels(graph, "shape")) == {"A(1, 2)", "B(4, 2)", "C(1, 5)"}
    assert all(s.dashed for s in graph.segments if s.role == "image")
    drawn_mirror = [s.label for s in graph.segments if s.role == "guide" and s.label]
    assert drawn_mirror == ([] if "axis" in mirror else [mirror.replace("-", "−")])


@pytest.mark.parametrize(
    "words, transform, image",
    [
        ("rotated 90° anticlockwise about the origin",
         {"kind": "rotation", "angle": 90, "direction": "anticlockwise"}, (-1, 3)),
        ("rotated 90° clockwise about the origin",
         {"kind": "rotation", "angle": 90, "direction": "clockwise"}, (1, -3)),
        ("rotated 90° about the origin", {"kind": "rotation", "angle": 90}, (-1, 3)),
        ("rotated through -90° about the origin", {"kind": "rotation", "angle": -90}, (1, -3)),
        ("given a half turn about the origin", {"kind": "rotation"}, (-3, -1)),
        ("rotated 270° anticlockwise about the origin",
         {"kind": "rotation", "angle": 270, "direction": "anticlockwise"}, (1, -3)),
        ("rotated 90° clockwise about the point (1, 2)",
         {"kind": "rotation", "angle": 90, "direction": "clockwise", "centre": {"x": 1, "y": 2}},
         (0, 0)),
        ("translated by the vector (-4, 2)",
         {"kind": "translation", "vector": {"x": -4, "y": 2}}, (-1, 3)),
        ("translated 2 units left and 5 units down",
         {"kind": "translation", "vector": {"x": -2, "y": -5}}, (1, -4)),
        ("enlarged by scale factor 3 about the origin",
         {"kind": "enlargement", "factor": "3"}, (9, 3)),
        ("enlarged by scale factor 1/2 about the point (1, 1)",
         {"kind": "enlargement", "factor": "1/2", "centre": {"x": 1, "y": 1}}, (2, 1)),
        ("enlarged by scale factor -2 about the origin",
         {"kind": "enlargement", "factor": "-2"}, (-6, -2)),
    ],
)  # fmt: skip
def test_a_point_s_image_is_worked_out_from_the_stated_transformation(
    words: str, transform: dict[str, Any], image: Pair
) -> None:
    question = f"The point P(3, 1) is {words}. Find its image."
    graph = _drawn(question, {"kind": "points", "points": _points(("P", 3, 1)),
                              "transforms": [transform]})  # fmt: skip
    assert _labels(graph, "image") == {"P′": image}


def test_an_enlargement_keeps_fractions_exact() -> None:
    graph = _drawn(
        "Triangle ABC with A(1, 2), B(4, 2) and C(1, 5) is enlarged by scale factor 1/3 "
        "about the origin.",
        {"kind": "points", "points": TRIANGLE, "transforms": [{"kind": "enlargement", "factor": "1/3"}]},
    )  # fmt: skip
    assert _labels(graph, "image")["A′"] == (pytest.approx(1 / 3), pytest.approx(2 / 3))
    assert coordinate_text(Fraction(1, 3)) == "1/3"
    assert coordinate_text(Fraction(-5, 2)) == "−2.5"
    assert primed("A", 2) == "A″" and primed("", 1) == ""


def test_a_transformation_s_guides_show_how_it_was_made() -> None:
    translated = _drawn(
        "Triangle PQR with P(0, 0), Q(2, 0) and R(0, 3) is translated by the vector (4, 1). "
        "Find the new vertices.",
        # The read listed the vector among the points: a pair written once, as the vector.
        {"kind": "points", "join": "polygon",
         "points": _points(("P", 0, 0), ("Q", 2, 0), ("R", 0, 3), ("", 4, 1)),
         "transforms": [{"kind": "translation", "vector": {"x": 4, "y": 1}}]},
    )  # fmt: skip
    assert _image(translated) == {(4, 1), (6, 1), (4, 4)}
    (arrow,) = [s for s in translated.segments if s.arrow]
    assert (arrow.start, arrow.end, arrow.label) == ((0, 0), (4, 1), "(4, 1)")
    rotated = _drawn(
        "Triangle ABC with A(2, 1), B(5, 1) and C(5, 3) is rotated 90° clockwise about the "
        "point (1, 0).",
        {"kind": "points", "points": _points(("A", 2, 1), ("B", 5, 1), ("C", 5, 3)),
         "transforms": [{"kind": "rotation", "angle": 90, "direction": "clockwise",
                         "centre": {"x": 1, "y": 0}}]},
    )  # fmt: skip
    assert _image(rotated) == {(2, -1), (2, -4), (4, -4)}
    assert _labels(rotated, "guide") == {"(1, 0)": (1, 0)}
    assert (1, 0) in [mark.at for mark in rotated.right_angles]


def test_two_transformations_in_turn_draw_both_images() -> None:
    graph = _drawn(
        "The point A(2, 3) is reflected in the x-axis and then rotated 90° anticlockwise "
        "about the origin. Find the final image.",
        {"kind": "points", "points": _points(("A", 2, 3)),
         "transforms": [{"kind": "reflection", "mirror": "x-axis"},
                        {"kind": "rotation", "angle": 90, "direction": "anticlockwise"}]},
    )  # fmt: skip
    assert _labels(graph, "image") == {"A′": (2, -3), "A″": (3, 2)}


ROTATE_Q = "The point P(3, 1) is rotated 90° anticlockwise about the origin."
_ROTATE = {"kind": "rotation", "angle": 90, "direction": "anticlockwise"}


@pytest.mark.parametrize(
    "question, reading",
    [
        # A mirror line the question never names.
        (f"{TRIANGLE_Q} Reflect it in the x-axis.",
         {"kind": "points", "points": TRIANGLE, "transforms": [{"kind": "reflection", "mirror": "y = x"}]}),
        # An angle it never states.
        ("The point P(3, 1) is rotated 180° about the origin.",
         {"kind": "points", "points": _points(("P", 3, 1)), "transforms": [_ROTATE]}),
        # The direction the other way.
        ("The point P(3, 1) is rotated 90° clockwise about the origin.",
         {"kind": "points", "points": _points(("P", 3, 1)), "transforms": [_ROTATE]}),
        # A centre it never names: about (1, 2) is no rotation about the origin.
        ("The point P(3, 1) is rotated 90° anticlockwise about the point (1, 2).",
         {"kind": "points", "points": _points(("P", 3, 1)), "transforms": [_ROTATE]}),
        # A vector it never writes.
        ("Triangle PQR with P(0, 0), Q(2, 0) and R(0, 3) is translated by the vector (4, 1).",
         {"kind": "points", "points": _points(("P", 0, 0), ("Q", 2, 0), ("R", 0, 3)),
          "transforms": [{"kind": "translation", "vector": {"x": 1, "y": 4}}]}),
        # A scale factor it never writes.
        ("The point P(3, 1) is enlarged by scale factor 3 about the origin.",
         {"kind": "points", "points": _points(("P", 3, 1)),
          "transforms": [{"kind": "enlargement", "factor": "2"}]}),
        # A transformation it does not name.
        (ROTATE_Q, {"kind": "points", "points": _points(("P", 3, 1)),
                    "transforms": [{"kind": "reflection", "mirror": "x-axis"}]}),
        # One transformation after another read as one: the image would be the first's.
        ("The point A(2, 3) is reflected in the x-axis and then rotated 90° anticlockwise "
         "about the origin.",
         {"kind": "points", "points": _points(("A", 2, 3)),
          "transforms": [{"kind": "reflection", "mirror": "x-axis"}]}),
        # A vertex it never writes.
        (ROTATE_Q, {"kind": "points", "points": _points(("P", 3, 2)), "transforms": [_ROTATE]}),
        # A formula the plane would leave out.
        ("The point P(3, 1) lies on y = 2x - 5. Rotate P 90° anticlockwise about the origin.",
         {"kind": "points", "points": _points(("P", 3, 1)), "transforms": [_ROTATE]}),
        # A circle's equation the question does not write.
        ("Find the centre and radius of the circle x^2 + y^2 - 6x + 4y - 12 = 0.",
         {"kind": "points", "equation": "x^2 + y^2 - 6x + 4y + 12 = 0"}),
        # No circle: its radius squared is not positive.
        ("Find the centre and radius of x^2 + y^2 + 4 = 0.",
         {"kind": "points", "equation": "x^2 + y^2 + 4 = 0"}),
        # Corners in an order that crosses itself, and corners on one line.
        ("Find the area of ABCD with A(0, 0), B(4, 0), C(0, 4) and D(4, 4).",
         {"kind": "points", "join": "polygon",
          "points": _points(("A", 0, 0), ("B", 4, 0), ("C", 0, 4), ("D", 4, 4))}),
        ("Find the area of the triangle A(1, 2), B(3, 6), C(5, 10).",
         {"kind": "points", "join": "polygon",
          "points": _points(("A", 1, 2), ("B", 3, 6), ("C", 5, 10))}),
    ],
)  # fmt: skip
def test_a_reading_the_question_does_not_bear_out_draws_nothing(
    question: str, reading: dict[str, Any]
) -> None:
    assert _plane(question, reading) is None


def test_points_alone_still_plot_as_before() -> None:
    graph = _drawn(
        "Plot the points A(2, 3) and B(-1, 4).",
        {"kind": "points", "points": _points(("A", 2, 3), ("B", -1, 4))},
    )
    assert graph.title == "A(2, 3), B(−1, 4)"
    assert not (graph.segments or graph.polygons or graph.circles)
