"""Frustums, a regular tetrahedron, solids made of round parts, and a box's space
diagonal, each drawn to its stated sizes or not at all."""

from __future__ import annotations

import math
from typing import Any

import pytest

from .figure_support import at, draw, figure, labelled_length, labels, length


def _solid(shape: str, *measures: tuple[str, float, str], **more: Any) -> dict[str, Any]:
    return {
        "kind": "solid",
        "shape": shape,
        "measures": [{"what": w, "value": v, "of": of} for w, v, of in measures],
        "unit": more.pop("unit", "cm"),
        **more,
    }


FRUSTUM = "A frustum of a cone has end radii 3 cm and 6 cm and a height of 4 cm. Find its volume."


def test_frustum_has_its_ends_and_height_true_to_scale() -> None:
    reading = _solid("frustum", ("radius", 3, ""), ("radius", 6, ""), ("height", 4, ""))
    spec = figure(FRUSTUM, reading)
    assert labels(spec) == ["3 cm", "4 cm", "6 cm"]
    for label, size in (("3 cm", 3), ("4 cm", 4), ("6 cm", 6)):
        assert labelled_length(spec, label) == pytest.approx(size)
    assert sorted(arc.rx for arc in spec.arcs) == pytest.approx([3, 6, 6])


def test_frustum_from_its_slant_height() -> None:
    question = "A bucket is a frustum with radii 15 cm and 10 cm and slant height 13 cm."
    reading = _solid("frustum", ("radius", 15, ""), ("radius", 10, ""), ("slant_height", 13, ""))
    spec = figure(question, reading)
    assert labelled_length(spec, "13 cm") == pytest.approx(13)
    assert max(p.y for p in spec.points) == pytest.approx(12)


@pytest.mark.parametrize(
    "measures",
    [
        [("radius", 3, ""), ("radius", 6, ""), ("height", 4, ""), ("slant_height", 6, "")],
        [("radius", 3, ""), ("radius", 3, ""), ("height", 4, "")],
        [("radius", 3, ""), ("radius", 6, ""), ("slant_height", 2, "")],
    ],
)
def test_frustum_that_cannot_hold_draws_nothing(measures: list[tuple[str, float, str]]) -> None:
    question = "A frustum of a cone has radii 3 cm and 6 cm, height 4 cm, slant 6 cm or 2 cm."
    assert draw(question, _solid("frustum", *measures)) is None


def test_pyramid_frustum_labels_both_square_ends_and_its_height() -> None:
    question = "A frustum of a square pyramid has a base of side 12 cm, a top of 6 cm and a height of 4 cm."
    reading = _solid("square_frustum", ("edge", 12, ""), ("edge", 6, ""), ("height", 4, ""))
    spec = figure(question, reading)
    assert labels(spec) == ["12 cm", "4 cm", "6 cm"]
    assert sum(s.dashed for s in spec.segments) >= 3  # hidden edges and the height


def test_pyramid_frustum_with_equal_ends_draws_nothing() -> None:
    question = "A frustum of a square pyramid has ends of 6 cm and 6 cm and a height of 4 cm."
    reading = _solid("square_frustum", ("edge", 6, ""), ("edge", 6, ""), ("height", 4, ""))
    assert draw(question, reading) is None


def test_tetrahedron_labels_an_edge_in_sight() -> None:
    question = "Find the surface area of a regular tetrahedron with edges of 6 cm."
    spec = figure(question, _solid("tetrahedron", ("edge", 6, "")))
    labelled = next(s for s in spec.segments if s.label)
    assert labelled.label == "6 cm" and not labelled.dashed
    assert len(spec.segments) == 6


def test_tetrahedron_with_two_edge_lengths_draws_nothing() -> None:
    question = "A regular tetrahedron has edges of 6 cm and 7 cm."
    reading = _solid("tetrahedron", ("edge", 6, ""), ("edge", 7, ""))
    assert draw(question, reading) is None


TOY = "A toy is a cone of height 8 cm standing on a hemisphere of radius 6 cm. Find its volume."


def test_stacked_cone_on_hemisphere_shares_the_radius() -> None:
    reading = _solid(
        "hemisphere",
        ("height", 8, "cone"),
        ("radius", 6, "hemisphere"),
        attached="cone",
    )
    spec = figure(TOY, reading)
    assert labels(spec) == ["6 cm", "8 cm"]
    assert labelled_length(spec, "6 cm") == pytest.approx(6)
    assert labelled_length(spec, "8 cm") == pytest.approx(8)
    assert max(p.y for p in spec.points) == pytest.approx(6 + 8)
    bowl = next(arc for arc in spec.arcs if arc.rx == arc.ry)
    assert (bowl.start, bowl.end) == (180, 360)


