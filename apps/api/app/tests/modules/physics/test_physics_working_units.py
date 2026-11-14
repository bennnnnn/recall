"""Each number of a worked substitution carries the unit of the law symbol it replaced.

The cases a review of 2026-11-10 found printed wrong when units were matched by value: a
braking distance in m/s, a reaction distance in m²/s², a horizontal throw's speed in metres,
a torque in J. Each line here is the exact line a student reads.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.direct import format_direct_physics_working
from app.tests.modules.physics.support import build_verified_physics_block, extract_physics_intent


def _working(question: str) -> list[str]:
    intent = extract_physics_intent(question)
    assert intent is not None
    block = build_verified_physics_block(intent, Settings(math_tools_enabled=True))
    assert block is not None
    reply = format_direct_physics_working(block)
    assert reply is not None
    section = reply.split("**Substitution**", 1)[1].split("**Answer", 1)[0]
    return [line.strip() for line in section.splitlines() if line.strip()]


@pytest.mark.parametrize(
    ("question", "lines"),
    [
        (
            "The speed of a car increases uniformly from 8m/s to 48 m/s in 10s. "
            "Calculate the acceleration.",
            [
                r"$a = \frac{48\,\mathrm{m/s} - 8\,\mathrm{m/s}}{10\,\mathrm{s}}$",
                r"$a = \frac{40\,\mathrm{m/s}}{10\,\mathrm{s}}$",
            ],
        ),
        (
            "A driver has a reaction time of 1 s, travels at 10 m/s and brakes at 10 m/s^2. "
            "What is the stopping distance?",
            [
                r"$d_r = 10\,\mathrm{m/s} \times 1\,\mathrm{s} = 10\,\mathrm{m}$",
                r"$d_b = \frac{(10\,\mathrm{m/s})^{2}}{2 \times 10\,\mathrm{m/s²}} = 5\,\mathrm{m}$",
                r"$d = 10\,\mathrm{m} + 5\,\mathrm{m} = 15\,\mathrm{m}$",
            ],
        ),
        (
            "A driver has a reaction time of 6 s, travels at 6 m/s and brakes at 6 m/s^2. "
            "What is the stopping distance?",
            [
                r"$d_r = 6\,\mathrm{m/s} \times 6\,\mathrm{s} = 36\,\mathrm{m}$",
                r"$d_b = \frac{(6\,\mathrm{m/s})^{2}}{2 \times 6\,\mathrm{m/s²}} = 3\,\mathrm{m}$",
            ],
        ),
        (
            "A driver has a reaction time of 2 s, travels at 20 m/s and brakes at 2 m/s^2. "
            "What is the stopping distance?",
            [
                r"$d_r = 20\,\mathrm{m/s} \times 2\,\mathrm{s} = 40\,\mathrm{m}$",
                r"$d_b = \frac{(20\,\mathrm{m/s})^{2}}{2 \times 2\,\mathrm{m/s²}} = 100\,\mathrm{m}$",
            ],
        ),
        # The flight time is worked elsewhere: no symbol here says what 0.638551 is, so
        # the row stays as the solver wrote it, never with the speed in metres.
        (
            "A ball is thrown horizontally at 2 m/s from a 2 m high cliff. "
            "How far from the base does it land?",
            [r"$R = 2\cos(0^\circ) \times 0.638551$"],
        ),
        # A torque is N·m, a centripetal force's m v² is kg·m²/s², never J.
        (
            "A 16 N force acts 0.5 m from a pivot at right angles. What is the torque?",
            [r"$\tau = 16\,\mathrm{N} \times 0.5\,\mathrm{m}$"],
        ),
        (
            "A 2 kg mass moves in a circle of radius 0.5 m at 4 m/s. Find the centripetal force.",
            [
                r"$F_c = \frac{2\,\mathrm{kg} \times (4\,\mathrm{m/s})^{2}}{0.5\,\mathrm{m}}$",
                r"$F_c = \frac{32\,\mathrm{kg·m²/s²}}{0.5\,\mathrm{m}}$",
            ],
        ),
    ],
)
def test_each_number_carries_its_symbols_unit(question: str, lines: list[str]) -> None:
    working = _working(question)
    for line in lines:
        assert line in working, working
    assert not any(r"\,\mathrm{J}" in line for line in working if "tau" in line or "F_c" in line)


@pytest.mark.parametrize(
    ("question", "line"),
    [
        (
            "What is the magnetic field 5 cm from a long straight wire carrying 10 A?",
            r"{2 \pi \times 0.05\,\mathrm{m}}$",
        ),
        (
            "A child sits 2.5 m from the centre of a merry-go-round that turns once every 6 s. "
            "What is her speed?",
            r"$v = \frac{2 \pi \times 2.5\,\mathrm{m}}{6\,\mathrm{s}}$",
        ),
    ],
)
def test_a_number_after_pi_keeps_its_times_sign(question: str, line: str) -> None:
    """2π then 0.05 m is a product: "2 π 0.05" would read as one number."""
    assert any(row.endswith(line) for row in _working(question)), _working(question)


def test_a_worked_value_states_the_unit_its_quantity_is_in() -> None:
    """1/R_p and the R_p that follows it read in one unit, Ω⁻¹."""
    working = _working(
        "Find the total resistance of 4 ohm, 6 ohm and 12 ohm resistors in parallel."
    )
    assert r"$\frac{1}{R_p} = 0.5\,\mathrm{Ω⁻¹}$" in working
    assert r"$R_p = \frac{1}{0.5\,\mathrm{Ω⁻¹}}$" in working
