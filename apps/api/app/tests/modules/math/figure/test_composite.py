"""A rectangle or a square with a second shape joined to it: a semicircle on (or cut out
of) a side, a gable on top, a second rectangle making an L."""

from __future__ import annotations

from typing import Any

import pytest

from .figure_support import at, draw, figure, labelled_length, labels

SEMICIRCLE = (
    "A shape is made of a rectangle 10 cm by 6 cm with a semicircle on one of its 6 cm sides. "
    "Find its perimeter."
)
L_SHAPE = "An L-shaped room is made of a 6 m by 4 m rectangle joined to a 3 m by 2 m rectangle."


def _two(
    shape: str, attached: str, *measures: tuple[str, float, str], unit: str = "cm", **more: Any
) -> dict[str, Any]:
    return {
        "kind": "polygon",
        "shape": shape,
        "attached": attached,
        "measures": [{"what": w, "value": v, "of": of} for w, v, of in measures],
        "unit": unit,
        **more,
    }


def _area(spec: Any) -> float:
    face = [at(spec, name) for name in spec.faces[0]]
    return (
        abs(
            sum(
                x1 * y2 - x2 * y1
                for (x1, y1), (x2, y2) in zip(face, face[1:] + face[:1], strict=True)
            )
        )
        / 2
    )


def test_composite_semicircle_stands_on_the_side_its_diameter_names() -> None:
    reading = _two(
        "rectangle",
        "semicircle",
        ("length", 10, ""),
        ("width", 6, ""),
        ("diameter", 6, "semicircle"),
    )
    spec = figure(SEMICIRCLE, reading)
    assert labels(spec) == ["10 cm", "6 cm"]
    assert labelled_length(spec, "6 cm") == pytest.approx(6)
    assert labelled_length(spec, "10 cm") == pytest.approx(10)
    (arc,) = spec.arcs
    assert (arc.rx, arc.start, arc.end) == (pytest.approx(3), 0, 180)
    assert at(spec, arc.center) == pytest.approx((3, 10))


def test_composite_window_takes_its_width_along_and_height_up() -> None:
    question = "A window is a rectangle 1.2 m wide and 1.5 m tall with a semicircle on top."
    reading = _two("rectangle", "semicircle", ("width", 1.2, ""), ("height", 1.5, ""), unit="m")
    spec = figure(question, reading)
    assert labelled_length(spec, "1.2 m") == pytest.approx(1.2)
    assert labelled_length(spec, "1.5 m") == pytest.approx(1.5)
    assert spec.arcs[0].rx == pytest.approx(0.6)


def test_composite_semicircle_cut_out_bites_into_the_shape() -> None:
    question = "A semicircle of radius 3 cm is cut out of one end of a rectangle 10 cm by 6 cm."
    reading = _two(
        "rectangle",
        "semicircle",
        ("length", 10, ""),
        ("width", 6, ""),
        ("radius", 3, "semicircle"),
        parts=["cut"],
    )
    spec = figure(question, reading)
    (arc,) = spec.arcs
    assert (arc.start, arc.end) == (180, 360)
    assert labelled_length(spec, "3 cm") == pytest.approx(3)
    assert not spec.faces  # the hole is not filled


@pytest.mark.parametrize(
    ("question", "measures", "parts"),
    [
        (
            "A rectangle 10 cm by 6 cm with a semicircle of diameter 8 cm on a side.",
            [("length", 10, ""), ("width", 6, ""), ("diameter", 8, "semicircle")],
            [],
        ),
        (
            "A semicircle is cut out of the 10 cm side of a rectangle 10 cm by 2 cm.",
            [("length", 2, ""), ("width", 10, ""), ("diameter", 10, "")],
            ["cut"],
        ),
    ],
)
def test_composite_semicircle_that_cannot_fit_draws_nothing(
    question: str, measures: list[tuple[str, float, str]], parts: list[str]
) -> None:
    assert draw(question, _two("rectangle", "semicircle", *measures, parts=parts)) is None


def test_composite_gable_rises_as_its_sloping_sides_decide() -> None:
    question = (
        "The front of a shed is a rectangle 8 m wide and 4 m high with an isosceles triangle "
        "on top whose sloping sides are 5 m long."
    )
    reading = _two(
        "rectangle",
        "triangle",
        ("width", 8, ""),
        ("height", 4, ""),
        ("equal_side", 5, ""),
        unit="m",
    )
    spec = figure(question, reading)
    assert labels(spec) == ["4 m", "5 m", "8 m"]
    assert max(p.y for p in spec.points) == pytest.approx(4 + 3)
    assert _area(spec) == pytest.approx(8 * 4 + 8 * 3 / 2)


def test_composite_equilateral_gable_on_a_square_labels_the_side_once() -> None:
    question = "A house shape is a square of side 6 m with an equilateral triangle on top."
    reading = _two("square", "equilateral_triangle", ("side", 6, ""), unit="m")
    spec = figure(question, reading)
    assert labels(spec) == ["6 m"]
    assert max(p.y for p in spec.points) == pytest.approx(6 + 6 * 3**0.5 / 2)


def test_composite_gable_too_short_to_meet_draws_nothing() -> None:
    question = "A rectangle 8 m by 4 m has a triangle on top with sloping sides of 3 m."
    reading = _two(
        "rectangle", "triangle", ("length", 8, ""), ("width", 4, ""), ("side", 3, "triangle")
    )
    assert draw(question, reading) is None


def test_composite_l_shape_is_both_rectangles_at_their_sizes() -> None:
    reading = _two(
        "rectangle",
        "rectangle",
        ("length", 6, ""),
        ("width", 4, ""),
        ("length", 3, "second"),
        ("width", 2, "second"),
        unit="m",
    )
    spec = figure(L_SHAPE, reading)
    assert labels(spec) == ["2 m", "3 m", "4 m", "6 m"]
    for label, size in (("2 m", 2), ("3 m", 3), ("4 m", 4), ("6 m", 6)):
        assert labelled_length(spec, label) == pytest.approx(size)
    assert _area(spec) == pytest.approx(6 * 4 + 3 * 2)
    assert sum(s.dashed for s in spec.segments) == 1


def test_composite_l_shape_read_in_order_without_of() -> None:
    reading = _two(
        "rectangle",
        "rectangle",
        ("length", 6, ""),
        ("width", 4, ""),
        ("length", 3, ""),
        ("width", 2, ""),
        unit="m",
    )
    assert _area(figure(L_SHAPE, reading)) == pytest.approx(30)


def test_composite_second_rectangle_too_wide_draws_nothing() -> None:
    question = "A 3 m by 2 m rectangle is joined to an 8 m by 7 m rectangle."
    reading = _two(
        "rectangle",
        "rectangle",
        ("length", 3, ""),
        ("width", 2, ""),
        ("length", 8, "second"),
        ("width", 7, "second"),
        unit="m",
    )
    assert draw(question, reading) is None


def test_composite_attached_shape_the_question_never_names_draws_nothing() -> None:
    question = "A rectangle is 10 cm by 6 cm. Find its perimeter."
    reading = _two("rectangle", "semicircle", ("length", 10, ""), ("width", 6, ""))
    assert draw(question, reading) is None
