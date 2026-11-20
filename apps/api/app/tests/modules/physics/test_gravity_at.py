"""One reader of a stated g, for the binder and ``detect_gravity`` alike (``gravity_at``)."""

from __future__ import annotations

import pytest

from app.modules.physics.extractors.surface_gravity import (
    detect_gravity,
    gravity_at,
    gravity_unit_unread,
    stated_gravity,
    stated_gravity_spans,
)


@pytest.mark.parametrize(
    ("text", "value", "is_g"),
    [
        ("On the Moon, where g = 1.62 m/s², a rock is dropped.", "1.62", True),
        ("Take 10 m/s^2 for g.", "10", True),
        ("Taking 10 m/s² as g, find the weight.", "10", True),
        ("Take 9.8 m/s² as the acceleration due to gravity.", "9.8", True),
        ("A gravitational acceleration of 3.7 m/s² acts on it.", "3.7", True),
        ("The acceleration due to gravity is 3.7 m/s².", "3.7", True),
        # Every spelling of a stated g (Claude on #2491).
        ("Take g as 10 m/s². Find the weight of a 2 kg mass.", "10", True),
        ("Take g = 10. Find the weight of a 2 kg mass.", "10", True),
        ("Assume g \u2248 9.8 m/s².", "9.8", True),
        ("Here g is 9.8 m/s².", "9.8", True),
        ("g: 9.81 m/s²", "9.81", True),
        ("Take g to be 10 m/s².", "10", True),
        # Joined by "is equal to" or "equals" (g7-047: no g, the weight declined).
        ("On the moon, whose acceleration due to gravity is equal to 1.63 m/s2.", "1.63", True),
        ("The acceleration due to gravity equals 3.7 m/s².", "3.7", True),
        ("Here g is equal to 9.8 m/s².", "9.8", True),
        ("A gravitational acceleration equal to 4 m/s².", "4", True),
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
    assert detect_gravity("Take g as 10 m/s². Find the weight of a 2 kg mass.") == 10.0


@pytest.mark.parametrize(
    "text",
    [
        # A "g" right after a number is grams (Gemini on #2491: g = 15 certified 300 J).
        "The upward acceleration of a model rocket of 500 g is 15 m/s² as it rises 40 m.",
        "A ball of mass 500 g is 20 m above the ground.",
        # A value in a unit of another kind is no g: "gravity of 5 kg" is a mass.
        "Find the potential energy due to gravity of 5 kg at a height of 2 m.",
    ],
)
def test_a_mass_is_never_a_stated_g(text: str) -> None:
    assert stated_gravity(text) is None
    assert not gravity_unit_unread(text)
    assert detect_gravity(text) == 9.81


def test_a_g_beside_a_mass_in_grams_is_still_read() -> None:
    assert stated_gravity("A 500 g ball is lifted 2 m with g = 10 m/s².") == 10.0
    assert stated_gravity("A 500 g ball, g = 32 ft/s².") == pytest.approx(9.7536)
    # A unit nothing reads is still a g, declined as unread.
    assert gravity_unit_unread("Take g = 10 zorb/s^2.")


def test_stated_gravity_spans_cover_label_value_and_unit() -> None:
    text = "A ball is kicked at 20 m/s at 30°. Use 10 m/s^2 for g. Find the range."
    assert [text[start:end] for start, end in stated_gravity_spans(text)] == ["10 m/s^2 for g"]
    text = "Here g = 9.8 m/s^2 and a 500 g ball."
    assert [text[start:end] for start, end in stated_gravity_spans(text)] == ["g = 9.8 m/s^2"]


def _verified(text: str) -> str | None:
    from app.core.config import Settings
    from app.modules.physics import build_verified_physics_block, extract_physics_intent

    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, Settings(math_tools_enabled=True))
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # A world's "acceleration due to gravity" is its g, whatever owns it (g7-047).
        (
            "How much does a 100 kg body weight on the surface of the moon whose acceleration "
            "due to gravity is equal to 1.63 m/s2?",
            "163 N",
        ),
        (
            "What is the weight of a 100 kg body on Mars whose acceleration due to gravity "
            "is 3.7 m/s2?",
            "370 N",
        ),
    ],
)
def test_a_worlds_acceleration_due_to_gravity_is_its_g(text: str, answer: str) -> None:
    assert _verified(text) == answer


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # A falling body's own acceleration is no g (Claude on #2491: 3600 J for 11,772 J).
        (
            "A 60 kg skier drops into the run and accelerates at 3.00 m/s² down the slope. "
            "What is her potential energy loss after descending 20 m?",
            None,
        ),
        # At the scene's g, or on a world the question names, it is g.
        (
            "A ball dropped from a 45 m tower accelerates at 9.8 m/s². How long does it take "
            "to reach the ground?",
            "3.03 s",
        ),
        (
            "On planet X, a dropped rock accelerates at 4.0 m/s². How long does it take to "
            "fall 10 m?",
            "2.24 s",
        ),
    ],
)
def test_a_falling_bodys_own_acceleration_is_g_only_at_its_worlds_g(
    text: str, answer: str | None
) -> None:
    assert _verified(text) == answer
