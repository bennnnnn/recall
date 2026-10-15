"""Laws and readers the September investigation found left to the model.

Each table holds questions the solver now verifies, with the answer worked by
hand (g = 9.81 m/s²), and the near misses it must still decline: a reading
that is not complete is never verified.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.physics.binding import crosswise
from app.modules.physics.binding_values import light_enters_from_air
from app.modules.physics.extract import needs_physics
from app.modules.physics.numbers import normalize_physics_numbers, normalize_physics_units
from app.services.subject_solving import detect_subject
from app.tests.modules.physics.support import answer_number

_SETTINGS = Settings(math_tools_enabled=True)


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


def _operation(text: str) -> str | None:
    intent = extract_physics_intent(text)
    return None if intent is None else intent.physics_op


def _assert_answer(text: str, operation: str, value: float, unit: str) -> None:
    assert _operation(text) == operation, text
    answer = _answer(text)
    assert answer is not None, text
    assert answer_number(answer) == pytest.approx(value, rel=5e-3), answer
    assert unit in answer, answer


# --- optics -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        # The angle to the surface is 90° less than the angle of incidence.
        (
            "Light strikes a glass block (n = 1.5) making an angle of 50 degrees with the "
            "surface. Find the angle of refraction.",
            25.37,
        ),
        (
            "a ray of light hits the surface of water (n=1.33) at 30° to the surface. "
            "what's the angle of refraction?",
            40.63,
        ),
        ("Light enters glass (n = 1.5) at 30°. what is the angle of refraction?", 19.47),
    ],
)
def test_snell_refraction_angle_reads_light_from_air(text: str, value: float) -> None:
    _assert_answer(text, "snell_refraction_angle", value, "°")


@pytest.mark.parametrize(
    "text",
    [
        # Light inside the glass, or coming from it, is not from air.
        "Light inside a glass block (n = 1.5) hits the surface at 30°. "
        "What is the angle of refraction?",
        "A ray leaves water (n = 1.33) at 30°. What is the angle of refraction?",
        "Light travelling in diamond hits glass (n = 1.5) at 30°. Find the angle of refraction.",
    ],
)
def test_snell_refraction_angle_declines_light_that_starts_in_a_medium(text: str) -> None:
    assert _answer(text) is None


@pytest.mark.parametrize(
    ("lower", "from_air"),
    [
        ("light strikes a glass block (n = 1.5)", True),
        ("a ray of light hits the surface of water (n=1.33)", True),
        ("light inside a glass block hits the surface", False),
        ("light from the glass enters water", False),
        ("a ray of light hits the surface from the air", True),
        ("light passes between two blocks", False),
    ],
)
def test_light_enters_from_air_reads_where_the_ray_starts(lower: str, from_air: bool) -> None:
    assert light_enters_from_air(lower) is from_air


@pytest.mark.parametrize(
    ("text", "operation", "value", "unit"),
    [
        (
            "what is the critical angle for light going from glass n=1.5 into water n=1.33",
            "critical_angle_between",
            62.46,
            "°",
        ),
        (
            "What is the critical angle for light going from glass (n = 1.5) into water "
            "(n = 1.33)?",
            "critical_angle_between",
            62.46,
            "°",
        ),
        (
            "What is the wavelength of 650 nm red light inside glass of refractive index 1.5?",
            "wavelength_in_medium",
            433.3,
            "nm",
        ),
        (
            "Light of wavelength 650 nm enters glass with refractive index 1.5. What is its "
            "wavelength in the glass?",
            "wavelength_in_medium",
            433.3,
            "nm",
        ),
        (
            "In a double slit experiment the slits are 0.2 mm apart and the screen is 1.5 m "
            "away. With 600 nm light, what's the fringe spacing?",
            "double_slit_fringe_spacing",
            0.0045,
            "m",
        ),
        (
            "A diffraction grating has 500 lines per mm. Light of 550 nm. At what angle is the "
            "first-order maximum?",
            "grating_angle",
            15.96,
            "°",
        ),
        (
            "a magnifying glass has focal length 5 cm. what's its power in diopters?",
            "lens_power",
            20.0,
            "D",
        ),
        (
            "A 4 cm tall object is 15 cm in front of a converging lens of focal length 10 cm. "
            "how tall is the image?",
            "image_height",
            8.0,
            "cm (inverted)",
        ),
        (
            "a concave mirror has a radius of curvature of 40 cm. an object is placed 30 cm "
            "away. where is the image?",
            "mirror_image_from_radius",
            60.0,
            "cm",
        ),
        (
            "an object is 8 cm from a converging lens with focal length 12 cm. find the image "
            "distance",
            "image_distance",
            24.0,
            "cm (virtual, on the object's side of the lens)",
        ),
        (
            "what is the image distance for a lens of focal length 20 cm and object at 10 cm",
            "image_distance",
            20.0,
            "virtual",
        ),
    ],
)
def test_optics_laws_answer_the_investigation_questions(
    text: str, operation: str, value: float, unit: str
) -> None:
    _assert_answer(text, operation, value, unit)


@pytest.mark.parametrize(
    "text",
    [
        # Into the denser medium there is no total internal reflection.
        "what is the critical angle for light going from water n=1.33 into glass n=1.5",
        # Inside F a mirror's image is virtual, behind it.
        "a concave mirror has a radius of curvature of 40 cm. an object is placed 10 cm "
        "away. where is the image?",
        # Inside F the image is virtual and upright: its height's sign is a convention.
        "A 4 cm tall object is 5 cm in front of a converging lens of focal length 10 cm. "
        "how tall is the image?",
        # A diverging lens is outside these laws.
        "A 4 cm tall object is 15 cm in front of a diverging lens of focal length 10 cm. "
        "how tall is the image?",
    ],
)
def test_optics_laws_decline_what_they_cannot_read_whole(text: str) -> None:
    assert _answer(text) is None


# --- forces and motion ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        (
            "A 25 kg crate is pulled across a floor by a rope at 30° above the horizontal "
            "with a 150 N force. μk = 0.2. find the accelaration",
            3.834,
        ),
        # Pushed down at the angle: the floor presses back harder.
        (
            "A 25 kg crate is pushed across a floor with a 150 N force at 30° below the "
            "horizontal. μk = 0.2. find the acceleration",
            2.634,
        ),
    ],
)
def test_angled_pull_friction_acceleration_resolves_the_force(text: str, value: float) -> None:
    _assert_answer(text, "angled_pull_friction_acceleration", value, "m/s²")


@pytest.mark.parametrize(
    "text",
    [
        # Steep enough to lift the crate: no floor to press on.
        "A 2 kg crate is pulled by a rope at 60° above the horizontal with a 150 N force. "
        "μk = 0.2. find the acceleration",
        # A slope's angle is not the rope's.
        "A 25 kg crate is pulled up a 30° incline by a rope at 20° above the horizontal "
        "with a 150 N force. μk = 0.2. find the acceleration",
    ],
)
def test_angled_pull_friction_acceleration_declines_outside_its_shape(text: str) -> None:
    assert _operation(text) != "angled_pull_friction_acceleration" or _answer(text) is None


@pytest.mark.parametrize(
    ("written", "read"),
    [
        ("accelaration?", "acceleration?"),
        ("it acclerates at 2 m/s^2", "it accelerates at 2 m/s^2"),
        ("whats the total distance?", "what's the total distance?"),
        ("Whats the tension", "What's the tension"),
        ("final velocty", "final velocity"),
    ],
)
def test_normalize_physics_units_reads_a_misspelt_ask(written: str, read: str) -> None:
    assert normalize_physics_units(written) == read


@pytest.mark.parametrize(
    ("text", "operation", "value", "unit"),
    [
        (
            "a train starts from rest and acclerates at 0.8 m/s^2 for 25 s, then travels at "
            "constant speed for 1 min. whats the total distance?",
            "two_stage_distance",
            1450.0,
            "m",
        ),
        (
            "a sprinter reaches her top speed of 11 m/s in 2.2 s starting from rest and "
            "holds it to the finish. how long does she take to run 100 m?",
            "two_stage_time",
            10.19,
            "s",
        ),
        (
            "A car accelerates from rest at 2 m/s^2 for 10 s, then brakes at 4 m/s^2 to a "
            "stop. total distance?",
            "two_stage_distance",
            150.0,
            "m",
        ),
        (
            "A bus starts from rest and accelerates to 12 m/s in 6 s, then brakes to a stop "
            "in 4 s. what is the total distance?",
            "two_stage_distance",
            60.0,
            "m",
        ),
        (
            "A car accelerates from rest at 2 m/s^2 for 10 s, then brakes at 4 m/s^2 to a "
            "stop. what is the total time?",
            "two_stage_time",
            15.0,
            "s",
        ),
    ],
)
def test_two_stage_motion_answers_the_whole_trip(
    text: str, operation: str, value: float, unit: str
) -> None:
    _assert_answer(text, operation, value, unit)


@pytest.mark.parametrize(
    "text",
    [
        # One stage asked: not the whole trip.
        "A car accelerates from rest at 2 m/s^2 for 10 s, then brakes at 4 m/s^2 to a stop. "
        "how far does it travel while braking?",
        # A start speed: not from rest.
        "A car moving at 5 m/s accelerates at 2 m/s^2 for 10 s, then brakes at 4 m/s^2 to a "
        "stop. total distance?",
        # The 10 m ends before the top speed is reached.
        "a sprinter reaches her top speed of 11 m/s in 2.2 s starting from rest and holds it "
        "to the finish. how long does she take to run 10 m?",
        # A held speed with no time or distance has no end.
        "A train starts from rest, accelerates at 1 m/s^2 for 20 s, then travels at constant "
        "speed. total distance?",
        # A second stage this reading does not know.
        "A lift starts from rest and accelerates at 1 m/s^2 for 3 s, then goes up a 2 m shaft. "
        "total distance?",
    ],
)
def test_two_stage_motion_declines_a_partial_reading(text: str) -> None:
    assert _answer(text) is None


def test_stopping_distance_reads_a_braking_rate() -> None:
    _assert_answer(
        "Driver going 108 km/h sees a hazard, reaction time 0.8 s, then brakes at 6 m/s^2. "
        "total stopping distance?",
        "stopping_distance",
        99.0,
        "m",
    )


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        (
            "a boat heads straight across a river at 4 m/s while the current flows at 3 m/s. "
            "what is the boat's resultant speed relative to the bank?",
            5.0,
            "m/s",
        ),
        (
            "a plane flies due north at 250 km/h and a 50 km/h wind blows from west to east. "
            "what's its ground speed?",
            255.0,
            "km/h",
        ),
    ],
)
def test_perpendicular_velocity_sum_adds_at_right_angles(
    text: str, value: float, unit: str
) -> None:
    _assert_answer(text, "perpendicular_velocity_sum", value, unit)


@pytest.mark.parametrize(
    "text",
    [
        # Aimed upstream to land opposite: the other triangle.
        "a boat wants to go straight across a river at 4 m/s while the current flows at "
        "3 m/s. what is the boat's resultant speed relative to the bank?",
        "a boat aims upstream so it crosses straight across a river at 4 m/s in a 3 m/s "
        "current. what is its resultant speed?",
        # A wind along the heading is not a right angle.
        "a plane flies due north at 250 km/h into a 50 km/h wind from the north. what's its "
        "ground speed?",
        # Between the axes.
        "a plane flies north-east at 250 km/h and a 50 km/h wind blows from west to east. "
        "what's its ground speed?",
    ],
)
def test_perpendicular_velocity_sum_declines_other_geometry(text: str) -> None:
    assert _operation(text) != "perpendicular_velocity_sum"


@pytest.mark.parametrize(
    ("lower", "crossing"),
    [
        ("flies due north and a wind blows from west to east", True),
        ("i walk 3 km east then 4 km north", True),
        ("flies north into a wind from the north", False),
        ("flies north-east with a wind from the west", False),
        ("heads north at a bearing of 30 degrees east", False),
    ],
)
def test_crosswise_reads_one_direction_on_each_axis(lower: str, crossing: bool) -> None:
    assert crosswise(lower) is crossing


def test_meeting_time_reads_when_do_they_meet() -> None:
    _assert_answer(
        "Two cars 300 m apart drive toward each other at 20 m/s and 10 m/s. when do they meet?",
        "meeting_time",
        10.0,
        "s",
    )


# --- momentum -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "operation", "value", "unit"),
    [
        # The asked body's mass names it; it is not a third mass.
        (
            "a 2 kg ball moving at 6 m/s hits a stationary 4 kg ball head-on in a perfectly "
            "elastic collision. what is the velocity of the 4 kg ball after?",
            "final_velocity",
            -2.0,
            "m/s and 4 m/s",
        ),
        (
            "A 1500 kg car going 20 m/s rear-ends a 1000 kg car going 10 m/s in the same "
            "direction and they lock bumpers. what's their speed just after?",
            "final_velocity",
            16.0,
            "m/s",
        ),
        (
            "a 10 g bullet traveling 400 m/s embeds in a 2 kg wooden block at rest on ice. "
            "how fast does the block move after?",
            "final_velocity",
            1.99,
            "m/s",
        ),
        # Directions: east is positive, so the west-moving puck's speed is negative.
        (
            "A 0.5 kg puck moving east at 4 m/s collides with a 0.3 kg puck moving west at "
            "2 m/s. they stick together. final velocity?",
            "final_velocity",
            1.75,
            "m/s",
        ),
        (
            "A 3 kg cart moving at 4 m/s collides and sticks to a 1 kg cart at rest. how much "
            "kinetic energy is lost?",
            "collision_energy_lost",
            6.0,
            "J",
        ),
        (
            "A 6 kg shell at rest explodes into two pieces, 2 kg and 4 kg. The 2 kg piece "
            "flies off at 30 m/s. how fast does the 4 kg piece move?",
            "explosion_speed",
            15.0,
            "m/s",
        ),
        (
            "A 6 kg bomb at rest explodes into a 2 kg piece and a 4 kg piece. If the 2 kg "
            "piece moves at 30 m/s, how fast does the 4 kg piece move?",
            "explosion_speed",
            15.0,
            "m/s",
        ),
        (
            "A tennis racket exerts an average force of 240 N on a 58 g ball for 5 ms. "
            "what's the change in the ball's speed?",
            "speed_change_from_force",
            20.69,
            "m/s",
        ),
        (
            "A 0.2 kg ball hits a wall at 15 m/s and bounces back at 10 m/s. contact time "
            "0.05 s. average force on the ball?",
            "rebound_average_force",
            100.0,
            "N",
        ),
        (
            "an astronaut of mass 90 kg throws a 3 kg wrench at 6 m/s. what's his recoil speed",
            "recoil_speed",
            0.2,
            "m/s",
        ),
    ],
)
def test_momentum_laws_answer_the_investigation_questions(
    text: str, operation: str, value: float, unit: str
) -> None:
    _assert_answer(text, operation, value, unit)


@pytest.mark.parametrize(
    "text",
    [
        # One body's direction and the other's unsaid.
        "A 0.5 kg puck moving east at 4 m/s collides with a 0.3 kg puck moving at 2 m/s. "
        "they stick together. final velocity?",
        # East and north: two dimensions.
        "A 0.5 kg puck moving east at 4 m/s collides with a 0.3 kg puck moving north at "
        "2 m/s. they stick together. final velocity?",
        # An elastic collision loses no kinetic energy to ask about.
        "A 3 kg cart moving at 4 m/s collides elastically with a 1 kg cart at rest. how much "
        "kinetic energy is lost?",
        # Speeds listed apart from their masses: which is whose is not read.
        "Two carts of 2 kg and 3 kg move toward each other at 3 m/s and 2 m/s and stick "
        "together. what is their final velocity?",
        # The asked mass is no body's.
        "a 2 kg ball moving at 6 m/s hits a stationary 4 kg ball in a perfectly elastic "
        "collision. what is the velocity of the 3 kg ball after?",
        # The pieces do not make up the shell.
        "A 6 kg shell at rest explodes into two pieces, 2 kg and 3 kg. The 2 kg piece flies "
        "off at 30 m/s. how fast does the 3 kg piece move?",
        # Which piece moves is not said.
        "A 6 kg shell at rest explodes into two pieces, 2 kg and 4 kg. One piece flies off "
        "at 30 m/s. how fast does the other move?",
    ],
)
def test_momentum_laws_decline_a_partial_reading(text: str) -> None:
    assert _answer(text) is None


# --- fluids ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "operation", "value", "unit"),
    [
        (
            "What's the absolute pressure 50 m deep in seawater (density 1025 kg/m^3)? "
            "include atmospheric pressure",
            "absolute_pressure_at_depth",
            6.04e5,
            "Pa",
        ),
        (
            "Water flows at 2 m/s in a pipe of diameter 4 cm, which narrows to 2 cm "
            "diameter. what's the speed in the narrow part?",
            "continuity_velocity",
            8.0,
            "m/s",
        ),
        (
            "Water flows at 8 m/s in a 2 cm diameter pipe that widens to 4 cm. what is the "
            "speed in the wider section?",
            "continuity_velocity",
            2.0,
            "m/s",
        ),
        (
            "water in a horizontal pipe speeds up from 2 m/s to 8 m/s. what's the pressure drop?",
            "bernoulli_pressure_drop",
            30000.0,
            "Pa",
        ),
        (
            "Water leaks out of a small hole 3 m below the water surface in a big tank. how "
            "fast does it come out?",
            "torricelli_speed",
            7.672,
            "m/s",
        ),
        (
            "A 3 kg object weighs only 18 N when fully submerged in water. what is its volume?",
            "volume_from_apparent_weight",
            0.001165,
            "m³",
        ),
        (
            "In a hydraulic press the small piston has a diameter of 2 cm and the big one "
            "20 cm. If you push with 50 N on the small piston, what force is produced on the "
            "large piston?",
            "hydraulic_force",
            5000.0,
            "N",
        ),
    ],
)
def test_fluid_laws_answer_the_investigation_questions(
    text: str, operation: str, value: float, unit: str
) -> None:
    _assert_answer(text, operation, value, unit)


@pytest.mark.parametrize(
    "text",
    [
        # The speed is the narrow part's: not the first section's.
        "A pipe of diameter 4 cm narrows to 2 cm. In the narrow part the water moves at "
        "8 m/s. Find the speed in the wide part.",
        "A pipe of diameter 4 cm narrows to 2 cm. In the narrow part the water moves at "
        "8 m/s. Find the speed in the narrow part.",
        # Slowing down raises the pressure.
        "water in a horizontal pipe slows from 8 m/s to 2 m/s. what's the pressure drop?",
        # A height change adds a term the horizontal form leaves out.
        "water in a pipe speeds up from 2 m/s to 8 m/s as it rises 3 m. what's the pressure drop?",
        # Heavier under water than in air is no upthrust.
        "A 3 kg object weighs 40 N when fully submerged in water. what is its volume?",
    ],
)
def test_fluid_laws_decline_a_partial_reading(text: str) -> None:
    assert _answer(text) is None


# --- oscillations, waves, modern -------------------------------------------------


@pytest.mark.parametrize(
    ("text", "operation", "value", "unit"),
    [
        (
            "A 250 g mass hangs on a spring with k = 40 N/m. What is the period of oscillation?",
            "shm_period",
            0.4967,
            "s",
        ),
        ("frequency of a 1.2 m long simple pendulum?", "pendulum_frequency", 0.4551, "Hz"),
        (
            "What is the frequency of a simple pendulum of length 1.2 m?",
            "pendulum_frequency",
            0.4551,
            "Hz",
        ),
        (
            "A mass on a spring oscillates with a period of 0.8 s. if k = 50 N/m, what is the "
            "mass?",
            "spring_mass_from_period",
            0.8106,
            "kg",
        ),
        (
            "What is the sound intensity level of a sound with intensity 3.2 x 10^-5 W/m^2?",
            "sound_level",
            75.05,
            "dB",
        ),
        (
            "What is the sound level in dB for an intensity of 3.2 × 10^-5 W/m²?",
            "sound_level",
            75.05,
            "dB",
        ),
        (
            "how long until only 1/16 of a carbon-14 sample remains? half life 5730 years",
            "decay_time_from_fraction",
            22920.0,
            "years",
        ),
        (
            "Carbon-14 has a half-life of 5730 years. How long until 1/16 of a sample remains?",
            "decay_time_from_fraction",
            22920.0,
            "years",
        ),
        (
            "a radioactive source has an activity of 800 Bq. after 12 hours it's 200 Bq. "
            "what's the half-life?",
            "half_life_from_activities",
            6.0,
            "h",
        ),
        (
            "what percentage of a radioactive sample remains after 3 half-lives?",
            "percent_after_half_lives",
            12.5,
            "%",
        ),
        (
            "A muon travels at 0.98c. if its lifetime at rest is 2.2 µs, what's its lifetime "
            "measured in the lab?",
            "time_dilation",
            1.106e-5,
            "s",
        ),
    ],
)
def test_oscillation_wave_and_modern_laws_answer(
    text: str, operation: str, value: float, unit: str
) -> None:
    _assert_answer(text, operation, value, unit)


@pytest.mark.parametrize(
    "text",
    [
        # A third is no exact decimal: the fraction stays unread.
        "how long until only 1/3 of a carbon-14 sample remains? half life 5730 years",
        # Activity that rises is no decay.
        "a radioactive source has an activity of 200 Bq. after 12 hours it's 800 Bq. "
        "what's the half-life?",
    ],
)
def test_decay_laws_decline_what_is_not_a_decay(text: str) -> None:
    assert _answer(text) is None


@pytest.mark.parametrize(
    ("text", "read"),
    [
        ("only 1/16 of a sample", "only 0.0625 of a sample"),
        ("until 3/4 of the way", "until 0.75 of the way"),
        # Not "of" something, or not an exact decimal: left as written.
        ("only 1/3 of a sample", None),
        ("on 1/16 at noon", None),
    ],
)
def test_normalize_physics_numbers_reads_an_exact_fraction_of(text: str, read: str | None) -> None:
    assert normalize_physics_numbers(text) == read


# --- routing ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "a sprinter reaches her top speed of 11 m/s in 2.2 s starting from rest and holds it "
        "to the finish. how long does she take to run 100 m?",
        "A 25 kg crate is pulled across a floor by a rope at 30° above the horizontal with a "
        "150 N force. μk = 0.2. find the accelaration",
        "Light strikes a glass block (n = 1.5) making an angle of 50 degrees with the surface. "
        "Find the angle of refraction.",
        "a boat heads straight across a river at 4 m/s while the current flows at 3 m/s. what "
        "is the boat's resultant speed relative to the bank?",
    ],
)
def test_detect_subject_gives_the_investigation_gaps_to_physics(text: str) -> None:
    assert needs_physics(text)
    assert detect_subject(text) == "physics"


@pytest.mark.parametrize(
    "text",
    [
        "how fast is my wifi",
        "I'm recovering from rest days then going back to the gym",
        "the road narrows to one lane after the bridge, how long is the delay?",
        "my boat heads straight across the bay tomorrow, what should I pack?",
        "whats the time in Tokyo",
        "the river current is strong today, is it safe to swim?",
    ],
)
def test_needs_physics_leaves_everyday_lookalikes(text: str) -> None:
    assert not needs_physics(text)
