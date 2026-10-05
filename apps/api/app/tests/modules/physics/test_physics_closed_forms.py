"""The one-expression laws added after the catalog close-out."""

from __future__ import annotations

import pytest

from app.modules.physics.extract import extract_physics_intent
from app.tests.modules.physics.support import answer_number
from app.tests.modules.physics.test_physics_binding import _answer

_CASES = [
    (
        "A wire carries 1.60 A through area 1.00e-4 m^2 with number density 1.00e28 /m^3. "
        "Find the drift speed.",
        "drift_speed",
        9.986e-6,
    ),
    (
        "Two parallel wires carry 2.00 A and 3.00 A and are 0.100 m apart. "
        "Find the force per unit length.",
        "wire_force_per_length",
        1.2e-5,
    ),
    (
        "An ideal gas has gamma 1.40, pressure 1.01e5 Pa, and density 1.20 kg/m^3. "
        "Find the speed of sound.",
        "ideal_gas_sound_speed",
        343.27,
    ),
    (
        "An ideal transformer has 100 primary turns, 500 secondary turns, "
        "and primary current 2.00 A. Find the secondary current.",
        "transformer_current",
        0.4,
    ),
    (
        "A parallel-plate capacitor has plate area 0.0200 m^2, separation 0.00100 m, "
        "and dielectric constant 5.00. Find the capacitance.",
        "dielectric_parallel_plate",
        8.854e-10,
    ),
    (
        "A blackbody with emissivity 1 and area 1 m^2 has body temperature 300 K "
        "and surroundings 290 K. Find the net radiated power.",
        "net_blackbody_power",
        58.246,
    ),
    (
        "An adiabatic process has gamma 1.40, initial temperature 300 K, "
        "initial volume 2.00 L, and final volume 1.00 L. Find the final temperature.",
        "adiabatic_temperature",
        395.85,
    ),
    (
        "Cv is 20.8 J/(mol·K). Use Mayer's relation to find the molar heat capacity "
        "at constant pressure.",
        "mayer_cp",
        29.114,
    ),
    (
        "Cp is 29.1 J/(mol·K). Use Mayer's relation to find the molar heat capacity "
        "at constant volume.",
        "mayer_cv",
        20.786,
    ),
    (
        "A series circuit has inductive reactance 150 ohm, capacitive reactance 50 ohm, "
        "and resistance 100 ohm. Find the tangent of the phase angle.",
        "series_phase_tangent",
        1.0,
    ),
    (
        "An AC circuit has rms voltage 120 V, rms current 2.00 A, and a phase angle "
        "of 60 degrees. Find the average power.",
        "average_power_phase",
        120.0,
    ),
    (
        "A hydrogen-like ion has atomic number 2 and n = 1. Find its energy.",
        "hydrogenlike_energy",
        -8.716e-18,
    ),
    (
        "A mutual inductance of 0.200 H has its current change by 3.00 A during 0.500 s. "
        "Find the induced emf.",
        "mutual_inductance_emf",
        1.2,
    ),
    (
        "An electric dipole moment of 1.0e-9 C·m is observed at a distance of 0.0500 m "
        "on its axis. Find the electric field.",
        "dipole_field_axis",
        1.438e5,
    ),
    (
        "Masses of 1 kg at 0 m, 2 kg at 2 m, and 3 kg at 6 m. Find the center of mass.",
        "center_of_mass_three",
        3.6667,
    ),
]


@pytest.mark.parametrize(("text", "operation", "value"), _CASES)
def test_a_closed_form_is_verified(text: str, operation: str, value: float) -> None:
    intent = extract_physics_intent(text)
    assert intent is not None and intent.physics_op == operation
    answer = _answer(text)
    assert answer is not None
    assert answer_number(answer) == pytest.approx(value, rel=0.02)


@pytest.mark.parametrize(
    "text",
    [
        "Two parallel wires carry 2.00 A and 3.00 A. Find the force per unit length.",
        "A hydrogen-like ion has n = 1. Find its energy.",
        "Masses of 1 kg at 0 m, 2 kg at 2 m, 3 kg at 6 m, and 4 kg at 8 m. "
        "Find the center of mass.",
        "A parallel-plate capacitor has plate area 0.02 m^2 and separation 1 mm "
        "and a dielectric. Find the capacitance.",
    ],
)
def test_a_closed_form_with_a_missing_input_declines(text: str) -> None:
    assert _answer(text) is None
