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
from app.models.schemas.physics import PhysicsIntent
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


# ---------------------------------------------------------------------------
# Round 3. Three defects and four new ops.
#
# The first defect was invisible from inside this file: every test above calls
# `extract_math_intent` directly, and the extractor reads the original casing.
# `needs_symbolic` lowercases before testing the same cues, so a question
# carried only by the SI symbols was dropped by the pre-filter and never
# reached the extractor in production - while these tests passed. Every round-3
# case below therefore asserts the pre-filter too.
# ---------------------------------------------------------------------------


def _reaches_the_tool_path(text: str) -> bool:
    from app.services.math.match.needs import needs_symbolic

    return needs_symbolic(text)


UNIT_ONLY = [
    ("what is the electrical power for 12 V and 3 A", "electrical_power", "36.00 W"),
    ("a 12 V battery with 4 A of current, what is the resistance", "resistance", "3.00 ohm"),
    ("what is the current for 12 V and 4 ohms", "current", "3.00 A"),
]


@pytest.mark.parametrize("text,op,answer", UNIT_ONLY, ids=[row[0][:44] for row in UNIT_ONLY])
def test_a_question_carried_only_by_its_units_reaches_the_solver(
    text: str, op: str, answer: str
) -> None:
    """The pre-filter assertion is the point; the answer was already right."""
    assert _reaches_the_tool_path(text), "dropped before extraction"
    intent = extract_math_intent(text)
    assert isinstance(intent, PhysicsIntent) and intent.physics_op == op
    assert _verified_answer(text) == answer


BARE_LETTER_DECOYS = [
    "I bought 12 v cards and 3 a piece was the price",
    "i drink 2 a day, she drinks 5 a day",
    "the 5 v 5 format beats 3 v 3",
    "chapter 3 a and chapter 4 a",
    "flight ba 2 a and ba 4 a were cancelled",
]


@pytest.mark.parametrize("text", BARE_LETTER_DECOYS)
def test_lowercase_bare_letters_are_still_not_units(text: str) -> None:
    """Two *different* symbols is most of the rule, but not all of it.

    "12 v cards and 3 a piece" pairs a v with an a exactly as a real question
    does. What separates them is case, which is why the cue stays
    case-sensitive and the pre-filter stopped lowercasing instead.
    """
    assert not _reaches_the_tool_path(text)
    intent = extract_math_intent(text)
    assert intent is None or intent.kind not in PHYSICS_KINDS


# (question, expected op, expected answer)
NETWORKS: list[tuple[str, str, str]] = [
    # Three resistors were read and only two were used, so these were wrong
    # answers rather than gaps: 5.00 ohm for a series of 2, 3 and 5.
    (
        "what is the total resistance of 2 ohms, 3 ohms and 5 ohms in series",
        "series_resistance",
        "10.00 ohm",
    ),
    (
        "what is the total resistance of 4 ohms, 6 ohms and 12 ohms in parallel",
        "parallel_resistance",
        "2.00 ohm",
    ),
    (
        "three resistors of 2 ohms, 3 ohms and 6 ohms in parallel, what is the total",
        "parallel_resistance",
        "1.00 ohm",
    ),
    # One unit for the whole list: these returned nothing at all.
    (
        "two resistors of 4 and 6 ohms in series, what is the total resistance",
        "series_resistance",
        "10.00 ohm",
    ),
    (
        "three resistors of 2, 3 and 6 ohms in parallel, what is the total resistance",
        "parallel_resistance",
        "1.00 ohm",
    ),
    # A unit each, two resistors: the shape that already worked.
    (
        "what is the combined resistance of 4 ohms and 6 ohms in parallel",
        "parallel_resistance",
        "2.40 ohm",
    ),
    (
        "what is the total resistance of a 4 ohm and 6 ohm resistor in series",
        "series_resistance",
        "10.00 ohm",
    ),
]


