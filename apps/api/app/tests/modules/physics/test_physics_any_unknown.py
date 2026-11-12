"""Every law answers whichever of its quantities is asked (phone test, 2026-11-11).

The owner's phone test sent right answers out unverified: F = ma asked for a with the force
in words, W = Fs asked for s, density = m/V asked with grams and for m, d = vt in miles per
hour, and questions pasted in LaTeX. Each answer below is worked by hand (g = 9.81 m/s²).
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.direct import maybe_direct_physics_reply
from app.modules.physics.numbers import unit_names_as_symbols
from app.modules.physics.prompt import solve_physics_request
from app.tests.modules.physics.support import answer_number
from app.tests.modules.physics.test_physics_binding import _answer

_SETTINGS = Settings.model_validate({})


@pytest.mark.parametrize(
    ("text", "operation", "value"),
    [
        # F = ma, the force in words.
        (
            "A net force of 30 Newtons is applied to a 6 kg box. What is the acceleration of the box?",
            "net_force",
            5.0,
        ),
        (
            "A net force of 2 kilonewtons acts on a 500 kg car. Find its acceleration.",
            "net_force",
            4.0,
        ),
        # W = Fs solved for s and for F; the law asked its own way still answers.
        (
            "An engine does 400 Joules of work pushing a cart with a constant force of 80 Newtons. "
            "How far did the cart move?",
            "work",
            5.0,
        ),
        ("How far does a box move if 150 J of work is done on it by a 30 N push?", "work", 5.0),
        (
            "A machine does 2000 J of work moving a crate 8 m. What force did it apply?",
            "work",
            250.0,
        ),
        ("How much work is done when a force of 80 N moves a cart 5 m?", "work", 400.0),
        # Density = m/V, with grams and solved for m and V.
        (
            "A solid metal cube has a mass of 100 grams and a volume of 20 cm³. "
            "What is the density of the metal?",
            "density",
            5000.0,
        ),
        (
            "A liquid has a density of 2.5 g/mL. If you have 40 mL of this liquid, what is its mass?",
            "density",
            0.1,
        ),
        (
            "A block of wood has a density of 600 kg/m³ and a mass of 3 kg. What is its volume?",
            "density",
            0.005,
        ),
        # ½mv², mgh and P = W/t, each solved for another of its quantities.
        (
            "A ball moving at 4 m/s has 40 J of kinetic energy. What is its mass?",
            "kinetic_energy",
            5.0,
        ),
        (
            "A 2 kg book has 40 J of potential energy. How high is it above the floor?",
            "potential_energy",
            40 / (2 * 9.81),
        ),
        (
            "A motor delivers 600 W of power for 10 seconds. How much work does it do?",
            "power",
            6000.0,
        ),
        ("A motor does 6000 J of work with a power of 600 W. How long does it run?", "power", 10.0),
        # d = vt in miles per hour, which has no slash to split.
        (
            "A train moves at a constant speed of 60 miles per hour for 4.5 hours. "
            "How far does the train travel?",
            "rate_distance",
            270.0,
        ),
        (
            "How long does it take to drive 270 miles at a steady 60 miles per hour?",
            "rate_time",
            4.5,
        ),
    ],
)
def test_a_law_answers_the_quantity_asked(text: str, operation: str, value: float) -> None:
    outcome, block = solve_physics_request(text, _SETTINGS, None)
    assert outcome == "verified", text
    assert block is not None and block.physics_intent is not None
    assert block.physics_intent.physics_op == operation
    assert answer_number(block.canonical_answer or "") == pytest.approx(value, rel=0.01)


@pytest.mark.parametrize(
    "text",
    [
        # Not the only force: F = ma answers the net force, which is not asked.
        "How much force does a spring exert on a 5 kg mass accelerating at 2 m/s²?",
        "What is the centripetal force on a 5 kg mass accelerating at 2 m/s^2",
        # 1 mm is the tube's diameter, not the rise the question asks.
        "Water with surface tension 0.072 N/m rises in a capillary tube of diameter 1 mm. "
        "Find the height of the rise.",
        # The initial pressure is stated; the final one is not the law's stated result.
        "A gas at constant temperature is compressed to 2 L at 300 kPa. "
        "Its initial pressure was 100 kPa. What was its initial volume?",
        # Energy of no named kind: kinetic is one guess of several.
        "A 2 kg ball has 100 J of energy. How fast is it moving?",
        # The law's word is in the sentence but labels no value of its kind.
        "A cart that does work is pushed 400 J by a force of 80 N. How far does it move?",
        # A result the words state as a size while its sign moves the answer (review
        # 2026-11-11): 120 °C for 40, 0 °C for 80, 18.2 L for 5.48, 7 m/s for 3.
        "A 2 kg block of iron cools from 80 °C, giving out 36000 J of heat. What is its final "
        "temperature? The specific heat capacity of iron is 450 J/kg°C.",
        "A 2 kg block of iron cools to 40 °C, giving out 36000 J of heat. What was its initial "
        "temperature? (c = 450 J/kg°C)",
        "2 mol of an ideal gas at 300 K is compressed isothermally from 10 L. 3000 J of work "
        "is done on the gas. What is the final volume?",
        "A 2 kg ball moving at 5 m/s is hit by a bat with an average force of 40 N for 0.1 s "
        "in the opposite direction. What is its final speed?",
        "Two forces act on a box in opposite directions. The net force is 10 N and one force "
        "is 30 N. What is the other force?",
        # A unit of two words is no unit of its first: 30 N·m, never 30 N and "metres".
        "A wrench applies a torque of 30 newton metres to a bolt. The wrench is 0.5 m long. "
        "What force is applied?",
        "An impulse of 6 newton seconds acts on a 2 kg ball over 0.3 s. What is the change in "
        "momentum?",
        "A bat delivers an impulse of 6 newton-seconds over 0.3 s. What is the change in "
        "momentum of the ball?",
        # Thousands grouped by a space: 1200 kg or a 1 and a 200 kg.
        "A car of mass 1 200 kg moves at 20 m/s. What is its kinetic energy?",
        # The ask is one part of a divided body; the values are the whole's.
        "A 6 kg block is cut in half. What is the weight of each half?",
        "An object has a density of 2 g/cm³ and a volume of 3 cm³ and is cut in half. "
        "What is the mass of each half?",
        "A 6 kg block is split into three equal pieces. What is the weight of each piece?",
    ],
)
def test_a_result_the_words_do_not_state_is_never_solved_for(text: str) -> None:
    assert _answer(text) is None


def test_the_working_rearranges_the_law_for_the_asked_quantity() -> None:
    text = (
        "An engine does 400 Joules of work pushing a cart with a constant force of 80 Newtons. "
        "How far did the cart move?"
    )
    outcome, block = solve_physics_request(text, _SETTINGS, None)
    assert outcome == "verified" and block is not None
    reply = maybe_direct_physics_reply(block, text)
    assert reply is not None
    lines = [line.strip() for line in reply.splitlines()]
    law = lines.index("$W = Fs$")
    assert lines[law + 1 : law + 3] == ["Solve for $s$", r"$s = \frac{W}{F}$"]
    # The stated result is a given named by what the law is asked for.
    assert "$W = 400\\,\\mathrm{J}$" in lines
    assert any(line.startswith("where") and "$W$ = work" in line for line in lines)


def test_a_form_the_givens_choose_is_the_one_rearranged() -> None:
    text = "A motor delivers 600 W of power for 10 seconds. How much work does it do?"
    outcome, block = solve_physics_request(text, _SETTINGS, None)
    assert outcome == "verified" and block is not None
    reply = maybe_direct_physics_reply(block, text)
    assert reply is not None
    lines = [line.strip() for line in reply.splitlines()]
    law = lines.index(r"$P = \frac{W}{t}$")
    assert lines[law + 1 : law + 3] == ["Solve for $W$", "$W = P t$"]


@pytest.mark.parametrize(
    ("written", "read"),
    [
        ("a net force of 30 Newtons", "a net force of 30 N"),
        ("100 grams of water and 2 kilograms of ice", "100 g of water and 2 kg of ice"),
        ("a 12 volt battery and 3 amps", "a 12 V battery and 3 A"),
        ("at 300 kelvin", "at 300 K"),
        # Kinds every reader already reads in words stay as written.
        (
            "for 4.5 hours over 20 metres at 30 degrees",
            "for 4.5 hours over 20 metres at 30 degrees",
        ),
        ("500 turns", "500 turns"),
        ("20 degrees Celsius", "20 degrees Celsius"),
        # A unit that goes on past its name is the table's to read whole, or nobody's.
        ("3 joules per second", "3 joules per second"),
        ("Newton's second law", "Newton's second law"),
        # So is a unit of two words, joined or not, and a name in the possessive.
        ("a torque of 30 newton metres", "a torque of 30 newton metres"),
        ("20 newton-seconds", "20 newton-seconds"),
        ("5 joule seconds", "5 joule seconds"),
        ("5 volt amperes", "5 volt amperes"),
        ("2 Newtons' laws", "2 Newtons' laws"),
        ("2 newtons of force", "2 N of force"),
    ],
)
def test_a_unit_named_in_words_reads_as_its_symbol(written: str, read: str) -> None:
    assert unit_names_as_symbols(written) == read


@pytest.mark.parametrize(
    ("text", "value"),
    [
        (
            r"Two point charges, \(q_1 = +2.0 \, \mu\text{C}\) and \(q_2 = -6.0 \, \mu\text{C}\), "
            r"are separated by a distance of \(0.30 \text{ m}\) in a vacuum "
            r"(\(k_e \approx 9.0 \times 10^9 \text{ N}\cdot\text{m}^2/\text{C}^2\)). "
            "What is the magnitude of the electrostatic force between them?",
            1.2,
        ),
        (
            "Two point charges, q1 = +2.0 μC and q2 = -6.0 μC, are 0.30 m apart "
            "(k = 9.0 × 10^9 N·m²/C²). What is the magnitude of the electrostatic force?",
            1.2,
        ),
        (
            r"A 3.0 kg cart moving at \(+4.0 \text{ m/s}\) collides head-on and sticks together "
            "with a 1.0 kg stationary cart. What is the final velocity of the combined carts "
            "immediately after the collision?",
            3.0,
        ),
        (
            r"A \(12.0 \text{ V}\) battery is connected to three resistors in parallel: "
            r"\(R_1 = 4.0 \, \Omega\), \(R_2 = 6.0 \, \Omega\), and \(R_3 = 12.0 \, \Omega\). "
            "What is the total current drawn from the battery?",
            6.0,
        ),
        (
            r"A \(5.0 \text{ kg}\) block on a horizontal floor is pushed with a horizontal force "
            r"of \(25 \text{ N}\). The coefficient of kinetic friction is \(\mu_k = 0.30\). "
            r"What is the acceleration of the block? (Use \(g = 9.8 \text{ m/s}^2\).)",
            2.06,
        ),
        (
            r"A net force of $25\,\mathrm{N}$ acts on a $5.0\,\mathrm{kg}$ cart. Find its acceleration.",
            5.0,
        ),
        (r"\[ m = 2.0\,\mathrm{kg},\quad v = 3.0\,\mathrm{m/s} \] Find the kinetic energy.", 9.0),
        # Thin spaces between digit groups are one number: 1500 kg, never 500.
        (
            r"A \(1\,500\,\text{kg}\) car accelerates at \(2\,\text{m/s}^2\). What is the net force?",
            3000.0,
        ),
    ],
)
def test_a_question_in_latex_reads_as_its_plain_text(text: str, value: float) -> None:
    answer = _answer(text)
    assert answer is not None, text
    assert answer_number(answer) == pytest.approx(value, rel=0.01)


def test_a_stated_constant_is_the_one_the_answer_uses() -> None:
    # k = 9e9, not CODATA's 8.99e9: 0.6 N as the question works it, not 0.599 N.
    text = (
        "Two charges q1 = 2 μC and q2 = 3 μC are 0.3 m apart, with k = 9 × 10^9 N·m²/C². "
        "Find the force."
    )
    answer = _answer(text)
    assert answer is not None
    assert answer_number(answer) == pytest.approx(0.6, rel=1e-6)
    assert answer_number(_answer(text.replace(", with k = 9 × 10^9 N·m²/C²", "")) or "") == (
        pytest.approx(0.599, rel=1e-3)
    )


@pytest.mark.parametrize(
    "text",
    [
        # A law whose result is in degrees, solved backwards from it: the stated angle reached
        # the rearranged arithmetic in radians and was read as degrees (review, 2026-11-11).
        # Glass is n = 1/sin 42° = 1.49; it was 78.2.
        "The critical angle of glass is 42°. Calculate the refractive index of glass.",
        "If the critical angle of a medium is 45°, what is its refractive index?",
        "The critical angle for diamond is 24.4°. What is the refractive index of diamond?",
        "Light in water strikes the water-air surface. The critical angle is 48.8°. "
        "What is the refractive index of the water?",
        # λ = d sin θ / n is 5.88e-7 m; it was 1.1e-8 m.
        "A diffraction grating with 500 lines per mm gives a second-order bright fringe at an "
        "angle of 36°. What is the wavelength?",
        "Light falls on a grating with 300 lines per mm. The first-order maximum is at an angle "
        "of 10.4°. What is the wavelength?",
    ],
)
def test_a_law_whose_result_is_not_in_si_is_not_solved_backwards(text: str) -> None:
    assert _answer(text) is None


@pytest.mark.parametrize(
    ("operation", "backwards"),
    [
        ("critical_angle_to_air", False),  # degrees
        ("grating_angle", False),
        ("efficiency_percent", False),  # a percent: 75 % is 0.75 in SI
        ("work", True),
        ("density", True),
    ],
)
def test_only_a_law_whose_result_is_in_si_is_solved_backwards(
    operation: str, backwards: bool
) -> None:
    from app.modules.physics.catalog import CATALOG
    from app.modules.physics.solvers.si import solves_backwards_in_si

    assert solves_backwards_in_si(CATALOG[operation]) is backwards


@pytest.mark.parametrize(
    ("unit", "name", "offset"),
    [("°C", "temp_change", True), ("degF", "temperature", True), ("°C", "delta_t", False)],
)
def test_a_reading_on_an_offset_scale_is_no_size_to_solve_from(
    unit: str, name: str, offset: bool
) -> None:
    from app.modules.physics.schemas import PhysicsIntent
    from app.modules.physics.solvers.si import stated_on_an_offset_scale

    # Only its units are read: built without the checks a whole intent passes.
    intent = PhysicsIntent.model_construct(physics_params={name: 10.0}, physics_units={name: unit})
    assert stated_on_an_offset_scale(intent, name) is offset
