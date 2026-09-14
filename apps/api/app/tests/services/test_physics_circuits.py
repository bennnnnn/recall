"""P8: Ohm's law and resistance networks.

The first topic here that is not mechanics, which is also the point — it proves
the physics package generalises past motion.

Two collisions shaped it. `"series"` and `"parallel"` belong to mathematics
first: a geometric series is a `series` intent and a parallelogram is its own
kind. And `power` already exists as a *mechanical* op (`P = F v`, newtons and
m/s). Electrical power is a different quantity that happens to share the name
and the watt, so it is its own op and fires only when electrical units are
present.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.math.tools import _build_verified_block, extract_math_intent

PHYSICS_KINDS = {
    "kinematics",
    "projectile",
    "force",
    "energy",
    "momentum",
    "friction",
    "circular",
    "spring",
    "circuit",
}


def _settings() -> Settings:
    return Settings(math_tools_enabled=True)


def _verified_answer(text: str) -> str | None:
    intent = extract_math_intent(text)
    if intent is None:
        return None
    block = _build_verified_block(intent, _settings())
    return None if block is None else block.canonical_answer


# V = 12, I = 3, R = 4 throughout, so all three rearrangements share one triangle.
VERIFIED: list[tuple[str, str, str]] = [
    ("what is the current if the voltage is 12 V and resistance is 4 ohms", "current", "3.00 A"),
    ("find the current for a 12 V supply across a 4 ohm resistor", "current", "3.00 A"),
    (
        "a 12 V battery is connected to a 4 ohm resistance, what is the current",
        "current",
        "3.00 A",
    ),
    ("find the voltage with current 3 A and resistance 4 ohms", "voltage", "12.00 V"),
    ("what is the voltage across a 4 ohm resistor carrying 3 A", "voltage", "12.00 V"),
    ("calculate the voltage for 3 amps through 4 ohms", "voltage", "12.00 V"),
    ("resistance when voltage is 12 V and current is 3 A", "resistance", "4.00 ohm"),
    (
        "what is the resistance of a resistor with 12 V across it and 3 A through it",
        "resistance",
        "4.00 ohm",
    ),
    ("find the resistance for 12 volts and 3 amps", "resistance", "4.00 ohm"),
    ("power dissipated by a 4 ohm resistor carrying 3 A", "electrical_power", "36.00 W"),
    ("what is the electrical power for 12 V and 3 A", "electrical_power", "36.00 W"),
    (
        "two resistors of 4 ohms and 6 ohms in series, what is the total resistance",
        "series_resistance",
        "10.00 ohm",
    ),
    (
        "two resistors of 4 ohms and 6 ohms in parallel, what is the total resistance",
        "parallel_resistance",
        "2.40 ohm",
    ),
]


@pytest.mark.parametrize("text,op,answer", VERIFIED, ids=[row[0][:44] for row in VERIFIED])
def test_circuit_phrasings_reach_a_verified_answer(text: str, op: str, answer: str) -> None:
    intent = extract_math_intent(text)
    assert intent is not None, "no intent extracted"
    assert intent.kind == "circuit"
    assert intent.physics_op == op
    assert _verified_answer(text) == answer


def test_all_three_rearrangements_of_ohms_law_verify() -> None:
    """The ticket's acceptance clause, stated as one fact.

    The extractor reads the question from its *givens* — whichever of V, I, R is
    absent is the one being asked — so the three rearrangements need no separate
    wording rules.
    """
    from collections import Counter

    covered = Counter(op for _, op, _ in VERIFIED)

    assert covered["voltage"] >= 3
    assert covered["current"] >= 3
    assert covered["resistance"] >= 3


# --- the physics ------------------------------------------------------------


def test_the_three_rearrangements_agree_with_each_other() -> None:
    """One triangle: 12 V, 3 A, 4 ohms. Each answer must reproduce the others."""
    assert _verified_answer("what is the current if the voltage is 12 V and resistance is 4 ohms")
    v = _verified_answer("find the voltage with current 3 A and resistance 4 ohms")
    i = _verified_answer("what is the current if the voltage is 12 V and resistance is 4 ohms")
    r = _verified_answer("resistance when voltage is 12 V and current is 3 A")

    assert v is not None and i is not None and r is not None
    assert float(v.split()[0]) == pytest.approx(float(i.split()[0]) * float(r.split()[0]))


def test_parallel_resistance_is_below_the_smaller_resistor() -> None:
    """The property that catches a series/parallel mix-up immediately."""
    parallel = _verified_answer(
        "two resistors of 4 ohms and 6 ohms in parallel, what is the total resistance"
    )
    series = _verified_answer(
        "two resistors of 4 ohms and 6 ohms in series, what is the total resistance"
    )

    assert parallel is not None and series is not None
    assert float(parallel.split()[0]) < 4.0
    assert float(series.split()[0]) == pytest.approx(10.0)


def test_power_agrees_across_its_three_forms() -> None:
    """P = VI, I^2 R and V^2/R are one quantity reached three ways."""
    from_vi = _verified_answer("what is the electrical power for 12 V and 3 A")
    from_ir = _verified_answer("power dissipated by a 4 ohm resistor carrying 3 A")
    from_vr = _verified_answer("power dissipated by a 4 ohm resistor across 12 V")

    assert from_vi is not None and from_ir is not None and from_vr is not None
    assert float(from_vi.split()[0]) == pytest.approx(36.0)
    assert float(from_ir.split()[0]) == pytest.approx(36.0)
    assert float(from_vr.split()[0]) == pytest.approx(36.0)


# --- the two name collisions ------------------------------------------------


def test_mechanical_power_is_untouched() -> None:
    """`power` already existed as a mechanical op, in newtons and m/s.

    Electrical power shares the name and the watt but is a different quantity,
    so it is a separate op that fires only on electrical units. The ticket
    called this out specifically: the two must not collide silently.
    """
    intent = extract_math_intent("what is the power of a force of 10 N moving at 3 m/s")

    assert intent is not None and intent.kind == "energy"
    assert intent.physics_op == "power"
    assert _verified_answer("what is the power of a force of 10 N moving at 3 m/s") == "30.00 W"


@pytest.mark.parametrize(
    "text",
    [
        "sum the series 1 + 1/2 + 1/4",
        "find the sum of the geometric series with ratio 0.5",
        "are these two lines parallel",
    ],
)
def test_series_and_parallel_are_not_cues(text: str) -> None:
    """Both belong to mathematics first, so neither may stand alone.

    They qualify a question that already names resistors; they never start one.
    """
    intent = extract_math_intent(text)
    assert intent is None or intent.kind not in PHYSICS_KINDS


def test_parallelogram_geometry_is_untouched() -> None:
    intent = extract_math_intent("area of a parallelogram with base 4 and height 6")

    assert intent is not None and intent.kind == "parallelogram"
    assert _verified_answer("area of a parallelogram with base 4 and height 6") == "24"


def test_the_current_date_is_not_a_circuit() -> None:
    """ "current" is left out of the cue list for this reason."""
    intent = extract_math_intent("what is the current date")
    assert intent is None or intent.kind not in PHYSICS_KINDS


def test_bare_letters_are_matched_case_sensitively() -> None:
    """V and A are SI symbols, so the signature regex does not lowercase them.

    Matching case-insensitively would read "3 a piece" as three amps.
    """
    intent = extract_math_intent("I bought 12 v cards and 3 a piece was the price")
    assert intent is None or intent.kind not in PHYSICS_KINDS


# --- refusals ---------------------------------------------------------------


UNDERSPECIFIED = [
    "what is the current through the resistor",
    "find the voltage across a 4 ohm resistor",
    "two resistors in series, what is the total resistance",
]


@pytest.mark.parametrize("text", UNDERSPECIFIED)
def test_circuits_missing_a_given_are_refused(text: str) -> None:
    assert _verified_answer(text) is None
