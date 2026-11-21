"""Angles drawn true: a triangle's exterior angle, a quadrilateral by its angles, a regular
polygon by its perimeter or its angle, and angles written with a letter, solved where
their sum decides them."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.math.figure.angle_terms import sized_angles
from app.modules.math.figure.request import FigureRequest

from .figure_support import angle, draw, figure, labelled_angle, labels, length


def _angles(shape: str, kind: str = "polygon", **more: Any) -> dict[str, Any]:
    measures = [
        {"what": what, "name": name, "value": value}
        for what, name, value in more.pop("measures", [])
    ]
    return {"kind": kind, "shape": shape, "measures": measures, **more}


EXTERIOR = (
    "An exterior angle of a triangle is 120° and one of the interior opposite angles is 50°. "
    "Find the other interior opposite angle."
)


def test_exterior_angle_is_the_sum_of_the_two_opposite() -> None:
    reading = _angles("triangle", measures=[("exterior_angle", "", 120), ("angle", "", 50)])
    spec = figure(EXTERIOR, reading)
    assert labels(spec) == ["120°", "50°"]
    assert labelled_angle(spec, "120°") == pytest.approx(120)
    assert labelled_angle(spec, "50°") == pytest.approx(50)
    assert angle(spec, "B", "A", "C") == pytest.approx(70)
    assert angle(spec, "C", "A", "B") == pytest.approx(60)


def test_exterior_angle_named_by_its_letters() -> None:
    question = "In triangle ABC, BC is produced to D. Angle ACD = 115° and angle BAC = 45°."
    reading = _angles(
        "triangle",
        vertices="ABC",
        measures=[("exterior_angle", "ACD", 115), ("angle", "BAC", 45)],
    )
    spec = figure(question, reading)
    assert angle(spec, "C", "A", "D") == pytest.approx(115)
    assert angle(spec, "A", "B", "C") == pytest.approx(45)
    assert angle(spec, "B", "A", "C") == pytest.approx(70)
    assert {p.name for p in spec.points if p.show} == set("ABCD")


@pytest.mark.parametrize(
    "measures",
    [
        [("exterior_angle", "", 120), ("angle", "", 130)],
        [("exterior_angle", "", 120), ("angle", "", 50), ("angle", "", 60)],
        [("exterior_angle", "C", 120), ("angle", "C", 70)],
    ],
)
def test_exterior_angle_that_cannot_hold_draws_nothing(
    measures: list[tuple[str, str, float]],
) -> None:
    question = "An exterior angle at C is 120°; angles of 130°, 50°, 60° and 70°."
    assert draw(question, _angles("triangle", measures=measures)) is None


QUADRILATERAL = "In quadrilateral ABCD, angle A = 80°, angle B = 95° and angle C = 110°."


def test_quadrilateral_is_drawn_with_its_angles_and_the_fourth_they_leave() -> None:
    reading = _angles(
        "quadrilateral",
        vertices="ABCD",
        measures=[("angle", "A", 80), ("angle", "B", 95), ("angle", "C", 110)],
    )
    spec = figure(QUADRILATERAL, reading)
    assert labels(spec) == ["110°", "80°", "95°"]
    for vertex, before, after, size in (
        ("A", "D", "B", 80),
        ("B", "A", "C", 95),
        ("C", "B", "D", 110),
        ("D", "C", "A", 75),
    ):
        assert angle(spec, vertex, before, after) == pytest.approx(size)
    sides = [length(spec, a, b) for a, b in ("AB", "BC", "CD", "DA")]
    assert max(sides) / min(sides) <= 4


def test_quadrilateral_keeps_a_stated_side() -> None:
    question = "In quadrilateral ABCD, AB = 7 cm, angle A = 80°, angle B = 95°, angle C = 110°."
    reading = _angles(
        "quadrilateral",
        vertices="ABCD",
        unit="cm",
        measures=[
            ("side", "AB", 7),
            ("angle", "A", 80),
            ("angle", "B", 95),
            ("angle", "C", 110),
        ],
    )
    assert length(figure(question, reading), "A", "B") == pytest.approx(7)


def test_quadrilateral_angles_with_a_letter_are_solved_and_labelled_as_written() -> None:
    question = "The angles of a quadrilateral are x, 2x, 3x and 4x. Find the largest angle."
    reading = _angles("quadrilateral", angle_terms=[{"term": t} for t in ("x", "2x", "3x", "4x")])
    spec = figure(question, reading)
    assert labels(spec) == ["2x", "3x", "4x", "x"]
    assert labelled_angle(spec, "x") == pytest.approx(36)
    assert labelled_angle(spec, "4x") == pytest.approx(144)


@pytest.mark.parametrize(
    "measures",
    [
        [("angle", "A", 170), ("angle", "B", 170), ("angle", "C", 30)],
        [("angle", "A", 80), ("angle", "B", 95), ("angle", "C", 110), ("angle", "D", 70)],
    ],
)
def test_quadrilateral_angles_that_cannot_hold_draw_nothing(
    measures: list[tuple[str, str, float]],
) -> None:
    question = "Quadrilateral ABCD has angles of 170°, 170°, 30°, 80°, 95°, 110° and 70°."
    assert draw(question, _angles("quadrilateral", vertices="ABCD", measures=measures)) is None


def test_regular_polygon_side_is_its_perimeter_shared() -> None:
    question = "A regular pentagon has a perimeter of 45 cm. Find the length of one side."
    reading = _angles("regular_polygon", sides=5, unit="cm", measures=[("perimeter", "", 45)])
    spec = figure(question, reading)
    assert spec.shape == "regular_polygon_5"
    assert length(spec, "A", "B") == pytest.approx(9)
    assert labels(spec) == []


@pytest.mark.parametrize(
    ("question", "what", "value", "count"),
    [
        (
            "Each interior angle of a regular polygon is 140°. How many sides?",
            "interior_angle",
            140,
            9,
        ),
        (
            "Each exterior angle of a regular polygon is 30°. How many sides?",
            "exterior_angle",
            30,
            12,
        ),
    ],
)
def test_regular_polygon_sides_are_worked_out_from_its_angle(
    question: str, what: str, value: float, count: int
) -> None:
    spec = figure(question, _angles("regular_polygon", measures=[(what, "", value)]))
    assert spec.shape == f"regular_polygon_{count}"
    assert labelled_angle(spec, f"{value:g}°") == pytest.approx(value)


@pytest.mark.parametrize(
    ("question", "reading"),
    [
        (
            "Each interior angle of a regular polygon is 100°.",
            _angles("regular_polygon", measures=[("interior_angle", "", 100)]),
        ),
        (
            "A regular hexagon has each interior angle 140°.",
            _angles("regular_hexagon", measures=[("interior_angle", "", 140)]),
        ),
    ],
)
def test_regular_polygon_angle_that_names_no_polygon_draws_nothing(
    question: str, reading: dict[str, Any]
) -> None:
    assert draw(question, reading) is None


def _terms(*terms: str) -> list[dict[str, str]]:
    return [{"term": term} for term in terms]


def test_angles_at_a_point_with_a_letter_are_drawn_at_their_solved_sizes() -> None:
    question = "Three angles at a point are x, 2x and 150°. Find x."
    reading = _angles(
        "angles_at_point",
        kind="lines",
        measures=[("angle", "", 150)],
        angle_terms=_terms("x", "2x"),
    )
    spec = figure(question, reading)
    assert labels(spec) == ["150°", "2x", "x"]
    assert labelled_angle(spec, "x") == pytest.approx(70)
    assert labelled_angle(spec, "2x") == pytest.approx(140)


def test_supplementary_angles_with_a_letter_make_a_straight_line() -> None:
    question = "Two supplementary angles are 3x + 10 and 2x - 5. Find x."
    reading = _angles("supplementary_angles", kind="lines", angle_terms=_terms("3x + 10", "2x - 5"))
    spec = figure(question, reading)
    assert labelled_angle(spec, "3x + 10") == pytest.approx(115)
    assert labelled_angle(spec, "2x - 5") == pytest.approx(65)


def test_triangle_angles_with_a_letter_box_the_right_angle() -> None:
    question = "The angles of a triangle are x, 2x and 3x. Find each angle."
    spec = figure(question, _angles("triangle", angle_terms=_terms("x", "2x", "3x")))
    assert labels(spec) == ["2x", "3x", "x"]
    assert labelled_angle(spec, "x") == pytest.approx(30)
    right = next(a for a in spec.angles if a.label == "3x")
    assert right.right


@pytest.mark.parametrize(
    ("question", "shape", "terms", "measures"),
    [
        # Two letters: the sum does not decide them.
        ("Angles x, y and 100° are on a straight line.", "angles_on_line", ("x", "y"), [100]),
        # A term the question does not write.
        ("Three angles at a point are x, 2x and 150°.", "angles_at_point", ("x", "3x"), [150]),
        # An angle that comes out at 180° or more.
        ("Two angles at a point are x and 150°.", "angles_at_point", ("x",), [150]),
    ],
)
def test_lettered_angles_that_do_not_decide_draw_nothing(
    question: str, shape: str, terms: tuple[str, ...], measures: list[float]
) -> None:
    reading = _angles(
        shape,
        kind="lines",
        measures=[("angle", "", value) for value in measures],
        angle_terms=_terms(*terms),
    )
    assert draw(question, reading) is None


def test_sized_angles_solve_exactly() -> None:
    request = FigureRequest.model_validate(
        _angles("angles_on_line", kind="lines", angle_terms=_terms("x + 20", "x"))
    )
    sized = sized_angles(request, 180.0)
    assert sized is not None
    assert [a.size for a in sized] == [100, 80]


def test_exterior_angle_with_its_interior_neighbour_stated_labels_both() -> None:
    question = (
        "In triangle ABC, BC is produced to D. Angle ACD = 110°, angle ACB = 70° and angle "
        "A = 50°. Find angle B."
    )
    reading = _angles(
        "triangle",
        vertices="ABC",
        measures=[("exterior_angle", "ACD", 110), ("angle", "ACB", 70), ("angle", "A", 50)],
    )
    spec = figure(question, reading)
    assert labels(spec) == ["110°", "50°", "70°"]
    assert labelled_angle(spec, "70°") == pytest.approx(70)
    assert angle(spec, "C", "A", "B") == pytest.approx(70)
    assert angle(spec, "B", "A", "C") == pytest.approx(60)
