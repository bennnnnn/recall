"""A law reads the parts the question gives it, not every value written in its unit.

Reviews 2026-11-07: once prefixed values were read, a voltmeter's 20 MΩ was summed into a
loop as a series resistor (3e-7 A for 2 mA), a steady 500 mA and "increases by 3 A" were
read as a current going from one to the other (50 V for 60 V), and "Ignoring the Earth's
50 µT field" took that field for the one asked about. The same questions in unprefixed
units were already wrong; each reader now takes only what the words give it, and reads
a change, a meter and a set-aside quantity the ways English states them.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.physics.extractors.circuit_patterns import resistor_values
from app.modules.physics.extractors.stated_change import stated_change
from app.modules.physics.extractors.stated_values import positioned_values
from app.modules.physics.extractors.unit_patterns import AMP_PATTERN
from app.modules.physics.givens import PHYSICS_UNITS, scan_givens
from app.modules.physics.set_aside import set_aside, uses_set_aside_part

_SETTINGS = Settings(math_tools_enabled=True)


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(
    "text",
    [
        "A voltmeter of resistance 20 MΩ measures the voltage across a 2 kΩ resistor.",
        "A 10 MΩ voltmeter is connected across a 2 kΩ resistor and a 3 kΩ resistor.",
        "An ammeter of resistance 2 Ω is connected in parallel with a 6 Ω resistor.",
    ],
)
def test_a_meter_across_a_part_is_no_resistor_of_the_path(text: str) -> None:
    assert resistor_values(text) == []


@pytest.mark.parametrize(
    ("text", "values"),
    [
        ("A 2 kΩ resistor and a 3 kΩ resistor are connected in series.", [2000.0, 3000.0]),
        # A meter named with no resistance of its own leaves the resistors as they are.
        ("The voltmeter reads 4 V across a 2 Ω resistor and a 4 Ω resistor.", [2.0, 4.0]),
        ("Resistors of 2 Ω and 3.5 Ω with an internal resistance of 500 mΩ.", [2.0, 3.5, 0.5]),
        # An ammeter or a galvanometer in series is part of the path.
        (
            "A 12 V battery is in series with a 5 Ω resistor and an ammeter of resistance 1 Ω.",
            [5.0, 1.0],
        ),
        (
            "A galvanometer of resistance 50 Ω is in series with a 950 Ω resistor across 1 V.",
            [50.0, 950.0],
        ),
    ],
)
def test_resistors_of_the_path_are_read(text: str, values: list[float]) -> None:
    assert resistor_values(text) == pytest.approx(values)


@pytest.mark.parametrize(
    "text",
    [
        "In a loop, a 6 V cell drives current through a 1 kΩ resistor and a 2 kΩ resistor. "
        "A voltmeter of resistance 20 MΩ measures the voltage across the 2 kΩ resistor. "
        "What is the current in the loop?",
        "In a loop, a 9 V battery drives current through a 10 Ω resistor and a 20 Ω resistor. "
        "A voltmeter of resistance 10 kΩ is connected in parallel with the 20 Ω resistor. "
        "What is the current in the loop?",
        "In a loop, a 12 V battery is connected to resistors of 100 Ω and 200 Ω. A 300 Ω "
        "resistor is in parallel with the 200 Ω one. What is the current in the loop?",
        # A part bridging or across another is in parallel with it.
        "In a loop, a 9 V battery drives a 3 Ω resistor and a 6 Ω resistor. The 6 Ω resistor "
        "is bridged by a 12 Ω resistor. What is the current from the battery?",
        "In a loop, a 12 V battery drives a 2 Ω resistor and a 4 Ω resistor. A 3 Ω resistor is "
        "connected across a 4 Ω resistor. What is the current from the battery?",
        "In a loop, a 12 V battery drives a 2 Ω resistor, a 4 Ω resistor and a 6 Ω resistor, "
        "the last two side by side between the same pair of points. What is the current?",
    ],
)
def test_the_loop_rule_reads_only_one_series_path(text: str) -> None:
    assert _answer(text) is None


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        (
            "In a loop, a 12 V battery with an internal resistance of 500 mΩ is connected to "
            "resistors of 2 Ω and 3.5 Ω. What is the current in the loop?",
            "2 A",
        ),
        (
            "In a loop, a 12 V battery is connected to resistors of 2 kΩ and 4 kΩ. "
            "What is the current in the loop?",
            "0.002 A",
        ),
        # A measured branch current puts no part on a branch.
        (
            "In a loop, a 9 V battery drives a 3 Ω resistor and a 6 Ω resistor, and the branch "
            "current is measured. What is the current?",
            "1 A",
        ),
        (
            "A 12 V battery is connected in series with a 5 Ω resistor and an ammeter of "
            "resistance 1 Ω. What is the current?",
            "2 A",
        ),
        (
            "A galvanometer of resistance 50 Ω is connected in series with a 950 Ω resistor "
            "across 1 V. What current flows?",
            "0.001 A",
        ),
        (
            "In a loop, a 12 V battery drives a 2 Ω resistor and a 4 Ω resistor, and the ammeter "
            "in the branch reads the current. What is the current?",
            "2 A",
        ),
    ],
)
def test_a_series_path_still_answers(text: str, answer: str) -> None:
    assert _answer(text) == answer


@pytest.mark.parametrize(
    ("text", "change"),
    [
        ("A steady current of 500 mA then increases by 3 A in 0.1 s.", 3.0),
        ("A current change of 2 A in 10 ms.", 2.0),
        ("Its current changes from 20 mA to 50 mA in 0.01 s.", 0.03),
        ("Its current goes from 1 A up to 4 A in 0.1 s.", 3.0),
        ("Its current falls from 4 A down to 1 A in 0.1 s.", 3.0),
        ("Its current changes between 1 A and 4 A in 0.1 s.", 3.0),
        ("Its current rises to 4 A from 1 A in 0.1 s.", 3.0),
        ("A current that rises from 2A to 5A in 30 ms.", 3.0),
        ("Its current rises from 1 A → 4 A in 0.1 s.", 3.0),
        ("Its current goes 1 A → 4 A in 0.1 s.", 3.0),
        ("The current is 1 A initially and 4 A 0.1 s later.", 3.0),
        ("The current of 1 A in a 2 H inductor moves up to 4 A in 0.1 s.", 3.0),
        ("Its current increases from 1 A, going to 4 A in 0.1 s.", 3.0),
        # The next sentence may name the same thing changing; another thing is no end.
        ("It carries 1 A. Its current is raised to 4 A in 0.1 s.", 3.0),
        ("The current is 3 A. A second coil's current rises to 5 A in 0.1 s.", None),
        # The second end closes the change: a fuse's or a load's rating is no end.
        ("A current of 2 A goes through it to a 5 A fuse. It is switched off in 0.1 s.", None),
        ("It carries 1 A from a supply to a 4 A load.", None),
        ("Its current rises from 1 A to its rated 4 A in 0.1 s.", 3.0),
        ("The current is 4 A. It falls to 1 A in 0.1 s.", 3.0),
        ("It carries 2 A, which goes through a fuse rated to 5 A.", None),
        ("It carries 1 A at first, and a second coil carries 4 A after 0.1 s.", None),
        ("It carries 1 A. The current elsewhere in the circuit rises to 4 A in 0.1 s.", None),
        # Two currents no words make one change's ends are two currents.
        ("It carries 500 mA, and another coil carries 3 A.", None),
        ("It is limited by a 2 A fuse and rises from 0 to 1.5 A in 0.1 s.", None),
        ("A 4 A current flows and is connected to a 5 A supply.", None),
    ],
)
def test_a_change_is_read_the_ways_it_is_said(text: str, change: float | None) -> None:
    found = stated_change(text, positioned_values(text, AMP_PATTERN))
    assert found == (None if change is None else pytest.approx(change))


@pytest.mark.parametrize(
    "text",
    [
        "A 2 H inductor's current goes from 1 A up to 4 A in 0.1 s. What is the induced emf?",
        "A 2 H inductor's current falls from 4 A down to 1 A in 0.1 s. What is the induced emf?",
        "A 2 H inductor's current changes between 1 A and 4 A in 0.1 s. What is the induced emf?",
        "A 2 H inductor's current rises to 4 A from 1 A in 0.1 s. What is the induced emf?",
    ],
)
def test_an_inductor_reads_a_change_however_it_is_said(text: str) -> None:
    assert _answer(text) == "60 V"


def test_a_steady_current_beside_a_change_declines() -> None:
    text = (
        "A 2 H inductor carries a steady current of 500 mA. The current then increases by "
        "3 A in 0.1 s. What is the induced emf?"
    )
    assert _answer(text) is None


@pytest.mark.parametrize(
    "middle",
    [
        "sees the field fall from 0.7 T down to 0.2 T in 0.1 s",
        "is in a field that is 0.2 T at first and 0.7 T after 0.1 s",
        "is moved from a 0.7 T field into a 0.2 T field in 0.1 s",
        "in a 0.2 T field has the field raised to 0.7 T in 0.1 s",
        "in a 0.7 T field goes to a region of 0.2 T in 0.1 s",
        "is carried from a 0.2 T region to a 0.7 T region in 0.1 s",
    ],
)
def test_faraday_reads_a_change_of_field_however_it_is_said(middle: str) -> None:
    text = f"A coil of 200 turns and area 0.01 m^2 {middle}. What is the induced emf?"
    assert _answer(text) == "10 V"


def test_two_fields_not_one_change_are_no_change_in_flux() -> None:
    text = (
        "A coil of 100 turns and area 0.02 m^2 sits in a 0.5 T field next to a 50 mT field. "
        "What is the induced emf if the flux changes in 0.1 s?"
    )
    assert _answer(text) is None


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        (
            "Ignoring the Earth's 50 µT field, a 30 cm wire carrying 2 A sits in a 0.2 T field.",
            [30.0, 2.0, 0.2],
        ),
        (
            "A 30 cm wire carrying 2 A sits in a 0.2 T field. Ignore the Earth's 50 µT field.",
            [30.0, 2.0, 0.2],
        ),
        ("A 12 V battery drives a 3 Ω resistor. Ignore its 5 Ω internal resistance.", [12.0, 3.0]),
        # The thing set aside is named before the number, or the phrase never closes: the
        # number belongs to the rest of the sentence.
        (
            "Neglecting the wires 6 Ω and 3 Ω resistors are in parallel across 12 V.",
            [6.0, 3.0, 12.0],
        ),
        ("Ignoring internal resistance a 6 Ω and a 3 Ω resistor are in parallel.", [6.0, 3.0]),
        ("Ignoring friction forces of 3 N and 4 N act at right angles on a box.", [3.0, 4.0]),
        ("Ignoring losses a 2 kW kettle runs for 3 min.", [2.0, 3.0]),
        ("Ignore the 6 Ω and 3 Ω resistors are in parallel across 12 V.", [6.0, 3.0, 12.0]),
        # A possessive after the number makes it the owner's, never set aside.
        ("Ignoring the 6 Ω resistor's heating, a 12 V battery drives it.", [6.0, 12.0]),
        ("Ignoring the 1200 kg car's rolling resistance, it accelerates at 2 m/s².", [1200.0, 2.0]),
        # An owner with a value of its own keeps it; what it owns is set aside.
        (
            "Ignoring the 12 V battery's 0.5 Ω internal resistance, it drives a 4 Ω resistor.",
            [12.0, 4.0],
        ),
        # A comma then a value of the same kind continues a list, which sets nothing aside.
        ("Ignoring the 2 Ω, 3 Ω and 5 Ω resistors' tolerances, their total?", [2.0, 3.0, 5.0]),
        ("Ignoring the 440 Hz, 444 Hz forks' damping, what beat frequency?", [440.0, 444.0]),
        ("Ignoring the 4 Ω, a 12 V battery drives a 6 Ω resistor.", [12.0, 6.0]),
        # After "a" a new clause starts, so the comma closes: the trailer's 500 kg is set aside.
        ("Ignoring the trailer's 500 kg, a 1000 kg car accelerates at 2 m/s².", [1000.0, 2.0]),
    ],
)
def test_a_quantity_set_aside_is_no_given(text: str, kept: list[float]) -> None:
    assert [given.value for given in scan_givens(text)] == kept


def test_set_aside_names_only_its_own_closed_phrase() -> None:
    text = "Ignoring the Earth's 50 µT field, a wire"
    start = text.index("50")
    assert set_aside(text, start, start + 2, PHYSICS_UNITS)


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        (
            "Ignoring the Earth's 50 µT field, a 30 cm wire carrying 2 A sits in a 0.2 T field. "
            "What force acts on it?",
            "0.12 N",
        ),
        (
            "Neglect friction two forces 30 N and 40 N act at right angles on a box. What is "
            "the resultant force?",
            "50 N at 53.1°",
        ),
        (
            "Ignoring the battery 2 Ω and 3 Ω resistors are in series. What is the total "
            "resistance?",
            "5 Ω",
        ),
    ],
)
def test_set_aside_answers_with_what_is_left(text: str, answer: str) -> None:
    assert _answer(text) == answer


@pytest.mark.parametrize(
    "text",
    [
        "A 5 kg block slides down a 30° slope. The coefficient of friction is 0.2, but neglect "
        "friction. What is the acceleration?",
        "A 10 kg crate is pulled by a 50 N force on a floor with μ = 0.3. Ignore friction. What "
        "is its acceleration?",
    ],
)
def test_a_part_set_aside_by_name_is_not_used(text: str) -> None:
    assert _answer(text) is None


@pytest.mark.parametrize(
    ("text", "used"),
    [
        ("Ignore friction.", True),
        ("Neglecting air resistance and friction, a block is pushed.", True),
        ("The friction coefficient is 0.3.", False),
        # Placed, timed or negated, the part is not set aside whole.
        ("Ignore friction at the axle. A crate on a floor with μ = 0.3.", False),
        ("Ignore drag for the first second.", False),
        ("Without ignoring friction (μ = 0.3), a crate is pulled.", False),
        ("Never neglect friction. A crate with μ = 0.3.", False),
        ("A crate with μ = 0.3. Neglect friction and find its acceleration.", True),
        ("Neglecting frictional forces, what is its acceleration?", True),
    ],
)
def test_a_part_set_aside_names_its_inputs(text: str, used: bool) -> None:
    assert uses_set_aside_part({"mu": 0.3, "drag_k": 0.5}, text) is used


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        (
            "Ignoring the 1200 kg car's rolling resistance, the car accelerates at 2 m/s². "
            "What is the net force?",
            "2400 N",
        ),
        (
            "Ignoring the 2 H inductor's resistance, what emf is induced when its current rises "
            "from 1 A to 4 A in 0.1 s?",
            "60 V",
        ),
        (
            "Ignoring the 12 V battery's 0.5 Ω internal resistance, what current does it drive "
            "through a 4 Ω resistor?",
            "3 A",
        ),
        (
            "Ignore friction at the axle. A 10 kg crate is pulled by 50 N across a floor with "
            "μ = 0.3. What is its acceleration?",
            "2.06 m/s²",
        ),
        (
            "Ignoring the 2 Ω, 3 Ω and 5 Ω resistors' tolerances, what is their total "
            "resistance in series?",
            "10 Ω",
        ),
        (
            "Neglecting the 4 Ω, 6 Ω and 12 Ω resistors' heating, what is their combined "
            "resistance in parallel?",
            "2 Ω",
        ),
        ("Ignoring the 440 Hz, 444 Hz forks' damping, what beat frequency do they make?", "4 Hz"),
        ("Ignoring the 4 Ω, a 12 V battery drives a 6 Ω resistor. What current flows?", "2 A"),
        # A body that only owns what is set aside lends no gravity.
        (
            "Ignoring the Moon's 1.6 m/s², a ball is dropped from 20 m on Earth. How long does "
            "it take to land?",
            "2.02 s",
        ),
    ],
)
def test_an_owner_and_a_placed_part_keep_their_values(text: str, answer: str) -> None:
    assert _answer(text) == answer


def test_a_possessive_never_sets_aside_the_owner() -> None:
    # "the 6 Ω resistor's heating" set the resistor aside: 4 A for 1.33 A.
    text = (
        "Ignoring the 6 Ω resistor's heating, what current flows when a 12 V battery is "
        "connected to it and a 3 Ω resistor in series?"
    )
    assert _answer(text) in (None, "1.33 A")
