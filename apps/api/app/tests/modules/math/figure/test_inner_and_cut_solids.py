"""A sphere inside a cylinder or a cube, and a cone cut parallel to its base: drawn true to
the stated sizes, worked ones unlabelled, or not at all (the hard-geometry round,
2026-11-21)."""

from __future__ import annotations

from typing import Any

import pytest

from .figure_support import draw, figure, labelled_length, labels


def _solid(shape: str, *measures: tuple[str, float, str], **more: Any) -> dict[str, Any]:
    return {
        "kind": "solid",
        "shape": shape,
        "unit": "cm",
        "measures": [{"what": w, "value": v, "of": of} for w, v, of in measures],
        **more,
    }


def _extent(spec: Any) -> tuple[float, float]:
    xs, ys = [p.x for p in spec.points], [p.y for p in spec.points]
    return max(xs) - min(xs), max(ys) - min(ys)


SPHERE_IN = (
    "A sphere of radius 5 cm fits exactly inside a right circular cylinder. Find the "
    "cylinder's radius and height."
)


@pytest.mark.parametrize(
    "reading",
    [
        _solid("cylinder", ("radius", 5, ""), attached="sphere"),
        _solid("cylinder", ("radius", 5, ""), inscribed="sphere"),
        _solid("sphere", ("radius", 5, ""), attached="cylinder"),
    ],
)
def test_sphere_fitting_a_cylinder_makes_it_its_diameter_tall(reading: dict[str, Any]) -> None:
    spec = figure(SPHERE_IN, reading)
    assert spec.shape == "sphere_in_cylinder"
    assert labels(spec) == ["5 cm"]  # the cylinder's radius 5 and height 10 are worked
    assert _extent(spec) == pytest.approx((10, 10))
    assert labelled_length(spec, "5 cm") == pytest.approx(5)
    assert 5 in [arc.rx for arc in spec.arcs if arc.rx == arc.ry]


@pytest.mark.parametrize(
    ("question", "reading", "sizes", "label_count"),
    [
        (
            "A sphere fits exactly inside a cylinder of height 10 cm.",
            _solid("cylinder", ("height", 10, ""), inscribed="sphere"),
            (10, 10),
            1,
        ),
        (
            "A ball of radius 3 cm is placed inside a cylinder of radius 5 cm and height 12 cm.",
            _solid(
                "cylinder",
                ("radius", 3, "sphere"),
                ("radius", 5, "cylinder"),
                ("height", 12, ""),
                inscribed="sphere",
            ),
            (10, 12),
            3,
        ),
    ],
)
def test_sphere_in_a_cylinder_from_any_stated_size(
    question: str, reading: dict[str, Any], sizes: tuple[float, float], label_count: int
) -> None:
    spec = figure(question, reading)
    assert _extent(spec) == pytest.approx(sizes)
    assert len(labels(spec)) == label_count


def test_sphere_in_a_cube_labels_the_cube_edge() -> None:
    question = (
        "A ball fits exactly inside a cubical box of edge 10 cm. Find the volume of the ball."
    )
    spec = figure(question, _solid("cube", ("edge", 10, ""), inscribed="sphere"))
    assert spec.shape == "sphere_in_cube"
    assert labels(spec) == ["10 cm"]
    assert any(arc.rx == arc.ry == pytest.approx(5) for arc in spec.arcs)


@pytest.mark.parametrize(
    ("question", "reading"),
    [
        # Wider than what holds it.
        (
            "A ball of radius 6 cm is placed inside a cylinder of radius 5 cm.",
            _solid(
                "cylinder", ("radius", 6, "sphere"), ("radius", 5, "cylinder"), inscribed="sphere"
            ),
        ),
        # Taller than what holds it.
        (
            "A sphere of radius 5 cm is placed inside a cylinder of height 8 cm.",
            _solid("cylinder", ("radius", 5, ""), ("height", 8, ""), inscribed="sphere"),
        ),
        # On top, not inside: a solid made of two that no stack draws.
        (
            "A sphere of radius 5 cm sits on top of a cylinder of radius 5 cm and height 8 cm.",
            _solid("cylinder", ("radius", 5, ""), ("height", 8, ""), attached="sphere"),
        ),
    ],
)
def test_sphere_that_does_not_fit_draws_nothing(question: str, reading: dict[str, Any]) -> None:
    assert draw(question, reading) is None


CUT = (
    "A cone is cut parallel to its base, creating a frustum. The original cone has height "
    "24 cm and base radius 12 cm. The smaller cone removed has height 8 cm. Find the volume "
    "of the frustum."
)


