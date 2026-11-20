"""Review probes: the physics reader answers with part of the question unread (2026-11-19).

Each test sends a student's question through the real chat path (``stem_sweep.run_entry``) and
asserts today's verified number, which is wrong: a word, an operator or a missing value the
reader never read, filled with its law's default. Each passes while the defect exists. They
document the reading-layer review and are skipped in CI; a fix turns one red, and then it is
deleted or inverted into the fix's own test.

    RECALL_REVIEW_PROBES=1 uv run pytest app/tests/review/test_reading_completeness.py -q
"""

from __future__ import annotations

import math
import os

import pytest

from app.tests.behavior.stem_sweep import Entry, card_values, run_entry

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("RECALL_REVIEW_PROBES") != "1",
        reason="review probe: documents an unread question; run with RECALL_REVIEW_PROBES=1",
    ),
    pytest.mark.usefixtures("thread_sympy_executor"),
]


async def _verified(prompt: str) -> list[tuple[float, str]]:
    """The verified values the turn ships; empty when it declines."""
    outcome = await run_entry(
        Entry(id="probe", area="review", prompt=prompt, expect="explain"), "physics"
    )
    route = outcome.route
    if route is None or not route.solved:
        return []
    reply = route.instant_text or f"```answer\n{route.verified_answer}\n```"
    return [(value, unit) for value, unit, _shown in card_values(reply)]


def _first(values: list[tuple[float, str]]) -> float:
    assert values, "the turn declined: the defect is fixed"
    return abs(values[0][0])


# --- 1. a lost superscript: "1.5 x 103 kg" is read as 103 kg --------------------------------


async def test_unread_1_lost_superscript_mass() -> None:
    """``fold_scientific`` folds only "x 10^n" (services/number_text.py:153); the mantissa and
    "x" of the book's "1.5 x 103" are dropped and 103 kg is the mass. Right: 20 m/s."""
    got = await _verified("A 1.5 × 103 kg car has 300 kJ of kinetic energy. How fast is it moving?")
    assert math.isclose(_first(got), 76.3, rel_tol=0.01)


async def test_unread_1b_lost_superscript_temperature() -> None:
    """The same in a gas law: 3 x 102 K read as 102 K. Right: 5.33 L."""
    got = await _verified(
        "A gas at constant pressure occupies 4 L at 3 × 102 K. It is heated to 400 K. "
        "What is its new volume?"
    )
    assert math.isclose(_first(got), 15.7, rel_tol=0.01)


# --- 2. "average" unread: the final speed is answered -----------------------------------------


async def test_unread_2_average_speed_is_the_final_speed() -> None:
    """``_PHRASE_OP`` maps "speed" to ``suvat_velocity`` (extractors/suvat.py:102-104) and no
    reader looks at "average". Right: (10 + 30) / 2 = 20 m/s."""
    got = await _verified(
        "A car starts at 10 m/s and accelerates at 4 m/s^2 for 5 s. What is its average speed?"
    )
    assert math.isclose(_first(got), 30.0, rel_tol=0.01)


# --- 3. an operator on a given: "half of", "2 x" -----------------------------------------------


async def test_unread_3_half_of_a_height() -> None:
    """``has_unread_quantity`` (spelled.py:60) refuses a fraction word only beside a unit; "half
    of 20 m" passes and 20 m is the height. Right: 1.43 s."""
    got = await _verified(
        "A ball is dropped from half of 20 m. How long does it take to hit the ground?"
    )
    assert math.isclose(_first(got), 2.02, rel_tol=0.01)


async def test_unread_3b_a_product_given() -> None:
    """ "2 x 5 kg": no reader folds or refuses a product that is not a power of ten. Right: 2 m/s²."""
    got = await _verified(
        "A box of mass 2 × 5 kg is pushed with a net force of 20 N. What is its acceleration?"
    )
    assert math.isclose(_first(got), 4.0, rel_tol=0.01)


# --- 4. a negation unread ---------------------------------------------------------------------


async def test_unread_4_thrown_not_dropped() -> None:
    """ "thrown, not dropped": the fall is solved as a drop (v0 = 0, extractors/kinematics.py:217)
    though the speed of the throw is never given. Right: decline."""
    got = await _verified(
        "A ball is thrown, not dropped, from a 45 m tower. How long does it take to reach the ground?"
    )
    assert math.isclose(_first(got), 3.03, rel_tol=0.01)


# --- 5. a default filled for a missing value --------------------------------------------------


async def test_unread_5_thrown_down_with_no_speed() -> None:
    """ "thrown straight down" with no speed: v0 defaults to 0 (kinematics.py:217). Right: decline."""
    got = await _verified(
        "A ball is thrown straight down from a 30 m bridge. What is its speed when it hits the water?"
    )
    assert math.isclose(_first(got), 24.3, rel_tol=0.01)


