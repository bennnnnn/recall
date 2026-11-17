"""Setups the physics reader read wrong, found by the scene reviews (2026-11-16): each one
gave a verified answer for another situation, and a scene drawn from it. The reader now
declines them, or reads them right."""

from __future__ import annotations

import pytest

from app.modules.physics.extract import extract_physics_intent


@pytest.mark.parametrize(
    "question",
    [
        # An angle from the vertical, read as an elevation.
        "A ball is thrown at 20 m/s at 60 degrees to the vertical. Find its range.",
        # A height it lands on, read as the height it was launched from.
        "A ball is thrown at 20 m/s at 50 degrees and lands on the roof of a 10 m high "
        "building. Find the time of flight.",
        # A collision's type asked about, read as stated.
        "A 2 kg cart moving at 3 m/s hits a 1 kg cart at rest and bounces back; they move "
        "apart. Is the collision elastic?",
    ],
)
def test_a_setup_the_reader_would_misread_is_declined(question: str) -> None:
    assert extract_physics_intent(question) is None


def test_an_angle_to_the_plane_of_a_block_is_measured_from_its_surface() -> None:
    intent = extract_physics_intent(
        "A light ray strikes a glass block (n = 1.5) at 30 degrees to the plane of the "
        "block. Find the angle of refraction."
    )
    assert intent is not None and (intent.physics_params or {}).get("from_surface") == 1.0


@pytest.mark.parametrize(
    "question",
    [
        "A stone is thrown from the top of a 45 m high cliff with a speed of 20 m/s at 30 "
        "degrees above the horizontal. Find the range.",
        "A 2 kg ball moving at 4 m/s collides with a 3 kg ball at rest. The balls stick "
        "together. Find their final velocity.",
        "A light ray passes from air into glass with refractive index 1.5 at an angle of "
        "incidence of 30 degrees. Find the angle of refraction.",
    ],
)
def test_the_textbook_wordings_are_still_read(question: str) -> None:
    assert extract_physics_intent(question) is not None


@pytest.mark.parametrize(
    "question",
    [
        "A ball is thrown down at an angle of 30 degrees at 15 m/s from the top of a 45 m "
        "cliff. Find the time to land.",
        "A ball is thrown downward at 15 m/s at 30 degrees to the horizontal from a 45 m "
        "cliff. Find the time to land.",
        "A ball is thrown at 15 m/s at 30 degrees below the horizontal from the top of a 45 m "
        "cliff. Find the time to land.",
    ],
)
def test_a_launch_downward_is_read_below_the_horizontal(question: str) -> None:
    """ "Thrown down at an angle of 30°" was read 30° above: a 45 m cliff's throw landed in
    3.89 s, not 2.36 s (review round 4, 2026-11-16)."""
    intent = extract_physics_intent(question)
    assert intent is not None and (intent.physics_params or {}).get("angle") == -30.0


@pytest.mark.parametrize(
    "question",
    [
        "A golf ball is hit at 40 m/s at 35 degrees and lands on a green at the same level. "
        "Find its range.",
        "A ball is kicked at 20 m/s at 30 degrees above the horizontal and lands on a level "
        "field. How far does it go?",
        "A stone is thrown horizontally at 12 m/s from a 45 m cliff onto a beach below. How "
        "long is it in the air?",
        "A ball is thrown horizontally at 10 m/s from a 20 m high cliff. Find its speed when "
        "it lands, and the angle it makes with the vertical.",
        "A projectile is launched at 25 m/s at 40 degrees above the horizontal onto a flat "
        "plain. Find the time of flight.",
    ],
)
def test_a_level_landing_and_an_asked_angle_with_the_vertical_are_still_read(
    question: str,
) -> None:
    """Round 3's excludes declined these level-ground questions; only a raised landing and
    a launch angle from the vertical are declined."""
    assert extract_physics_intent(question) is not None


def test_an_angle_to_the_normal_wins_over_a_face_after_it() -> None:
    intent = extract_physics_intent(
        "Light is incident on the face of a prism (n = 1.5) at 40 degrees to the normal to "
        "the face. Find the angle of refraction."
    )
    assert intent is not None and "from_surface" not in (intent.physics_params or {})
