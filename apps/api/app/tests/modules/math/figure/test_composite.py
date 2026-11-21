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


LONGER = (
    "A shape is a rectangle 10 cm by 6 cm with a semicircle on one of its longer sides. "
    "Find its perimeter."
)


def _semicircle_on(spec: Any) -> float:
    """The length of the side the semicircle stands on: its diameter."""
    (arc,) = spec.arcs
    return 2 * arc.rx


@pytest.mark.parametrize("parts", [[], ["longer_side"]])
def test_composite_semicircle_on_a_longer_side_stands_on_the_longer_side(parts: list[str]) -> None:
    reading = _two("rectangle", "semicircle", ("length", 10, ""), ("width", 6, ""), parts=parts)
    spec = figure(LONGER, reading)
    assert _semicircle_on(spec) == pytest.approx(10)
    assert labelled_length(spec, "10 cm") == pytest.approx(10)
    assert labelled_length(spec, "6 cm") == pytest.approx(6)
    (arc,) = spec.arcs
    assert at(spec, arc.center) == pytest.approx((5, 6))


def test_composite_semicircle_on_a_shorter_side_stands_on_the_shorter_side() -> None:
    question = "A rectangle 10 cm by 6 cm has a semicircle on each of its shorter sides."
    reading = _two("rectangle", "semicircle", ("length", 10, ""), ("width", 6, ""))
    assert _semicircle_on(figure(question, reading)) == pytest.approx(6)


@pytest.mark.parametrize(
    ("question", "measures", "parts"),
    [
        # A diameter as long as the shorter side, on a side the question calls longer.
        (LONGER, [("length", 10, ""), ("width", 6, ""), ("diameter", 6, "semicircle")], []),
        # One side stated: which one is the longer is not known.
        ("A rectangle 10 cm long has a semicircle on one of its longer sides.",
         [("length", 10, "")], []),
        # The question names both sides.
        ("A rectangle 10 cm by 6 cm has a semicircle on a longer side and a shorter side.",
         [("length", 10, ""), ("width", 6, "")], []),
        # A side named by a length the rectangle has not.
        ("A rectangle 10 cm by 6 cm has a semicircle on its 8 cm side.",
         [("length", 10, ""), ("width", 6, "")], []),
    ],
)  # fmt: skip
def test_composite_semicircle_on_a_side_the_reading_cannot_place_draws_nothing(
    question: str, measures: list[tuple[str, float, str]], parts: list[str]
) -> None:
    assert draw(question, _two("rectangle", "semicircle", *measures, parts=parts)) is None


@pytest.mark.parametrize(
    ("question", "parts", "across"),
    [
        (LONGER, ["shorter_side"], 10),
        ("A rectangle 10 cm by 6 cm with a semicircle on one side.", ["longer_side"], 6),
        (SEMICIRCLE, ["longer_side"], 6),
    ],
)
def test_composite_the_questions_words_name_the_side_never_the_read(
    question: str, parts: list[str], across: float
) -> None:
    reading = _two("rectangle", "semicircle", ("length", 10, ""), ("width", 6, ""), parts=parts)
    assert _semicircle_on(figure(question, reading)) == pytest.approx(across)


def test_composite_semicircle_s_diameter_read_twice_as_its_side() -> None:
    reading = _two(
        "rectangle",
        "semicircle",
        ("length", 10, ""),
        ("width", 6, ""),
        ("diameter", 6, "semicircle"),
        ("side", 6, "semicircle"),
    )
    spec = figure(SEMICIRCLE, reading)
    assert _semicircle_on(spec) == pytest.approx(6)
    assert labels(spec) == ["10 cm", "6 cm"]


def test_composite_semicircle_on_the_side_named_by_its_length() -> None:
    question = "A rectangle 10 cm by 6 cm has a semicircle on its 10 cm side. Find the area."
    reading = _two("rectangle", "semicircle", ("side", 10, ""), ("side", 6, ""))
    spec = figure(question, reading)
    assert _semicircle_on(spec) == pytest.approx(10)
    assert labels(spec) == ["10 cm", "6 cm"]


def test_composite_semicircle_on_top_of_a_standing_shape_is_on_its_width() -> None:
    question = "A window is a rectangle 2 m wide and 1 m tall with a semicircle on top."
    reading = _two("rectangle", "semicircle", ("width", 2, ""), ("height", 1, ""), unit="m")
    spec = figure(question, reading)
    assert _semicircle_on(spec) == pytest.approx(2)
    assert labelled_length(spec, "1 m") == pytest.approx(1)


def test_composite_gable_on_a_shorter_side_stands_on_the_shorter_side() -> None:
    question = "A rectangle 10 m by 4 m has an equilateral triangle on one of its shorter sides."
    reading = _two(
        "rectangle", "equilateral_triangle", ("length", 10, ""), ("width", 4, ""), unit="m"
    )
    spec = figure(question, reading)
    apex = max(spec.points, key=lambda p: p.y)
    assert apex.y == pytest.approx(10 + 4 * 3**0.5 / 2)
    assert labelled_length(spec, "4 m") == pytest.approx(4)