def test_cut_cone_draws_the_frustum_and_the_cone_cut_off_true_to_scale() -> None:
    reading = _solid(
        "frustum", ("height", 24, ""), ("radius", 12, "original_cone"), ("height", 8, "cone")
    )
    spec = figure(CUT, reading)
    assert labels(spec) == ["12 cm", "24 cm", "8 cm"]
    for label, size in (("12 cm", 12), ("24 cm", 24), ("8 cm", 8)):
        assert labelled_length(spec, label) == pytest.approx(size)
    # The cut's radius (4) is worked: drawn, unlabelled.
    assert sorted(arc.rx for arc in spec.arcs) == pytest.approx([4, 12, 12])
    assert sum(s.dashed for s in spec.segments) >= 4  # the part cut off, the axis, the radii


@pytest.mark.parametrize(
    ("question", "reading", "cut_at", "top"),
    [
        (
            "A cone of height 30 cm and base radius 15 cm is cut parallel to its base 10 cm "
            "from the top. Find the volume of the frustum.",
            _solid("frustum", ("height", 30, ""), ("radius", 15, ""), ("height", 10, "")),
            20,
            5,
        ),
        (
            "A cone of height 30 cm and base radius 15 cm is cut parallel to its base 10 cm "
            "from the top. Find the volume of the part left.",
            _solid("cone", ("height", 30, ""), ("radius", 15, ""), ("height", 10, "")),
            20,
            5,
        ),
        (
            # The words name "a cone" without saying which; the read's tag says.
            "A cone of height 30 cm and base radius 15 cm is cut by a plane parallel to its "
            "base, 10 cm from its top. Find the volume of the frustum.",
            _solid(
                "frustum",
                ("height", 30, "original"),
                ("radius", 15, "original"),
                ("height", 10, "removed"),
            ),
            20,
            5,
        ),
        (
            # The cut's distance from the top read as a length: the cut-off cone's height.
            "A cone of height 30 cm and base radius 15 cm is cut by a plane parallel to its "
            "base, 10 cm from its top. Find the volume of the frustum.",
            _solid(
                "frustum",
                ("height", 30, "original"),
                ("radius", 15, "original"),
                ("length", 10, "removed"),
            ),
            20,
            5,
        ),
        (
            "The original cone has base radius 9 cm and height 12 cm. The small cone cut off "
            "has radius 3 cm.",
            _solid("cone", ("radius", 9, ""), ("height", 12, ""), ("radius", 3, "")),
            8,
            3,
        ),
        (
            "A cone of height 24 cm is cut parallel to its base to make a frustum of height "
            "16 cm and base radius 6 cm.",
            _solid("frustum", ("height", 24, ""), ("height", 16, ""), ("radius", 6, "")),
            16,
            2,
        ),
    ],
)
def test_cut_cone_from_any_values_that_fix_the_cut(
    question: str, reading: dict[str, Any], cut_at: float, top: float
) -> None:
    spec = figure(question, reading)
    assert spec.shape == "frustum"
    assert any(p.dot and p.y == pytest.approx(cut_at) for p in spec.points)
    assert min(arc.rx for arc in spec.arcs) == pytest.approx(top)


@pytest.mark.parametrize(
    ("question", "reading"),
    [
        # The small cone's radius disagrees with its height (8 of 24 is a third: 4, not 5).
        (
            "The original cone has height 24 cm and base radius 12 cm. The smaller cone "
            "removed has height 8 cm and radius 5 cm.",
            _solid(
                "frustum",
                ("height", 24, ""),
                ("radius", 12, ""),
                ("height", 8, ""),
                ("radius", 5, ""),
            ),
        ),
        # The part cut off is no smaller than the whole.
        (
            "The original cone has height 8 cm and base radius 12 cm. The smaller cone "
            "removed has height 24 cm.",
            _solid("frustum", ("height", 8, ""), ("radius", 12, ""), ("height", 24, "")),
        ),
    ],
)
def test_cut_cone_that_cannot_hold_draws_nothing(question: str, reading: dict[str, Any]) -> None:
    assert draw(question, reading) is None


@pytest.mark.parametrize(
    ("question", "reading", "shape"),
    [
        (
            "A cone has height 24 cm and radius 12 cm. Find its volume.",
            _solid("cone", ("height", 24, ""), ("radius", 12, "")),
            "cone",
        ),
        (
            "A bucket is a frustum of a cone with top radius 15 cm, bottom radius 10 cm and "
            "slant height 13 cm. Find its depth and capacity.",
            _solid("frustum", ("radius", 15, ""), ("radius", 10, ""), ("slant_height", 13, "")),
            "frustum",
        ),
    ],
)
def test_a_whole_cone_and_a_frustum_by_its_ends_are_drawn_as_before(
    question: str, reading: dict[str, Any], shape: str
) -> None:
    spec = figure(question, reading)
    assert spec.shape == shape
    assert not any(arc.rx < 9 for arc in spec.arcs if shape == "frustum")
