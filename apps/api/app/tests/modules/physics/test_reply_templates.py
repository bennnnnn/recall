# ruff: noqa: RUF003 -- the rows a student reads hold ×, µ and Greek letters.
"""The rows a server-written physics reply prints are true and say what they are.

Review 2026-11-12 (docs/reviews/2026-11-12-physics/REPORT.md §1.2): a given's factor after
its unit (D1), conversions the working never used (D2), a symbol never defined (D3), stock
phrases (D4), six-figure values on the way to the answer (D5) and a bare letter under
Required (D6). The last row stays the value reached, unrounded: only the card rounds (the
owner's rule, kept when D5 was fixed).
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.physics.direct import maybe_direct_physics_reply
from app.modules.physics.display import latex_working
from app.modules.physics.formula_rows import formula_rows
from app.modules.physics.given_rows import given_value
from app.modules.physics.schemas import PhysicsIntent

_SETTINGS = Settings(math_tools_enabled=True)


def _reply(text: str) -> str:
    intent = extract_physics_intent(text)
    assert intent is not None
    block = build_verified_physics_block(intent, _SETTINGS)
    assert block is not None
    reply = maybe_direct_physics_reply(block, text)
    assert reply is not None
    return reply


def _section(reply: str, heading: str) -> str:
    return reply.split(f"**{heading}**", 1)[1].split("\n\n", 1)[0].strip()


@pytest.mark.parametrize(
    ("name", "value", "unit", "arithmetic", "row"),
    [
        # A prefix's power of ten is the SI value already: one step.
        ("q1", 3.0, "uC", r"3 \times 10^{-6}", r"3\,\mathrm{µC} = 3 \times 10^{-6}\,\mathrm{C}"),
        (
            "q2",
            -5.0,
            "uC",
            r"-5 \times 10^{-6}",
            r"-5\,\mathrm{µC} = -5 \times 10^{-6}\,\mathrm{C}",
        ),
        # A factor that changes the number shows it in the SI unit, every side equal.
        (
            "d",
            30.0,
            "cm",
            "40 \\times 0.3",
            r"30\,\mathrm{cm} = 30 \times 0.01\,\mathrm{m} = 0.3\,\mathrm{m}",
        ),
        (
            "v",
            72.0,
            "km/h",
            r"20 \times 1800",
            r"72\,\mathrm{km/h} = 72 \times 1000/3600\,\mathrm{m/s} = 20\,\mathrm{m/s}",
        ),
        # The arithmetic works in the written value: no conversion.
        ("m", 80.0, "g", r"N = \frac{80}{2^{4}}", r"80\,\mathrm{g}"),
        # The written value only as a power is not the given used.
        (
            "t",
            2.0,
            "h",
            r"x = 7200^{2}",
            r"2\,\mathrm{h} = 2 \times 3600\,\mathrm{s} = 7200\,\mathrm{s}",
        ),
    ],
)
def test_a_given_row_is_a_true_equation(
    name: str, value: float, unit: str, arithmetic: str, row: str
) -> None:
    assert given_value(name, value, unit, arithmetic) == row


def test_no_given_row_puts_a_factor_after_its_unit() -> None:
    reply = _reply(
        "Two point charges of 3 μC and −5 μC are 0.2 m apart. "
        "What is the magnitude of the force between them?"
    )
    given = _section(reply, "Given")
    assert r"$q_1 = 3\,\mathrm{µC} = 3 \times 10^{-6}\,\mathrm{C}$" in given
    assert r"\mathrm{µC} \times" not in given


def test_a_half_life_shows_the_halves_and_converts_nothing_it_does_not_use() -> None:
    reply = _reply(
        "An 80 g sample of a radioactive isotope has a half-life of 5 days. "
        "How much of it remains after 20 days?"
    )
    given = _section(reply, "Given")
    assert r"$m = 80\,\mathrm{g}$" in given
    assert r"$T_{1/2} = 5\,\mathrm{days}$" in given
    assert r"\mathrm{kg}" not in given and r"\mathrm{s}" not in given
    assert r"$n = \frac{t}{T_{1/2}}$" in reply.split("**Substitution**")[0]
    substitution = _section(reply, "Substitution")
    assert substitution.startswith(
        r"$n = \frac{20\,\mathrm{days}}{5\,\mathrm{days}}$  " + "\n$n = 4$"
    )
    assert "**Required**  \n$N$ (mass remaining)" in reply


def test_halves_from_times_in_two_units_are_worked_in_seconds() -> None:
    reply = _reply(
        "A 40 g sample has a half-life of 2 days. How much of it remains after 96 hours?"
    )
    substitution = _section(reply, "Substitution")
    assert r"\mathrm{s}}{" in substitution and "$n = 2$" in substitution


def test_a_symbol_worked_from_the_givens_is_named_not_solved_for() -> None:
    reply = _reply(
        "How much heat is needed to raise the temperature of 2 kg of water from 20 °C to "
        "80 °C? Take c = 4186 J/(kg·K)."
    )
    law = reply.split("**Specific heat formula**", 1)[1].split("**Substitution**", 1)[0]
    assert "Solve for" not in law and "same law" not in law
    assert r"$Q = m c (T_2 - T_1)$ — with $\Delta T = T_2 - T_1$" in law
    # The value comes once, with its unit, in the substitution.
    assert r"60\,\mathrm{K}" in _section(reply, "Substitution")


def test_a_right_angle_is_named_where_the_sine_drops() -> None:
    reply = _reply(
        "A 30 cm spanner is pushed with a force of 40 N at right angles at its end. "
        "What torque is produced?"
    )
    assert r"$\tau = F d$ — with $\theta = 90^\circ$" in reply
    assert "**Required**  \n$\\tau$ (torque)" in reply


def test_working_rounds_on_the_way_and_ends_on_the_value_unrounded() -> None:
    reply = _reply(
        "A football is kicked at 18 m/s at 35° above the horizontal on level ground. Find its range."
    )
    substitution = _section(reply, "Substitution")
    assert "0.9397" in substitution and "0.939693" not in substitution
    assert substitution.endswith(r"$R = 31.0357\,\mathrm{m}$")
    assert "```answer\n31\\,\\mathrm{m}\n```" in reply


@pytest.mark.parametrize(
    ("question", "last_row", "card"),
    [
        # The look-alikes of the range: a speed, a time and an energy whose cards round.
        (
            "A ball is dropped from a height of 20 m. How fast is it moving when it hits the "
            "ground?",
            r"$v_{impact} = 19.8091\,\mathrm{m/s}$",
            r"19.8\,\mathrm{m/s}",
        ),
        (
            "What is the period of a simple pendulum 1 m long?",
            r"$T = 2.00607\,\mathrm{s}$",
            r"2.01\,\mathrm{s}",
        ),
        (
            "Find the total resistance of 4 ohm, 6 ohm and 7 ohm resistors in parallel.",
            r"$R_p = 1.78723\,\Omega$",
            r"1.79\,\Omega",
        ),
    ],
)
def test_the_last_row_is_unrounded_and_only_the_card_rounds(
    question: str, last_row: str, card: str
) -> None:
    reply = _reply(question)
    assert _section(reply, "Substitution").endswith(last_row)
    assert f"```answer\n{card}\n```" in reply


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (8372.0, "8372"),
        (0.0025, "0.0025"),
        (1.5e-11, r"1.5 \times 10^{-11}"),
        (0.9396926207859084, "0.9397"),
        (6.283185307179586, "6.283"),
        (304.4604, "304.5"),
    ],
)
def test_a_working_value_is_whole_or_four_figures(value: float, shown: str) -> None:
    assert latex_working(value) == shown


def _intent(kind: str, operation: str, params: dict[str, float]) -> PhysicsIntent:
    return PhysicsIntent.model_validate(
        {"kind": kind, "physics_op": operation, "physics_params": params}
    )


def test_a_balance_is_stated_not_solved_for() -> None:
    reply = _reply(
        "A 6 kg shell at rest explodes into two pieces, 2 kg and 4 kg. The 2 kg piece flies "
        "off at 30 m/s. how fast does the 4 kg piece move?"
    )
    assert "Solve for $0$" not in reply
    assert "$0 = m_1 v_1 - m_2 v_2$  \nSolve for $v_2$" in reply


def test_a_chained_base_is_not_written_again() -> None:
    rows = formula_rows(
        _intent("spring", "spring_max_speed", {"m": 0.5, "k": 200.0, "amplitude": 0.05}),
        [r"v_{max} = A \sqrt{\frac{k}{m}}"],
        "v_{max}",
    )
    assert all("same law" not in row for row in rows)
    assert len(rows) == 1
