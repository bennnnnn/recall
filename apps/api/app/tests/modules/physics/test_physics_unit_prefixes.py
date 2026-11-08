"""A unit keeps its SI prefix wherever it is read, and a written unit is never assumed.

Audit 2026-11-07: "500 mHz" was read as megahertz (a caseless table), "k = 2 kN/m" as
2 N/m and "k = 500 g/s" as 500 kg/s (an extractor's own pattern, then a default), each
shipped as verified. Every reader now asks the shared table, which reads a prefix in
its written case, and a unit it cannot read is converted by Pint or refused.

Review 2026-11-07: a reader that widened its pattern to prefixed units handed "2 kΩ" on
to a consumer that wrote "ohm" (2 A for 2 mA), and a unit read only in part ("N" of
"N kg^-1") refused a g. A widened match now comes in its base unit, and the whole unit
is read, its reading chosen by the dimension the slot expects.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.physics.accounting import competing_given
from app.modules.physics.extractors.stated_values import (
    find_value_with_specific_unit,
    ordered_values,
)
from app.modules.physics.extractors.surface_gravity import gravity_unit_unread, stated_gravity
from app.modules.physics.extractors.unit_patterns import (
    AMP_PATTERN,
    OHM_PATTERN,
    in_base_unit,
    with_prefixes,
)
from app.modules.physics.extractors.written_unit import written_unit
from app.modules.physics.givens import scan_givens
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solvers.si import params_in_si, to_si
from app.services.law_binding.units import keeps_prefix
from app.services.solving import SolveServiceError

_SETTINGS = Settings(math_tools_enabled=True)


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(
    ("written", "expression", "kept"),
    [
        ("mHz", "megahertz", False),
        ("mhz", "megahertz", False),
        ("Ms", "millisecond", False),
        ("Mm/s", "millimeter / second", False),
        # Capitals throughout say nothing of case.
        ("MHZ", "megahertz", True),
        ("MS", "millisecond", True),
        ("MMHG", "millimeter_Hg", True),
        ("PF", "picofarad", True),
        # Spelled out, a prefix has no case; with no twin, a fold is safe.
        ("Milliohms", "milliohm", True),
        ("Megohms", "megaohm", True),
        ("Kg", "kilogram", True),
        ("KHz", "kilohertz", True),
        # Not a prefix at all: a mile, a pound per square inch, a pascal.
        ("MPH", "mile / hour", True),
        ("PSI", "psi", True),
        ("pa", "pascal", True),
    ],
)
def test_a_caseless_reading_keeps_the_prefix_as_written(
    written: str, expression: str, kept: bool
) -> None:
    assert keeps_prefix(written, expression) is kept


@pytest.mark.parametrize(
    ("text", "si"),
    [
        ("500 mHz", 0.5),
        ("500 MHz", 5e8),
        ("5 mN", 0.005),
        ("2 kN/m", 2000),
        ("50 N/cm", 5000),
        ("500 g/s", 0.5),
        ("50 µT", 5e-5),
        ("50 uT", 5e-5),
        ("3 mT", 0.003),
        ("20 µA", 2e-5),
        ("2 kA", 2000),
        ("4 µH", 4e-6),
        ("2 GW", 2e9),
        ("3 mJ", 0.003),
        ("1 GeV", 1.602176634e-10),
        ("760 torr", 101325),
        ("2 AU", 2 * 149597870700),
        ("500 Å", 5e-8),
        ("4.2 light-years", 4.2 * 9460730472580800),
        ("1 kcal", 4184),
        ("1 knot", 0.514444),
        # Look-alikes that read as before.
        ("5 mg", 5e-6),
        ("500 MG", 5e-4),
        ("760 MMHG", 101325.0144),
        ("3 Kilometres", 3000),
        ("50 hertz", 50),
    ],
)
def test_the_scan_reads_each_prefix_in_its_case(text: str, si: float) -> None:
    [given] = scan_givens(text)
    assert given.si == pytest.approx(si)


@pytest.mark.parametrize("text", ["5 Mg", "2 Mm/s", "500 mhz"])
def test_a_prefix_in_the_other_case_is_not_read(text: str) -> None:
    # "Mg" is no milligram and "mhz" no megahertz: m is milli, M mega.
    assert [given.dimension for given in scan_givens(text)] == [None]


@pytest.mark.parametrize(
    ("value", "unit", "key", "si"),
    [
        (500, "mHz", "freq", 0.5),
        (500, "MHz", "freq", 5e8),
        (500, "Mhz", "freq", 5e8),
        (200, "MPa", "sigma", 2e8),
        (2, "mT", "b_field", 0.002),
        (760, "MMHG", "pres", 101325.0144),
        (5, "kpa", "pres", 5000),
        (50, "hz", "freq", 50),
        (3, "KHz", "freq", 3000),
        (3, "N/mm", "k", 3000),
    ],
)
def test_to_si_reads_the_prefix_as_written(value: float, unit: str, key: str, si: float) -> None:
    assert to_si(value, unit, expected_key=key) == pytest.approx(si)


@pytest.mark.parametrize(
    ("unit", "key"),
    [
        ("mhz", "freq"),
        ("mpa", "sigma"),
        ("mev", "energy"),
        # Matched as "ms", "MPa" and "mm/s" without case: Pint would read the other prefix.
        ("Ms", "t"),
        ("mPa", "sigma"),
        ("Mm/s", "v"),
    ],
)
def test_a_prefix_that_could_be_either_is_refused(unit: str, key: str) -> None:
    with pytest.raises(SolveServiceError):
        to_si(1.0, unit, expected_key=key)


@pytest.mark.parametrize(
    ("text", "unit"),
    [
        ("200", ""),
        ("200 and m = 2 kg", ""),
        ("200, x", ""),
        ("2 kN/m", "kN/m"),
        ("3 N/mm", "N/mm"),
        ("2 lbf/in", "lbf/in"),
        ("10 ms^-2", "ms^-2"),
        ("200N", "N"),
    ],
)
def test_the_unit_after_a_number_is_read_never_assumed(text: str, unit: str) -> None:
    number = text.split(" ")[0].rstrip("N,")
    assert written_unit(text, len(number)) == unit


@pytest.mark.parametrize(
    ("text", "key", "unit", "si"),
    [
        ("10 N kg^-1.", "g", "N kg^-1", 10),
        ("10 N kg⁻¹.", "g", "N kg⁻¹", 10),
        ("9.8 meters per second per second.", "g", "meters per second per second", 9.8),
        # In a g, "ms^-2" is m·s⁻²: a millisecond⁻² is no acceleration.
        ("1.6 ms^-2.", "g", "ms^-2", 1.6),
        ("10ms-2.", "g", "ms-2", 10),
        ("200 Nm^-1 is", "k", "Nm^-1", 200),
        ("0.5 kg s^-1.", "drag_k", "kg s^-1", 0.5),
        ("2 min.", "t", "min", 120),
    ],
)
def test_the_whole_unit_is_read_in_the_slot_dimension(
    text: str, key: str, unit: str, si: float
) -> None:
    number = text.split(" ")[0].split("m")[0]
    written = written_unit(text, len(number), key)
    assert written == unit
    assert to_si(float(number), written, expected_key=key) == pytest.approx(si)


def test_a_widened_pattern_reads_no_unit_of_another_case() -> None:
    # "h" is an hour; read without case it also took "mH", a millihenry, for a time.
    widened = with_prefixes(r"seconds?|s|hours?|h")
    assert "mH" not in widened and "µH" not in widened
    assert "ms" in widened


@pytest.mark.parametrize(
    ("text", "pattern", "read"),
    [
        ("a 2 kΩ resistor", OHM_PATTERN, (2000.0, "Ω")),
        ("a 4.7 kohm resistor", OHM_PATTERN, (4700.0, "ohm")),
        ("a current of 300 µA", AMP_PATTERN, (0.0003, "A")),
        ("a force of 5 mN", "N", (0.005, "N")),
        # A unit the pattern reads itself is handed on as written.
        ("a 2 Ω resistor", OHM_PATTERN, (2.0, "Ω")),
        ("a 3 mT field", "T|mT", (3.0, "mT")),
    ],
)
def test_a_widened_match_comes_in_its_base_unit(
    text: str, pattern: str, read: tuple[float, str]
) -> None:
    value, unit = find_value_with_specific_unit(text, pattern) or (None, "")
    assert (value, unit) == (pytest.approx(read[0]), read[1])


def test_values_in_order_come_in_their_base_unit() -> None:
    values = ordered_values("Currents of 200 mA and 3 A enter", AMP_PATTERN)
    assert [(pytest.approx(value), unit) for value, unit in values] == [
        (pytest.approx(0.2), "A"),
        (pytest.approx(3.0), "A"),
    ]


def test_written_numbers_add_up_only_in_one_unit() -> None:
    # 4 kΩ - 2 kΩ is no 2 Ω resistor: the accounting let 2 kΩ read as 2 Ω through.
    text = "In a loop, a 12 V battery is connected to resistors of 2 kΩ and 4 kΩ."
    intent = PhysicsIntent(
        kind="circuit",
        physics_op="kirchhoff_loop",
        physics_params={"V": 12.0, "R1": 2.0, "R2": 4.0},
        physics_units={"V": "V", "R1": "ohm", "R2": "ohm"},
        operation="solve",
    )
    assert competing_given(intent, text) is not None
    right = intent.model_copy(update={"physics_params": {"V": 12.0, "R1": 2000.0, "R2": 4000.0}})
    assert competing_given(right, text) is None


@pytest.mark.parametrize(
    ("text", "k_si"),
    [
        ("A spring with k = 2 kN/m is stretched 3 cm. What force does it exert?", 2000),
        ("A spring with spring constant 50 N/cm is stretched 3 cm. What force?", 5000),
        ("A spring with k = 3 N/mm is stretched 2 cm. What force does it exert?", 3000),
        # Nothing written after the number: the SI unit.
        ("A spring with k = 200 is stretched 0.1 m. What force does it exert?", 200),
        ("A spring with k = 200 N/m is stretched 10 cm. What force does it exert?", 200),
    ],
)
def test_a_spring_constant_keeps_its_unit(text: str, k_si: float) -> None:
    intent = extract_physics_intent(text)
    assert intent is not None and intent.physics_op == "spring_force"
    assert params_in_si(intent)["k"] == pytest.approx(k_si)


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("A spring with k = 2 kN/m is stretched 3 cm. What force does it exert?", "60 N"),
        ("A wave has a frequency of 500 mHz and a wavelength of 2 m. What is its speed?", "1 m/s"),
        (
            "In a loop, a 12 V battery is connected to resistors of 2 kΩ and 4 kΩ. "
            "What is the current in the loop?",
            "0.002 A",
        ),
        (
            "A 2 H inductor has its current change from 20 mA to 50 mA in 0.01 s. "
            "What is the induced emf in the inductor?",
            "6 V",
        ),
        (
            "A 2 kΩ resistor and a 3 kΩ resistor are connected in series. What is the total resistance?",
            "5000 Ω",
        ),
        ("A force of 5 mN acts on a 2 g mass. What is the acceleration?", "2.5 m/s²"),
        ("A spring with k = 200 Nm^-1 is stretched 0.1 m. What force does it exert?", "20 N"),
        ("A ball is dropped from 20 m. Take g = 10 N kg^-1. How long does it take to land?", "2 s"),
        ("A pendulum of length 1 m swings where g = 1.6 ms^-2. What is its period?", "4.97 s"),
    ],
)
def test_the_audit_answers_are_right(text: str, answer: str) -> None:
    assert _answer(text) == answer


@pytest.mark.parametrize(
    ("text", "key", "si"),
    [
        (
            "A 2 kg ball falls with linear drag, k = 500 g/s. What is its terminal velocity?",
            "drag_k",
            0.5,
        ),
        (
            "A 2 kg ball falls with linear drag, k = 0.5 kg/s. What is its terminal velocity?",
            "drag_k",
            0.5,
        ),
        (
            "A 2 kg ball falls with linear drag, k = 0.5. What is its terminal velocity?",
            "drag_k",
            0.5,
        ),
        (
            "A 2 kg ball falls from rest with linear drag, k = 0.5 kg/s. What is its speed at t = 200 ms?",
            "t",
            0.2,
        ),
    ],
)
def test_a_drag_constant_and_time_keep_their_units(text: str, key: str, si: float) -> None:
    intent = extract_physics_intent(text)
    assert intent is not None and intent.physics_op == "linear_drag_fall"
    assert params_in_si(intent)[key] == pytest.approx(si)


@pytest.mark.parametrize(
    ("text", "g"),
    [
        ("g = 9.8 m/s^2", 9.8),
        ("g = 10", 10.0),
        ("Using g = 32 ft/s^2", 9.7536),
        ("where g = 980 cm/s²", 9.8),
        ("gravity of 9.8 N/kg", 9.8),
        ("Take g = 10 N kg^-1.", 10.0),
        ("Take g = 10 N kg⁻¹.", 10.0),
        ("g = 9.8 meters per second per second", 9.8),
        ("g = 1.6 ms^-2", 1.6),
        ("Take g = 10ms-2.", 10.0),
    ],
)
def test_a_stated_g_is_read_in_its_unit(text: str, g: float) -> None:
    assert stated_gravity(text) == pytest.approx(g)
    assert not gravity_unit_unread(text)


def test_a_g_in_a_unit_nothing_reads_declines() -> None:
    text = "A ball is dropped from 20 m. Take g = 9.8 bananas/s^2. How long does it take to land?"
    assert gravity_unit_unread(text)
    assert _answer(text) is None


@pytest.mark.parametrize(
    ("unit", "key"), [("Cal", "heat"), ("CAL", "heat"), ("MS", "t"), ("MN", "F")]
)
def test_a_spelling_listed_only_in_another_case_has_no_reading(unit: str, key: str) -> None:
    # A food Calorie is a kcal: folded to "cal" it was 1046 J for 1.046 MJ (review 2026-11-07).
    with pytest.raises(SolveServiceError):
        to_si(250, unit, expected_key=key)


@pytest.mark.parametrize(
    ("value", "unit", "key", "si"),
    [(2, "l", "volume", 0.002), (1, "au", "d", 149597870700), (9.8, "ms²", "g", 9.8)],
)
def test_a_caseless_or_slipped_spelling_still_reads(
    value: float, unit: str, key: str, si: float
) -> None:
    # "ms²" in a g is m/s² that lost its slash; no other reading is an acceleration.
    assert to_si(value, unit, expected_key=key) == pytest.approx(si)


@pytest.mark.parametrize(
    ("value", "unit", "pattern", "read"),
    [
        (3.0, "cm^2", r"m\^?2", (3e-4, "m^2")),
        (3.0, "cm³", "m³", (3e-6, "m³")),
        (5.0, "km/s", "m/s", (5000.0, "m/s")),
    ],
)
def test_a_prefix_is_raised_to_its_units_power(
    value: float, unit: str, pattern: str, read: tuple[float, str]
) -> None:
    converted, base = in_base_unit(value, unit, pattern)
    assert (converted, base) == (pytest.approx(read[0]), read[1])
