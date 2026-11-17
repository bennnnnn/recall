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
