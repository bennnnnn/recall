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


@pytest.mark.parametrize(
    ("question", "angle"),
    [
        # Gravity's "downward" is no downward launch; an upward launch word wins.
        (
            "Gravity acts downward at 9.8 m/s^2, a ball is thrown upward at 20 m/s at 30 "
            "degrees from a 45 m cliff. Find the time of flight.",
            30.0,
        ),
        (
            "A ball is thrown downward at 15 m s^-1 at 30 degrees from the top of a 45 m "
            "cliff. Find the time to land.",
            -30.0,
        ),
    ],
)
def test_only_the_launch_verbs_own_direction_turns_the_angle(question: str, angle: float) -> None:
    intent = extract_physics_intent(question)
    assert intent is not None and (intent.physics_params or {}).get("angle") == angle


def test_an_angle_reference_is_read_after_a_degree_sign_with_no_space() -> None:
    """ "40° to the normal" and "60° to the vertical" (no space, the usual way) missed the
    guards (Gemini, PR #2490); an ask's "in degrees from the normal" is no angle's."""
    normal = extract_physics_intent(
        "Light is incident on the face of a prism (n = 1.5) at 40° to the normal to the "
        "face. Find the angle of refraction."
    )
    assert normal is not None and "from_surface" not in (normal.physics_params or {})
    vertical = "A ball is thrown at 20 m/s at 60° to the vertical. Find its range."
    assert extract_physics_intent(vertical) is None
    surface = extract_physics_intent(
        "A ray strikes a glass surface (n = 1.5) at 30° to the surface. Find the angle of "
        "refraction in degrees from the normal."
    )
    assert surface is not None and (surface.physics_params or {}).get("from_surface") == 1.0


@pytest.mark.parametrize(
    "question",
    [
        "A stone is kicked down off a 45 m cliff at 15 m/s at 30°. How long is it in the air?",
        "A ball is thrown downward at 15 m/s at 30 degrees from a 45 m cliff. "
        "How long is it in the air?",
    ],
)
def test_the_binder_reads_a_downward_launch_over_its_whole_sentence(question: str) -> None:
    """The binder read a launch's "down" only between the speed and the angle, so a
    downward verb before the speed bound +30° and certified 3.89 s for a 2.36 s flight
    (Gemini, PR #2490). It reads the sign with the extractor's own reader; an upward
    launch stays above the horizontal."""
    from app.modules.physics.binding import bind_physics_intent

    bound = bind_physics_intent(question)
    assert bound is not None and bound.physics_params is not None
    assert bound.physics_params["angle"] == -30.0
    upward = bind_physics_intent(
        question.replace("kicked down", "kicked up").replace("downward", "upward")
    )
    assert upward is not None and upward.physics_params is not None
    assert upward.physics_params["angle"] == 30.0