def test_stacked_capsule_has_a_hemisphere_at_each_end() -> None:
    question = (
        "A capsule is a cylinder of length 10 mm with a hemisphere of radius 3 mm at each end."
    )
    reading = _solid(
        "cylinder",
        ("height", 10, "cylinder"),
        ("radius", 3, ""),
        attached="hemispheres",
        unit="mm",
    )
    spec = figure(question, reading)
    round_ends = [arc for arc in spec.arcs if arc.rx == arc.ry]
    assert len(round_ends) == 2
    assert labelled_length(spec, "10 mm") == pytest.approx(10)
    assert max(p.y for p in spec.points) == pytest.approx(3 + 10 + 3)


def test_stacked_ice_cream_has_its_cone_pointing_down() -> None:
    question = "An ice-cream cone has radius 3 cm and height 12 cm with a hemisphere on top."
    reading = _solid("cone", ("radius", 3, ""), ("height", 12, "cone"), attached="hemisphere")
    spec = figure(question, reading)
    tip = min(spec.points, key=lambda p: p.y)
    assert (tip.x, tip.y) == pytest.approx((0, 0))
    assert labelled_length(spec, "12 cm") == pytest.approx(12)


def test_stacked_cone_slant_height_sets_its_height() -> None:
    question = "A cylinder of radius 3 cm and height 10 cm has a cone of slant height 5 cm on top."
    reading = _solid(
        "cylinder",
        ("radius", 3, ""),
        ("height", 10, "cylinder"),
        ("slant_height", 5, "cone"),
        attached="cone",
    )
    spec = figure(question, reading)
    assert max(p.y for p in spec.points) == pytest.approx(10 + 4)
    assert labelled_length(spec, "5 cm") == pytest.approx(5)


@pytest.mark.parametrize(
    "measures",
    [
        # Radii that disagree.
        [("radius", 6, "hemisphere"), ("radius", 5, "cone"), ("height", 8, "cone")],
        # The whole toy's height is no part's.
        [("radius", 6, ""), ("height", 14, "total")],
        # A slant no longer than the radius.
        [("radius", 6, ""), ("slant_height", 5, "cone")],
    ],
)
def test_stacked_values_that_do_not_fit_draw_nothing(
    measures: list[tuple[str, float, str]],
) -> None:
    question = "A cone on a hemisphere: radii 6 cm and 5 cm, height 8 cm, 14 cm tall, slant 5 cm."
    assert draw(question, _solid("hemisphere", *measures, attached="cone")) is None


CUBOID = "Find the length of the longest diagonal of a cuboid measuring 3 cm by 4 cm by 12 cm."


def test_box_space_diagonal_runs_through_the_inside() -> None:
    reading = _solid(
        "cuboid",
        ("length", 12, ""),
        ("width", 4, ""),
        ("height", 3, ""),
        parts=["diagonals"],
    )
    spec = figure(CUBOID, reading)
    diagonal = spec.segments[-1]
    assert diagonal.dashed and diagonal.label is None
    ends = {at(spec, diagonal.a), at(spec, diagonal.b)}
    corners = sorted(at(spec, p.name) for p in spec.points[:8])
    assert ends <= set(corners)


def test_box_stated_diagonal_decides_the_missing_size() -> None:
    question = "A cuboid is 3 cm by 4 cm and its space diagonal is 13 cm. Find its height."
    reading = _solid("cuboid", ("length", 3, ""), ("width", 4, ""), ("diagonal", 13, ""))
    spec = figure(question, reading)
    assert spec.segments[-1].label == "13 cm"
    assert length(spec, spec.points[0].name, spec.points[4].name) == pytest.approx(
        12 * math.cos(math.asin(0.3))
    )


def test_box_diagonal_that_disagrees_draws_nothing() -> None:
    question = "A cuboid 3 cm by 4 cm by 12 cm has a diagonal of 14 cm."
    reading = _solid(
        "cuboid", ("length", 3, ""), ("width", 4, ""), ("height", 12, ""), ("diagonal", 14, "")
    )
    assert draw(question, reading) is None