async def test_unread_5b_one_current_is_the_whole_change() -> None:
    """ "falls to 500 mA": one value alone is the change (extractors/stated_change.py:102-103), so
    the current fell from 0. Right: decline (the starting current is not given)."""
    got = await _verified(
        "A 2 H inductor carries a current that falls to 500 mA in 0.1 s. What is the induced emf?"
    )
    assert math.isclose(_first(got), 10.0, rel_tol=0.01)


async def test_unread_5c_a_named_part_without_a_value() -> None:
    """A galvanometer is named and its resistance never given; the circuit is solved with the
    950 Ω alone. Right: decline, or the galvanometer's resistance asked for."""
    got = await _verified(
        "A galvanometer is connected in series with a 950 Ω resistor across 1 V. What current flows?"
    )
    assert math.isclose(_first(got), 0.00105, rel_tol=0.01)


# --- 6. a value of one kind read as another ----------------------------------------------------


async def test_unread_6_g_in_words_is_a_drop_height() -> None:
    """ "9.8 meters per second per second" is read as a 9.8 m height: the drop height is the first
    length in the text, no keyword needed (kinematics.py:205-214). Right: decline (no height)."""
    got = await _verified(
        "A ball is dropped. Take g = 9.8 meters per second per second. How long does it take to land?"
    )
    assert math.isclose(_first(got), 1.41, rel_tol=0.01)


# --- 7. a stated equivalence moves the turn to another law ------------------------------------


async def test_unread_7_equivalence_moves_the_law() -> None:
    """Without "(1 hour = 3600 s)" this is 8.33 m/s. With it, the average-speed reading has an
    unused time and is refused, and the catalog binder (extract.py, after the extractors) fits
    a free fall to "from rest" and 100 m: 44.3 m/s. Right: 8.33 m/s."""
    got = await _verified(
        "A sprinter starts from rest and covers 100 m in 12 s (1 hour = 3600 s). "
        "What is her average speed?"
    )
    assert math.isclose(_first(got), 44.3, rel_tol=0.01)


async def test_unread_7b_equivalence_flips_a_throw() -> None:
    """The same parenthesis turns "thrown vertically down at 12 m/s" into a throw upward
    (``_velocity_is_downward``, extractors/kinematics_asks.py:129, reads the direction by its
    place in the text). Right: 2.48 s."""
    got = await _verified(
        "A rock is thrown vertically down at 12 m/s from a 60 m bridge (1 hour = 3600 s). "
        "How long till it hits the water?"
    )
    assert math.isclose(_first(got), 4.93, rel_tol=0.01)


# --- 8. the ask read by a word list that wants "the" ------------------------------------------


async def test_unread_8_how_long_must_runway_be() -> None:
    """``_HOW_LONG_IS_LENGTH`` (ask.py:260-264) wants an article after "must"; without one "how
    long" is a time, and a length question gets 20 s. Right: 600 m."""
    got = await _verified(
        "A plane needs 60 m/s to take off and accelerates at 3 m/s^2 from rest. "
        "How long must runway be?"
    )
    assert got and got[0][1] == "s"
    assert math.isclose(_first(got), 20.0, rel_tol=0.01)


# --- 9. the question first, the setup after ---------------------------------------------------


async def test_unread_9_question_first_swaps_the_states() -> None:
    """Asked first, the gas's end state (127 °C) is read as its start and the 27 °C as its end.
    Right: 2 L x 400 K / 300 K = 2.67 L."""
    got = await _verified(
        "What volume will the gas have at 127 °C at constant pressure? "
        "A gas has a volume of 2 L at 27 °C."
    )
    assert math.isclose(_first(got), 1.5, rel_tol=0.01)


# --- 10. another body's value -----------------------------------------------------------------


async def test_unread_10_another_bodys_mass() -> None:
    """The first mass in the text is the electron's (extractors/quantum.py:160): a 3 kg ball's.
    Right: 7.27e-10 m."""
    got = await _verified(
        "A 3 kg ball and an electron both move at 1e6 m/s. "
        "What is the de Broglie wavelength of the electron?"
    )
    assert math.isclose(_first(got), 2.21e-40, rel_tol=0.01)


async def test_unread_10b_a_clock_time_bends_the_ray() -> None:
    """ "at 3 pm" beside the angle: the refraction reader (extractors/optics_laws.py:203) gives
    90°. Right: 19.5°."""
    got = await _verified(
        "A ray in air enters glass (n = 1.5) at 30° to the normal at 3 pm. "
        "What is the angle of refraction?"
    )
    assert math.isclose(_first(got), 90.0, rel_tol=0.01)


# --- 11. "initial" asked, the final answered ---------------------------------------------------


async def test_unread_11_initial_velocity_of_a_collision() -> None:
    """The collision reader (request.py:162, ``_collision_intent``) answers the joined final
    velocity whatever velocity is asked. Right: 4 m/s, stated in the question."""
    got = await _verified(
        "A 0.5 kg puck moving east at 4 m/s collides with a 0.3 kg puck moving west at 2 m/s. "
        "They stick together. What was the initial velocity of the first puck?"
    )
    assert math.isclose(_first(got), 1.75, rel_tol=0.01)
