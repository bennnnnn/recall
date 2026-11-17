"""Which words name a diagram the app draws itself."""

from __future__ import annotations

import pytest

from app.services.diagram_kinds import names_diagram_kind, names_idea_curve


@pytest.mark.parametrize(
    "text, expected",
    [
        ("a decision tree for choosing a language", True),
        ("Family Tree of the Tudors", True),
        ("our org chart", True),
        ("a state-machine for a turnstile", True),
        ("a mind map of renewable energy", True),
        ("a MINDMAP", True),
        ("the entity-relationship diagram", True),
        ("an ERD for the library", True),
        ("a gantt chart", True),
        ("a tree in autumn", False),
        ("a treasure map", False),
        ("a map of Ethiopia", False),
        ("the state of the union", False),
        ("a machine learning model", False),
        ("", False),
    ],
)
def test_names_diagram_kind(text: str, expected: bool) -> None:
    assert names_diagram_kind(text) is expected


@pytest.mark.parametrize(
    "phrase, expected",
    [
        ("the learning curve for a new language", True),
        ("a growth curve for my startup", True),
        ("a curve of how memory fades", True),
        ("an S-curve of adoption", True),
        ("the demand curve", True),
        # A picture's detail, an adjective, or a function's curve (maths').
        ("a winding mountain road with sharp curves at sunset", False),
        ("a woman with beautiful curves", False),
        ("a curved road at sunset", False),
        ("the curve y = x^2", False),
        ("the curve f(x) = sin x", False),
        ("", False),
    ],
)
def test_names_idea_curve(phrase: str, expected: bool) -> None:
    assert names_idea_curve(phrase) is expected


@pytest.mark.parametrize(
    "message",
    [
        "Find the area enclosed by f(x) = 4 - x² and g(x) = 3x. Show the curves and shade the region.",
        # Gemini on #2481: any function's name, not f alone.
        "Find the area enclosed by g(x) = 4 - x² and h(x) = 3x. Show the curves and shade the region.",
        "P(t) = 100e^{0.2t}. Show the curve.",
    ],
)
def test_a_curve_the_message_writes_a_formula_for_is_maths(message: str) -> None:
    assert not names_idea_curve("the curves and shade the region", message)


def test_an_idea_curve_beside_no_formula_is_a_chart() -> None:
    assert names_idea_curve(
        "the learning curve", "Draw the learning curve for French (a) and Spanish (b)."
    )
