"""One reader of a stated g, for the binder and ``detect_gravity`` alike (``gravity_at``)."""

from __future__ import annotations

import pytest

from app.modules.physics.extractors.surface_gravity import detect_gravity, gravity_at


@pytest.mark.parametrize(
    ("text", "value", "is_g"),
    [
        ("On the Moon, where g = 1.62 m/s², a rock is dropped.", "1.62", True),
        ("Take 10 m/s^2 for g.", "10", True),
        ("Taking 10 m/s² as g, find the weight.", "10", True),
        ("Take 9.8 m/s² as the acceleration due to gravity.", "9.8", True),
        ("A gravitational acceleration of 3.7 m/s² acts on it.", "3.7", True),
        ("The acceleration due to gravity is 3.7 m/s².", "3.7", True),
        # The number right before the label, never an earlier one (Gemini on #2491).
        ("A block with \u03bc = 0.5 slides (10 N/kg for g).", "10", True),
        ("A block with \u03bc = 0.5 slides (10 N/kg for g).", "0.5", False),
        ("A lift accelerates upward at 2 m/s² (10 m/s² as g).", "2", False),
        ("A 2 kg book is raised 1.5 m (use 10 m/s² for g).", "1.5", False),
        ("A 2 kg book is raised 1.5 m (use 10 m/s² for g).", "10", True),
        # A body's own acceleration is no g.
        ("The cruiser accelerates from rest at 3.00 m/s² in the same direction.", "3.00", False),
        ("A car accelerates at 3 m/s² for 10 s.", "3", False),
    ],
)
def test_the_stated_g_is_read_at_its_value(text: str, value: str, is_g: bool) -> None:
    start = text.index(value)
    assert gravity_at(text, start, start + len(value)) is is_g


def test_detect_gravity_reads_a_g_named_after_its_value() -> None:
    assert detect_gravity("A 2 kg book is raised 1.5 m (take 10 m/s^2 for g).") == 10.0
