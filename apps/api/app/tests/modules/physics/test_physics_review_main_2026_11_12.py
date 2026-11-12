"""Wrong verified answers a review of main found with 386 hand-worked textbook questions
(2026-11-12), each class fixed whole: a law the question's situation rules out, a value read
as the wrong one of a law's quantities, or an ask read as another quantity.

Each wrong answer is now right or declined (left to the model, unverified), and its
look-alikes, the right reading of the same law, still verify. g = 9.81 m/s².
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.ask import asked_dimensions
from app.modules.physics.binding_values import light_starts_inside
from app.modules.physics.prompt import solve_physics_request
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
    ("text", "operation", "value"),
    [
        # A lift's floor pushes m(g ± a): its reading asks m = N/(g ± a), never F/a.
        (
            "In an elevator accelerating upward at 2 m/s², the apparent weight of a passenger "
            "is 708.6 N. What is the passenger's mass?",
            "lift_normal_force",
            60.0,
        ),
        (
            "In a lift with a downward acceleration of 2 m/s², the normal force on a passenger "
            "is 468.6 N. What is the passenger's mass?",
            "lift_normal_force",
            60.0,
        ),
        (
            "A 60 kg person in a lift with a downward acceleration of 2 m/s². Find the normal "
            "force.",
            "lift_normal_force",
            468.6,
        ),
        (
            "A 60 kg person stands on a scale in a lift accelerating upward at 2 m/s². What "
            "does the scale read?",
            "lift_normal_force",
            708.6,
        ),
        # A level tow rope is the towed car's net force; "frictionless" says none acts.
        (
            "A truck accelerating at 2 m/s² tows a car with a tension of 3000 N in the tow "
            "rope. What is the car's mass?",
            "mass_from_force",
            1500.0,
        ),
        (
            "A 400 N force accelerates a trolley at 2 m/s² on a frictionless surface. What is "
            "its mass?",
            "mass_from_force",
            200.0,
        ),
        # g named as gravity, however it is written.
        (
            "what is the mass of an object whose weight on the moon is 162 N? "
            "(g moon = 1.62 m/s^2)",
            "mass_from_weight",
            100.0,
        ),
        (
            "On a planet where objects fall at 3.7 m/s², a rock weighs 7.4 N. What is its mass?",
            "mass_from_weight",
            2.0,
        ),
    ],
)
def test_a_force_in_a_lift_or_beside_gravity_is_read_by_its_law(
    text: str, operation: str, value: float
) -> None:
    assert _verified(text) == (operation, pytest.approx(value, rel=0.01))


@pytest.mark.parametrize(
    "text",
    [
        # m = F/a read the scale as the net force: 354.3 kg and 234.3 kg for 60 kg.
        "A lift accelerates upward at 2 m/s². A person standing on a scale in it reads 708.6 N. "
        "What is the person's mass?",
        "A lift moving upward decelerates at 2 m/s². A person standing on a scale in it reads "
        "468.6 N. What is the person's mass?",
        "A crate is lifted by a rope with a tension of 708.6 N, accelerating upward at 2 m/s². "
        "What is its mass?",
        # Up was the lift law's default: 708.6 N for 468.6 N.
        "A 60 kg person stands on a scale in a lift accelerating at 2 m/s² downward. What does "
        "the scale read?",
        "A 60 kg person is in a lift that is descending with an acceleration of 2 m/s². What is "
        "the normal force on the person?",
        # W = mg with the lift's 2 m/s² as g: 120 N.
        "A 60 kg person rides in an elevator moving downward that decelerates at 2 m/s². What "
        "is the apparent weight?",
        # The car's own acceleration as g: 4905 kg for 1000 kg.
        "A car accelerates at 2 m/s². Its weight is 9810 N. What is its mass?",
        # A stated μ is never a distractor: m = F/a was 60 kg for 20.3 kg.
        "A 60 N force pushes a box across a floor with μ = 0.2, giving it an acceleration of "
        "1 m/s². What is its mass?",
        "A 60 N horizontal force pulls a crate with a coefficient of kinetic friction of 0.2. "
        "It accelerates at 1 m/s². Find the mass of the crate.",
        "A 2 kg box on a floor with μ = 0.3 moves at 3 m/s. What is its kinetic energy?",
    ],
)
def test_a_force_that_is_not_the_net_force_declines(text: str) -> None:
    assert _declined(text)


def test_friction_the_law_takes_still_verifies() -> None:
    text = (
        "A 60 N force pulls a 20 kg box across a floor where the coefficient of friction is "
        "0.2. What is the acceleration?"
    )
    assert _verified(text) == (
        "applied_friction_acceleration",
        pytest.approx((60 - 0.2 * 20 * 9.81) / 20, rel=0.01),
    )


@pytest.mark.parametrize(
    "text",
    [
        # a = -g with Earth's g: -9.81 m/s² for 2h/t² = 2.5 m/s².
        "On a planet, a ball dropped from 20 m takes 4 s to land. What is the acceleration due "
        "to gravity?",
        "A ball is dropped from 20 m and takes 4 s to land. What is its acceleration?",
        # A planet left unnamed has no school g: Earth's gave 0.495 s and 1.43 s.
        "An astronaut on a planet drops a hammer from 1.2 m. How long does it take to fall?",
        "On another planet a stone is dropped from 10 m. How long does it take to reach the "
        "ground?",
    ],
)
def test_an_unnamed_planet_takes_no_school_gravity(text: str) -> None:
    assert _declined(text)


@pytest.mark.parametrize(
    ("text", "operation", "value"),
    [
        (
            "An astronaut on the Moon drops a hammer from 1.2 m. How long does it take to fall?",
            "time_to_ground",
            (2 * 1.2 / 1.62) ** 0.5,
        ),
        ("A 2 kg rock sits on a planet where g = 3.7 m/s². What is its weight?", "weight", 7.4),
        # g the law is solved for is the question's own.
        (
            "A 1 m pendulum on a planet has a frequency of 0.4 Hz. What is the acceleration due "
            "to gravity?",
            "pendulum_frequency",
            6.3165,
        ),
    ],
)
def test_a_body_with_a_g_still_verifies(text: str, operation: str, value: float) -> None:
    assert _verified(text) == (operation, pytest.approx(value, rel=0.01))


@pytest.mark.parametrize(
    ("text", "operation", "value"),
    [
        # The combination's result stated is no part: P₂ = P - P₁, not P + P₁ (5 D, 1 D).
        (
            "Two thin lenses in contact have a total power of 3 D. One of them has a power of "
            "2 D. What is the power of the other?",
            "lens_power_sum",
            1.0,
        ),
        (
            "Two lenses in contact have a combined power of +3 D. One lens has a power of -2 D. "
            "What is the power of the other lens?",
            "lens_power_sum",
            5.0,
        ),
        (
            "A lens combination in contact has a net power of 5 D. One lens is 4 D. What is the "
            "power of the second lens?",
            "lens_power_sum",
            1.0,
        ),
        (
            "Two capacitors in parallel have a total capacitance of 10 μF. One is 4 μF. What is "
            "the capacitance of the other?",
            "capacitors_parallel",
            6.0,
        ),
        (
            "Two capacitors in series have an equivalent capacitance of 3 μF. One is 4 μF. What "
            "is the other capacitance?",
            "capacitors_series",
            12.0,
        ),
        (
            "Two springs in parallel have a combined spring constant of 500 N/m. One has "
            "k = 300 N/m. What is the spring constant of the other?",
            "springs_parallel",
            200.0,
        ),
        (
            "A boat crosses a river at right angles to the current. Its resultant speed is "
            "5 m/s and the current flows at 3 m/s. What is the boat's speed relative to the "
            "water?",
            "perpendicular_velocity_sum",
            4.0,
        ),
        # The parts stated, the combination asked: unchanged.
        (
            "Two thin lenses of power 2 D and 4 D are placed in contact. What is the power of "
            "the combination?",
            "lens_power_sum",
            6.0,
        ),
        (
            "A 4 μF and a 6 μF capacitor are connected in series. What is the equivalent "
            "capacitance?",
            "capacitors_series",
            2.4,
        ),
        # The ask's own "total" labels no value.
        (
            "Find the total capacitance of a 4 µF and a 6 µF capacitor in parallel.",
            "capacitors_parallel",
            10.0,
        ),
        (
            "What is the total power of two lenses of 2 D and 4 D in contact?",
            "lens_power_sum",
            6.0,
        ),
    ],
)
def test_a_combination_stated_is_its_result(text: str, operation: str, value: float) -> None:
    assert _verified(text) == (operation, pytest.approx(value, rel=0.01))


@pytest.mark.parametrize(
    ("text", "value"),
    [
        # 24 V output read as V_p gave 4.8 V; the secondary's 12 V gave 3 V and 0.6 V.
        (
            "A transformer has 500 primary turns and 100 secondary turns and gives an output "
            "voltage of 24 V. What is the input voltage?",
            120.0,
        ),
        (
            "A step-down transformer produces a secondary voltage of 12 V. It has 400 turns on "
            "the primary and 100 on the secondary. What is the primary voltage?",
            48.0,
        ),
        (
            "The secondary voltage of a transformer is 12 V. The primary coil has 1000 turns "
            "and the secondary 50 turns. Find the primary voltage.",
            240.0,
        ),
        (
            "A transformer has 100 turns on the primary and 500 turns on the secondary. It is "
            "connected to a 240 V supply. What is the output voltage?",
            1200.0,
        ),
    ],
)
def test_a_transformer_reads_which_coil_each_voltage_is_on(text: str, value: float) -> None:
    assert _verified(text) == ("transformer_voltage", pytest.approx(value, rel=0.01))


@pytest.mark.parametrize(
    ("text", "value"),
    [
        # Read in the order stated, sin 30°/sin 45° was 0.707.
        (
            "The angle of refraction is 30° when the angle of incidence is 45°. What is the "
            "refractive index of the glass?",
            1.414,
        ),
        (
            "A ray in air enters water. The refracted ray makes 30° with the normal and the "
            "incident ray makes 45°. Find the refractive index.",
            1.414,
        ),
        (
            "Find the refractive index of a glass block if light hits it at 45° and refracts "
            "at 30°.",
            1.414,
        ),
        (
            "Light travelling in air strikes a glass block at an angle of incidence of 40°. "
            "The angle of refraction is 25°. What is the refractive index of the glass?",
            1.52,
        ),
    ],
)
def test_the_angle_of_incidence_is_read_by_its_words(text: str, value: float) -> None:
    assert _verified(text) == ("refractive_index", pytest.approx(value, rel=0.01))


@pytest.mark.parametrize(
    "text",
    [
        # Light leaving the medium bends the other way: n = 0.667, 0.752 as if entering.
        "Light passes from glass into air. The angle of incidence in the glass is 30° and the "
        "angle of refraction is 48.6°. What is the refractive index of the glass?",
        "A ray of light leaves water and enters air. The angle in the water is 30° and the "
        "angle in the air is 41.7°. What is the refractive index of water?",
        # λ = nλ_n, not λ/n: 267 nm and 301 nm for 600 nm and 532 nm.
        "Light has a wavelength of 400 nm inside glass of refractive index 1.5. What is its "
        "wavelength in air?",
        "Inside water (refractive index 1.33) the wavelength of a green light is 400 nm. What "
        "is its wavelength in a vacuum?",
    ],
)
def test_light_that_starts_inside_a_medium_declines(text: str) -> None:
    assert _declined(text)


@pytest.mark.parametrize(
    ("text", "operation", "value"),
    [
        (
            "Light of wavelength 600 nm in air enters glass of refractive index 1.5. What is "
            "its wavelength inside the glass?",
            "wavelength_in_medium",
            400.0,
        ),
        (
            "Light travelling in air strikes a glass block of refractive index 1.5 at 30° to "
            "the normal. What is the angle of refraction?",
            "snell_refraction_angle",
            19.47,
        ),
    ],
)
def test_light_from_air_still_verifies(text: str, operation: str, value: float) -> None:
    assert _verified(text) == (operation, pytest.approx(value, rel=0.01))


@pytest.mark.parametrize(
    ("text", "inside"),
    [
        ("Light travelling in water strikes the surface at 30°. Find n.", True),
        ("Light of 600 nm travels in glass. What is its wavelength after it leaves?", True),
        ("Light travelling in air strikes a glass block at 40°. Find n.", False),
        # Where the ask puts the value is not where the light starts.
        ("Light of 600 nm in air enters glass. What is its wavelength inside the glass?", False),
    ],
)
def test_where_light_starts_is_read_before_the_ask(text: str, inside: bool) -> None:
    assert light_starts_inside(text) is inside


@pytest.mark.parametrize(
    "text",
    [
        # 0.8c measured from Earth is the sum: 0.946c for 0.385c and 0.929c for 0.5c.
        "A spaceship moving at 0.6c fires a probe forward. An observer on Earth measures the "
        "probe's speed as 0.8c. What is the probe's speed relative to the ship?",
        "A rocket moving at 0.5c relative to Earth fires a missile forward. An observer on "
        "Earth measures the missile's speed as 0.8c. What is the missile's speed relative to "
        "the rocket?",
        # ½mv² past the classical range: 4.24e8 m/s, faster than light, for 2.60e8 m/s.
        "A particle of mass 9.11 × 10⁻³¹ kg has relativistic kinetic energy 8.2 × 10⁻¹⁴ J. "
        "What is its speed?",
        "A particle of mass 9.11 × 10⁻³¹ kg moves at 2.0 × 10⁸ m/s. What is its kinetic energy?",
        # A ball may be solid or hollow; ½mv² left its spin out (8.37 m/s).
        "A ball of mass 2 kg rolls without slipping with a total kinetic energy of 70 J. What "
        "is its speed?",
        "A 2 kg ball rolls along the floor at 3 m/s. What is its kinetic energy?",
    ],
)
def test_a_relativistic_or_rolling_body_is_not_classical(text: str) -> None:
    assert _declined(text)


@pytest.mark.parametrize(
    ("text", "operation", "value"),
    [
        # ½mv² gave 8.37 m/s for each body.
        (
            "A solid sphere of mass 2 kg rolls without slipping with a total kinetic energy of "
            "70 J. What is its speed?",
            "rolling_body_kinetic_energy",
            50**0.5,
        ),
        (
            "A hoop of mass 2 kg rolls without slipping with a total kinetic energy of 70 J. "
            "What is its speed?",
            "rolling_body_kinetic_energy",
            35**0.5,
        ),
        (
            "A 2 kg block slides with 70 J of kinetic energy. What is its speed?",
            "speed_from_kinetic_energy",
            70**0.5,
        ),
        (
            "A spaceship moving at 0.6c relative to Earth fires a probe forward at 0.8c "
            "relative to the ship. What is the probe's speed relative to Earth?",
            "relativistic_velocity_addition",
            1.4 / 1.48,
        ),
        (
            "A particle of mass 9.11 × 10⁻³¹ kg has a kinetic energy of 1.6 × 10⁻¹⁷ J. What is "
            "its speed?",
            "speed_from_kinetic_energy",
            5.9267e6,
        ),
    ],
)
def test_the_classical_and_rolling_laws_answer_their_own(
    text: str, operation: str, value: float
) -> None:
    assert _verified(text) == (operation, pytest.approx(value, rel=0.01))


@pytest.mark.parametrize(
    "text",
    [
        # Answered with the force on a wire (0.004 N) and the photon's energy.
        "A solenoid 20 cm long carries a current of 2 A and produces a magnetic field of "
        "0.01 T. How many turns does it have?",
        "A hydrogen atom emits a photon of wavelength 656 nm when its electron falls from "
        "n = 3. To which level does it fall?",
        "A hydrogen atom emits a 656 nm photon as its electron drops from n = 3. What energy "
        "level does the electron fall to?",
    ],
)
def test_a_count_or_a_level_asked_is_not_another_quantity(text: str) -> None:
    assert asked_dimensions(text) == ("dimensionless",)
    assert _declined(text)


@pytest.mark.parametrize(
    "text",
    [
        "How many kWh does a 2 kW heater use in 3 hours?",
        "how many kwh does a 2 kw heater use in 3 hours?",
        "How many photons does a 60 W lamp of wavelength 600 nm emit?",
        "How many photons per second does a 60 W lamp of wavelength 600 nm emit?",
        "A 60 W lamp emits light of 600 nm. How many photons does it emit each second?",
    ],
)
def test_a_count_in_a_unit_or_each_second_is_no_pure_number(text: str) -> None:
    assert "dimensionless" not in asked_dimensions(text)


def test_a_count_a_law_gives_still_verifies() -> None:
    text = "A pendulum has a period of 2 s. How many oscillations does it make in 1 minute?"
    assert _verified(text) == ("period_from_count", pytest.approx(30.0))