@pytest.mark.parametrize("text,op,answer", NETWORKS, ids=[row[0][:44] for row in NETWORKS])
def test_resistor_networks_use_every_resistance(text: str, op: str, answer: str) -> None:
    assert _reaches_the_tool_path(text)
    intent = extract_math_intent(text)
    assert isinstance(intent, PhysicsIntent) and intent.physics_op == op
    assert _verified_answer(text) == answer


def test_a_network_larger_than_the_table_is_refused_not_truncated() -> None:
    """Answering from a prefix is the bug, so the cap refuses instead."""
    assert _verified_answer("five resistors of 1, 2, 3, 4 and 5 ohms in series") is None


NEW_OPS: list[tuple[str, str, str]] = [
    ("what is the charge if a current of 3 A flows for 5 s", "charge", "15.00 C"),
    ("how much charge passes when 2 A flows for 10 s", "charge", "20.00 C"),
    ("what charge is delivered by 4 A over 3 s", "charge", "12.00 C"),
    ("what is the energy used by a 2000 W heater in 3 hours", "electrical_energy", "21600000.00 J"),
    ("how much energy does a 100 W bulb use in 10 hours", "electrical_energy", "3600000.00 J"),
    ("energy consumed by a 500 W device in 2 hours", "electrical_energy", "3600000.00 J"),
    ("what is the capacitance storing 6 C at 3 V", "capacitance", "2.00 F"),
    ("a capacitor holds 12 C at 4 V, what is the capacitance", "capacitance", "3.00 F"),
    ("find the capacitance of a capacitor with 10 C at 5 V", "capacitance", "2.00 F"),
    (
        "what is the terminal voltage of a 12 V cell with 0.5 ohm internal resistance drawing 2 A",
        "terminal_voltage",
        "11.00 V",
    ),
    (
        "a 9 V battery with 1 ohm internal resistance supplies 2 A, what is the terminal voltage",
        "terminal_voltage",
        "7.00 V",
    ),
    (
        "find the voltage across the terminals of a 6 V cell, internal resistance 0.5 ohm, 2 A",
        "terminal_voltage",
        "5.00 V",
    ),
]


@pytest.mark.parametrize("text,op,answer", NEW_OPS, ids=[row[0][:44] for row in NEW_OPS])
def test_round_three_circuit_ops(text: str, op: str, answer: str) -> None:
    assert _reaches_the_tool_path(text), "dropped before extraction"
    intent = extract_math_intent(text)
    assert isinstance(intent, PhysicsIntent) and intent.physics_op == op
    assert _verified_answer(text) == answer


def test_every_round_three_circuit_op_has_at_least_three_phrasings() -> None:
    from collections import Counter

    counts = Counter(op for _, op, _ in NEW_OPS)
    thin = {op: n for op, n in counts.items() if n < 3}
    assert not thin, f"ops with fewer than three phrasings: {thin}"
    assert set(counts) == {"charge", "electrical_energy", "capacitance", "terminal_voltage"}


def test_a_cell_with_internal_resistance_is_ohms_law_unless_the_ask_says_terminal() -> None:
    """The EMF is the other answer to "what voltage", so the ask must say which.

    Choosing between them on the reader's behalf is the kind of guess a
    verified block must not make.
    """
    intent = extract_math_intent(
        "a 12 V cell with 0.5 ohm internal resistance supplies 2 A, what is the voltage"
    )
    assert getattr(intent, "physics_op", None) != "terminal_voltage"


ROUND_THREE_DECOYS = [
    "charge my card for the 2 tickets",
    "the energy in this 3 person team is great",
    "i have 2 chargers and 3 cables",
    "my phone takes 2 hours to charge",
]


@pytest.mark.parametrize("text", ROUND_THREE_DECOYS)
def test_the_new_circuit_cues_do_not_steal_ordinary_english(text: str) -> None:
    intent = extract_math_intent(text)
    assert intent is None or intent.kind not in PHYSICS_KINDS
