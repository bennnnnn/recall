"""The second review of the same twelve classes (2026-11-12): the first fixes read some of
them by the example's words, and one added a wrong answer of its own (another planet's moon
given the Moon's g). Each class is now read by its structure; each probe declines or is
right, and its look-alikes still verify. g = 9.81 m/s².
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.ask import asks_for_a_part
from app.modules.physics.bodies import names_another_moon, names_our_moon
from app.modules.physics.catalog import CATALOG
from app.modules.physics.frames import adds_speeds_across_frames
from app.modules.physics.motion import rolling_body
from app.modules.physics.net_force import in_a_lift, others_share_the_force
from app.modules.physics.prompt import solve_physics_request
from app.services.law_binding.inverse import same_part
from app.tests.modules.physics.support import answer_number

_SETTINGS = Settings.model_validate({})


def _verified(text: str) -> tuple[str, float]:
    outcome, block = solve_physics_request(text, _SETTINGS, None)
    assert outcome == "verified", text
    assert block is not None and block.physics_intent is not None
    return block.physics_intent.physics_op or "", answer_number(block.canonical_answer or "")


def _declined(text: str) -> bool:
    outcome, _block = solve_physics_request(text, _SETTINGS, None)
    return outcome != "verified"


@pytest.mark.parametrize(
    "text",
    [
        # Another body's moon took the Moon's g (81 N, 4.94 s, 7.72 m), Phobos Mars's.
        "On Europa, a moon of Jupiter, what is the weight of a 50 kg probe?",
        "A pendulum 1 m long swings on Callisto, a moon of Jupiter. What is its period?",
        "An astronaut on Io, a moon of Jupiter, throws a ball straight up at 5 m/s. How high "
        "does it go?",
        "An astronaut on Titan, Saturn's largest moon, drops a hammer from 2 m. How long does "
        "it take to fall?",
        "A 10 kg lander rests on the surface of Ganymede, the largest moon. What is its weight?",
        "A rock is dropped from 5 m on an icy moon. How long does it take to fall?",
        "Mars has two moons. On Phobos a rock is dropped from 2 m. How long does it fall?",
        "On Venus, a ball is dropped from 2 m. How long does it take to fall?",
    ],
)
def test_a_body_with_no_school_g_declines(text: str) -> None:
    assert _declined(text)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("An astronaut on the Moon drops a hammer from 2 m. How long does it take to fall?", 1.571),
        ("A 70 kg astronaut stands on Earth's moon. What is his weight?", 113.4),
        ("A rock is dropped from 2 m on Mars. How long does it fall?", 1.038),
        (
            "what is the mass of an object whose weight on the moon is 162 N? "
            "(g moon = 1.62 m/s^2)",
            100.0,
        ),
    ],
)
def test_the_moon_and_mars_keep_their_school_g(text: str, value: float) -> None:
    assert _verified(text)[1] == pytest.approx(value, rel=0.01)


@pytest.mark.parametrize(
    ("lower", "ours", "another"),
    [
        ("on the moon", True, False),
        ("(g moon = 1.62", True, False),
        ("earth's moon", True, False),
        ("on europa, a moon of jupiter", False, True),
        ("ganymede, the largest moon", False, True),
        ("on mars's moon deimos", False, True),
        ("mars has two moons", False, True),
    ],
)
def test_our_moon_is_told_from_another(lower: str, ours: bool, another: bool) -> None:
    assert (names_our_moon(lower), names_another_moon(lower)) == (ours, another)


@pytest.mark.parametrize(
    "text",
    [
        # The combination stated as a whole, a part asked: P₁ + P₂ gave 7 D, 8 D, 14 µF, 14 Ω.
        "Two lenses in contact: the combination has a power of 2 D. One lens has a power of "
        "5 D. What is the power of the other?",
        "A 3 D lens is placed in contact with a second lens. The pair has a power of 5 D. What "
        "is the power of the second lens?",
        "A 4 μF capacitor is connected in parallel with another and together they have a "
        "capacitance of 10 μF. What is the other capacitance?",
        "Two springs in series behave like one spring of 120 N/m. One is 200 N/m. What is the "
        "spring constant of the other?",
        "Two resistors in series have a total resistance of 10 Ω. One is 4 Ω. What is the other?",
        "Two resistors in parallel have a combined resistance of 2 Ω. One is 3 Ω. What is the "
        "other?",
        "A 4 Ω resistor in series with another gives 10 Ω altogether. What is the other "
        "resistance?",
    ],
)
def test_a_part_asked_is_never_the_parts_added(text: str) -> None:
    assert asks_for_a_part(text)
    assert _declined(text)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        (
            "Two lenses in contact together have a power of 5 D. One lens has a power of 3 D. "
            "What is the power of the other?",
            2.0,
        ),
        (
            "Two springs in parallel together have a spring constant of 500 N/m. One has "
            "k = 300 N/m. What is the spring constant of the other?",
            200.0,
        ),
        ("A 3 Ω and a 6 Ω resistor are connected in parallel. What is the total resistance?", 2.0),
        ("A 3 Ω and a 6 Ω resistor are connected in series. What is the total resistance?", 9.0),
        (
            "A lens of power +4 D is placed in contact with a lens of power -2.5 D. What is the "
            "power of the combination?",
            1.5,
        ),
    ],
)
def test_a_whole_or_a_part_by_its_law(text: str, value: float) -> None:
    assert _verified(text)[1] == pytest.approx(value, rel=0.01)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        # √(2gh) left the spin out: 6.26, 4.43, 7.67, 7.67 m/s.
        (
            "A solid sphere rolls without slipping down a 2 m high incline from rest. What is "
            "its speed at the bottom?",
            (10 * 9.81 * 2 / 7) ** 0.5,
        ),
        (
            "A hollow sphere rolls without slipping down a slope 1 m high from rest. What is its "
            "speed at the bottom?",
            (6 * 9.81 / 5) ** 0.5,
        ),
        (
            "A solid cylinder rolls without slipping down a hill 3 m high, starting from rest. "
            "What is its speed at the bottom?",
            (4 * 9.81 * 3 / 3) ** 0.5,
        ),
        (
            "A hoop rolls without slipping down a 3 m high ramp from rest. How fast is it "
            "moving at the bottom?",
            (9.81 * 3) ** 0.5,
        ),
        # The translational energy asked is ½mv², spin or not (the total said 14 J).
        (
            "A solid sphere of mass 5 kg rolls at 2 m/s. What is its translational kinetic energy?",
            10.0,
        ),
        # A car rolling along is moved, not spun.
        (
            "A 1000 kg car rolling along a road has 200 kJ of kinetic energy. What is its speed?",
            20.0,
        ),
    ],
)
def test_a_rolling_body_keeps_its_spin(text: str, value: float) -> None:
    assert _verified(text)[1] == pytest.approx(value, rel=0.01)


@pytest.mark.parametrize(
    ("text", "spins"),
    [
        ("A solid sphere rolls down a slope", True),
        ("A ball rolls down a ramp 1.5 m high", True),
        ("A 1000 kg car rolls along a road at 20 m/s", False),
        ("A roller coaster drops 20 m", False),
    ],
)
def test_a_body_that_spins_as_it_rolls(text: str, spins: bool) -> None:
    assert rolling_body(text) is spins


@pytest.mark.parametrize(
    "text",
    [
        # A shape the ball does not say: solid or hollow.
        "A ball rolls down a ramp 1.5 m high from rest. What is its speed at the bottom?",
        # The secondary's voltage unlabelled, the primary's asked: 0.6 V and 3.75 V for 240 V.
        "A transformer with 1000 primary turns and 50 secondary turns produces 12 V. What "
        "voltage is supplied?",
        "A 12 V lamp works normally from a transformer with 1000 turns on the primary and 50 "
        "on the secondary. What is the primary voltage?",
        "The secondary coil of a transformer has 600 turns and gives 30 V. The primary has "
        "4800 turns. What is the primary voltage?",
        # A speed in the frame the sum is in, asked in the mover's: 0.994c for 0.625c.
        "Seen from Earth, a probe moves at 0.95c. The ship that launched it forward moves at "
        "0.8c. Find the probe's speed in the ship's frame.",
        "Relative to Earth, a probe moves at 0.95c. It was fired forward from a ship moving at "
        "0.8c relative to Earth. What is the probe's speed relative to the ship?",
        "In the Earth frame a probe travels at 0.95c after being fired forward by a ship "
        "moving at 0.8c. What is the probe's speed relative to the ship?",
        # Light that starts in the glass: Snell from air gave 19.5° for 48.6°.
        "Light travelling in glass (n = 1.5) reaches the glass-air surface at 30°. What is the "
        "angle of refraction in air?",
        "A ray inside glass of refractive index 1.5 hits the surface at 30° to the normal. What "
        "is the angle of refraction in air?",
        # An angle said from neither line: it may be to the surface.
        "A ray of light strikes a glass block at 30° and is refracted at 20°. What is the "
        "refractive index of the glass?",
        # The body's own acceleration is no g: 420 N, 4 N, 40 N, 6 N.
        "A skydiver of mass 70 kg falls with an acceleration of 6 m/s². What is her weight?",
        "A 0.5 kg ball falls with an acceleration of 8 m/s² because of air resistance. What is "
        "its weight?",
        "A 20 kg box is accelerated across a field at 2 m/s². What is its weight?",
        "A 2 kg charged mass in an electric field accelerates at 3 m/s². What is its weight?",
        # λ = c/f is the vacuum's: 600 nm in glass for 400 nm.
        "Light has a frequency of 5 × 10¹⁴ Hz in glass of refractive index 1.5. What is its "
        "wavelength in the glass?",
    ],
)
def test_a_reading_the_structure_does_not_hold_declines(text: str) -> None:
    assert _declined(text)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        (
            "A transformer has 400 turns on the primary and 100 on the secondary. The secondary "
            "voltage is 12 V. What is the voltage across the primary?",
            48.0,
        ),
        (
            "A step-up transformer has 200 primary turns and 1000 secondary turns. The primary "
            "voltage is 12 V. What is the secondary voltage?",
            60.0,
        ),
        (
            "Spaceship A moves at 0.5c relative to Earth and fires a missile forward at 0.5c "
            "relative to the ship. What is the missile's speed relative to Earth?",
            0.8,
        ),
        (
            "A ship moving at 0.7c relative to a station fires a probe forward at 0.5c relative "
            "to the ship. What is the speed of the probe relative to the station?",
            1.2 / 1.35,
        ),
        # An angle to the surface is 90° less from the normal: 40° to it gave 1.26 for 1.50.
        (
            "A ray of light in air strikes a glass block at 40° to the surface. The refracted "
            "ray makes 30.7° with the normal. What is the refractive index of the glass?",
            1.50,
        ),
        (
            "A ray of light strikes a glass surface at 30° to the surface. The refracted ray "
            "makes 20° with the normal. What is the refractive index of the glass?",
            2.53,
        ),
        (
            "A light ray is incident at 45° on a glass slab and is refracted at 28°. What is the "
            "refractive index of the glass?",
            1.506,
        ),
        (
            "A ray in air enters glass (n = 1.5) at 30° to the normal. What is the angle of "
            "refraction?",
            19.47,
        ),
        ("A rock has a weight of 7.4 N on Mars where g = 3.7 m/s². What is its mass?", 2.0),
    ],
)
def test_the_structure_read_still_answers(text: str, value: float) -> None:
    assert _verified(text)[1] == pytest.approx(value, rel=0.01)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        # Over-declines on the first branch, read right again.
        ("A 2 kg box on a floor with μ = 0.3 moves at 3 m/s. What is its kinetic energy?", 9.0),
        (
            "A net force of 400 N acts on a cart on a ramp, giving it an acceleration of 2 m/s². "
            "What is its mass?",
            200.0,
        ),
        (
            "A 20 N net force acts on a block attached to a spring and it accelerates at "
            "4 m/s². What is its mass?",
            5.0,
        ),
        (
            "A 40 N force accelerates a mass at 10 m/s² on a frictionless floor, μ = 0. What is "
            "its mass?",
            4.0,
        ),
        (
            "What is the wavelength in glass (n = 1.5) of light whose wavelength in air is 600 nm?",
            400.0,
        ),
        (
            "A ball is thrown upward at 15 m/s and lands 3 s later. What is its acceleration at "
            "the top?",
            -9.81,
        ),
        # "Lift" the verb is no lift a body rides in: it still weighs mg.
        ("A crane lifts a 200 kg crate. What is its weight?", 1962.0),
        ("The workers lift a 50 kg box. What is its weight?", 490.5),
        ("A 15 kg bag is lifted onto a shelf. What is its weight?", 147.15),
    ],
)
def test_what_the_first_fixes_declined_answers_again(text: str, value: float) -> None:
    assert _verified(text)[1] == pytest.approx(value, rel=0.01)


@pytest.mark.parametrize(
    ("lower", "shares"),
    [
        ("a 60 n force pushes a box with μ = 0.2 at 1 m/s²", True),
        ("a 60 n force pushes a box on a ramp at 1 m/s²", True),
        ("a net force of 60 n acts on a box on a ramp at 1 m/s²", False),
        ("a 60 n force pushes a box on a frictionless floor, μ = 0", False),
    ],
)
def test_a_force_is_the_net_one_unless_others_share_it(lower: str, shares: bool) -> None:
    assert others_share_the_force(lower) is shares


@pytest.mark.parametrize(
    ("text", "adds"),
    [
        (
            "A ship at 0.6c relative to Earth fires a probe at 0.8c relative to the ship. Speed "
            "relative to Earth?",
            True,
        ),
        (
            "A ship at 0.6c fires a probe forward at 0.8c relative to the ship. What is its speed?",
            True,
        ),
        (
            "Relative to Earth a probe moves at 0.95c; the ship moves at 0.8c. Speed relative to "
            "the ship?",
            False,
        ),
        (
            "Two ships approach each other at 0.6c relative to Earth. Speed of one relative to "
            "the other?",
            False,
        ),
    ],
)
def test_velocity_addition_needs_a_speed_relative_to_a_mover(text: str, adds: bool) -> None:
    assert adds_speeds_across_frames(text) is adds


@pytest.mark.parametrize(
    ("operation", "parts"),
    [
        ("lens_power_sum", {"p1", "p2"}),
        ("capacitors_series", {"c1", "c2"}),
        ("perpendicular_velocity_sum", {"v1", "v2"}),
        # Speeds that give a force, masses that give a speed: no parts of a whole.
        ("rebound_average_force", set()),
        ("push_off_speed", set()),
    ],
)
def test_the_parts_a_law_adds_up(operation: str, parts: set[str]) -> None:
    assert same_part(CATALOG[operation]) == parts


def test_a_push_off_asked_of_the_second_body_still_answers() -> None:
    text = (
        "An ice skater of 60 kg pushes off another skater of 40 kg. If the first moves away "
        "at 2 m/s, how fast does the second move?"
    )
    assert _verified(text) == ("push_off_speed", pytest.approx(3.0))


@pytest.mark.parametrize(
    ("lower", "rides"),
    [
        ("a 60 kg person stands on a scale in a lift accelerating upward at 2 m/s²", True),
        ("a 1000 kg lift accelerates upward at 2 m/s²", True),
        ("a 60 kg person stands in a stationary lift", True),
        ("in the lift, a man stands on a scale", True),
        ("an elevator accelerates downward at 2 m/s²", True),
        ("a crane lifts a 200 kg crate", False),
        ("the workers lift a 50 kg box", False),
        ("a pump lifts 500 litres of water", False),
        ("a crane that lifts a crate", False),
        ("a 15 kg bag is lifted onto a shelf", False),
    ],
)
def test_a_lift_is_the_car_a_body_rides_in_not_the_verb(lower: str, rides: bool) -> None:
    assert in_a_lift(lower) is rides
