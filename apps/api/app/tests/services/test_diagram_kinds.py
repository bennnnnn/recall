"""Which words name a diagram the app draws itself."""

from __future__ import annotations

import pytest

from app.services.diagram_kinds import names_diagram_kind


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
