"""Similar triangles side by side to one scale, and shadows cast at one time."""

from __future__ import annotations

from typing import Any

import pytest

from .figure_support import angle, at, draw, figure, labels, length

SIMILAR = "Triangles ABC and DEF are similar with AB = 4 cm, BC = 5 cm and DE = 6 cm. Find EF."
SHADOW = "A 2 m pole casts a shadow of 3 m. At the same time a tree casts a shadow of 18 m."


def _sides(*sides: tuple[str, float]) -> list[dict[str, Any]]:
    return [{"what": "side", "name": name, "value": value} for name, value in sides]


def _similar(*sides: tuple[str, float], vertices: str = "ABCDEF") -> dict[str, Any]:
    return {
        "kind": "polygon",
        "shape": "similar_triangles",
        "vertices": vertices,
        "measures": _sides(*sides),
        "unit": "cm",
    }


def test_similar_the_second_triangle_is_the_first_at_the_stated_scale() -> None:
    spec = figure(SIMILAR, _similar(("AB", 4), ("BC", 5), ("DE", 6)))
    assert labels(spec) == ["4 cm", "5 cm", "6 cm"]
    assert length(spec, "D", "E") == pytest.approx(6)
    assert length(spec, "E", "F") == pytest.approx(7.5)
    assert length(spec, "D", "F") == pytest.approx(1.5 * length(spec, "A", "C"))
    for first, second in (("A", "D"), ("B", "E"), ("C", "F")):
        others = [n for n in "ABC" if n != first]
        theirs = [n for n in "DEF" if n != second]
        assert angle(spec, first, *others) == pytest.approx(angle(spec, second, *theirs))
    assert {p.name for p in spec.points if p.show} == set("ABCDEF")


def test_similar_triangles_do_not_overlap() -> None:
    spec = figure(SIMILAR, _similar(("AB", 4), ("BC", 5), ("DE", 6)))
    assert max(at(spec, n)[0] for n in "ABC") < min(at(spec, n)[0] for n in "DEF")


def test_similar_a_stated_angle_is_marked_on_its_own_triangle() -> None:
    question = "Triangles ABC and DEF are similar. AB = 3, DE = 6, EF = 8 and angle E = 70°."
    reading = _similar(("AB", 3), ("DE", 6), ("EF", 8))
    reading["measures"].append({"what": "angle", "name": "E", "value": 70})
    reading["unit"] = ""
    spec = figure(question, reading)
    assert angle(spec, "E", "D", "F") == pytest.approx(70)
    assert angle(spec, "B", "A", "C") == pytest.approx(70)
    assert next(a for a in spec.angles if a.label == "70°").at == "E"


@pytest.mark.parametrize(
    ("question", "sides", "vertices"),
    [
        (
            "ABC ~ DEF with AB = 4, BC = 5, DE = 6 and EF = 8.",
            [("AB", 4), ("BC", 5), ("DE", 6), ("EF", 8)],
            "ABCDEF",
        ),
        ("ABC ~ DEF with AB = 4 and EF = 8.", [("AB", 4), ("EF", 8)], "ABCDEF"),
        ("ABC ~ DE with AB = 4 and DE = 8.", [("AB", 4), ("DE", 8)], "ABCDE"),
    ],
)
def test_similar_no_single_scale_draws_nothing(
    question: str, sides: list[tuple[str, float]], vertices: str
) -> None:
    reading = _similar(*sides, vertices=vertices)
    reading["unit"] = ""
    assert draw(question, reading) is None


def _shadows(*measures: tuple[str, float, str]) -> dict[str, Any]:
    return {
        "kind": "polygon",
        "shape": "shadows",
        "measures": [{"what": w, "value": v, "of": of} for w, v, of in measures],
        "unit": "m",
    }


def _uprights(spec: Any) -> list[float]:
    return sorted(
        length(spec, s.a, s.b)
        for s in spec.segments
        if at(spec, s.a)[0] == pytest.approx(at(spec, s.b)[0])
    )


def test_shadows_the_tree_stands_at_the_height_the_pole_decides() -> None:
    spec = figure(
        SHADOW, _shadows(("height", 2, "pole"), ("shadow", 3, "pole"), ("shadow", 18, "tree"))
    )
    assert labels(spec) == ["18 m", "2 m", "3 m"]
    assert _uprights(spec) == pytest.approx([2, 12])
    assert sum(mark.right for mark in spec.angles) == 2


def test_shadows_objects_named_by_name_are_told_apart() -> None:
    reading = _shadows(("height", 2, ""), ("shadow", 3, ""), ("shadow", 18, ""))
    for measure, name in zip(reading["measures"], ("pole", "pole", "tree"), strict=True):
        measure["name"] = name
    assert _uprights(figure(SHADOW, reading)) == pytest.approx([2, 12])


@pytest.mark.parametrize(
    "measures",
    [
        # Two objects whose shadows disagree on the sun.
        [
            ("height", 2, "pole"),
            ("shadow", 3, "pole"),
            ("height", 5, "tree"),
            ("shadow", 6, "tree"),
        ],
        # Values the reading does not tell apart.
        [("height", 2, ""), ("shadow", 3, ""), ("shadow", 18, "")],
        # No object with both, and no sun.
        [("height", 2, "pole"), ("shadow", 18, "tree")],
    ],
)
def test_shadows_that_cannot_hold_draw_nothing(measures: list[tuple[str, float, str]]) -> None:
    question = "A 2 m pole casts a 3 m shadow; a 5 m tree casts a 6 m shadow and one of 18 m."
    assert draw(question, _shadows(*measures)) is None
