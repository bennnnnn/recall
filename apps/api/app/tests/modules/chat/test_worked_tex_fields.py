"""Every maths field of a ```worked block reaches the layout as TeX the phone draws, and an
answer of a vector, of two values or with a direction keeps its card (the owner's chat,
2026-11-20: two cars colliding at right angles)."""

from __future__ import annotations

from app.modules.chat.worked_render import WorkedLayout, render_worked
from app.modules.chat.worked_solution import Answer, Required, assemble, read_record
from app.tests.behavior.latex_check import latex_problems

# The owner's answer (a): its brace never closed, so the unit and the note went into the value.
_TWO_VECTORS = (
    r"answer: v_A, v_B | (0\hat{i} + 20\hat{j})\ \mathrm{m/s},\ (-16\hat{i} + 0\hat{j})\ "
    r"\mathrm{m/s | m/s | \hat{i} east, \hat{j} north"
)


def _laid_out(*lines: str) -> str:
    records = [record for record in map(read_record, lines) if record is not None]
    return render_worked(assemble(records), WorkedLayout())


def test_an_open_group_splits_no_fields() -> None:
    record = read_record(_TWO_VECTORS)
    assert record == Answer(
        symbol="v_A, v_B",
        value=r"(0\hat{i} + 20\hat{j})\ \mathrm{m/s},\ (-16\hat{i} + 0\hat{j})\ \mathrm{m/s}",
        unit="m/s",
        note=r"\hat{i} east, \hat{j} north",
    )


def test_a_bar_inside_a_closed_group_is_the_maths() -> None:
    record = read_record(r"answer: P | P(A|B) = 0.3 |")
    assert isinstance(record, Answer) and record.value == "P(A|B) = 0.3"


def test_a_double_subscript_is_set_on_its_base() -> None:
    assert read_record(r"required: v_A_{vec}, v_B_{vec} | velocities") == Required(
        symbol="{v_A}_{vec}, {v_B}_{vec}", meaning="velocities"
    )


def test_a_stray_closing_brace_keeps_the_record() -> None:
    """Review: refused for it, ``\\frac{1}{2}}`` lost the reply's card."""
    record = read_record(r"answer: x | \frac{1}{2}} |")
    assert isinstance(record, Answer) and record.value == r"\frac{1}{2}"


def test_an_evaluation_bar_is_the_maths() -> None:
    record = read_record(r"step: \left. x^2 \right|_0^1 = 1 | evaluate")
    assert record is not None and getattr(record, "move", "") == "evaluate"


def test_a_thousands_comma_is_one_value() -> None:
    assert _laid_out("required: a | x", "answer: a, b | 1,000 | m").endswith(
        r"$a, b = 1,000\,\mathrm{m}$"
    )


def test_a_thin_space_is_no_second_value() -> None:
    """Claude on #2509: ``3\\,\\mathrm{m/s}`` split at the comma of its thin space."""
    reply = _laid_out("required: a | x", r"answer: a, b | 3\,\mathrm{m/s} |")
    assert reply.endswith(r"$a, b = 3\,\mathrm{m/s}$")


def test_a_power_of_ten_and_a_range_take_no_brackets() -> None:
    assert _laid_out("required: I | current", "answer: I | 1.5e-3 | A").endswith(
        r"$I = 1.5e-3\,\mathrm{A}$"
    )
    assert "(20 - 25)" not in _laid_out("required: T | range", "answer: T | 20 - 25 | °C")


def test_two_values_in_one_record_are_two_answers() -> None:
    reply = _laid_out("required: v_A | velocity of car A", "required: v_B | of car B", _TWO_VECTORS)
    assert r"$v_A = (0\hat{i} + 20\hat{j})\ \mathrm{m/s}$" in reply
    assert r"$v_B = (-16\hat{i} + 0\hat{j})\ \mathrm{m/s}$" in reply
    assert r"\mathrm{m/s}\,\mathrm{m/s}" not in reply  # the unit the value writes, once
    assert latex_problems(reply) == []


def test_a_vector_takes_its_unit_after_its_components() -> None:
    reply = _laid_out("required: v | velocity", r"answer: \vec{v} | -16\hat{i} + 20\hat{j} | m/s")
    assert reply.endswith(r"$\vec{v} = (-16\hat{i} + 20\hat{j})\,\mathrm{m/s}$")


def test_a_direction_by_its_angle_stays_on_the_card() -> None:
    reply = _laid_out(
        "required: v_f | velocity after the collision",
        r"substitution: v_f = 12.4964\,\mathrm{m/s}",
        "answer: v_f | 12.4964 | m/s | 39.8° north of west (bearing 320.2°)",
    )
    assert reply.endswith(r"$v_f = 12.50\,\mathrm{m/s}$, 39.8° north of west (bearing 320.2°)")
    # A short label keeps its brackets, one that only starts with a number too.
    assert _laid_out("required: s | displacement", "answer: s | 2400 | m | east").endswith(
        r"$s = 2400\,\mathrm{m}$ (east)"
    )
    assert _laid_out("required: k | stiffness", "answer: k | 2.5 | N/m | 1st spring").endswith(
        r"$k = 2.50\,\mathrm{N/m}$ (1st spring)"
    )


def test_a_speed_and_its_angle_share_one_card() -> None:
    """Live (2026-11-20): the speed stayed above Answer (b) as working, and the angle's card
    ended "North of west |"."""
    from app.services.answer_fence import land_answer_card

    reply = land_answer_card(
        _laid_out(
            "required: v_f, \\theta | speed and direction",
            "substitution: v_f = \\sqrt{158.06}",
            "answer: v_f | 12.6 | m/s",
            "answer: \\theta | 45^\\circ | | North of west |",
        ),
        None,
    )
    assert reply.endswith(
        "verified: false\n$v_f = 12.60\\,\\mathrm{m/s}$, $\\theta = 45^\\circ$ (North of west)\n```"
    )


def test_a_symbol_braced_twice_by_the_layout_keeps_one_subscript() -> None:
    from app.modules.chat.worked_text import tidy_tex

    assert tidy_tex("v_Ai_mag") == "{v_{Ai}}_{mag}"


def test_a_closing_absolute_value_bar_stays() -> None:
    """Claude on #2509: the trailing-bar rule took the bar that closes | x_2 - x_1 |."""
    record = read_record("substitution: d = | x_2 - x_1 |")
    assert record is not None and getattr(record, "tex", "") == "d = | x_2 - x_1 |"


def test_a_vector_in_sized_brackets_is_one_value() -> None:
    """Codex on #2509: \\left( … \\right) around the components."""
    from app.services.final_value import is_final_value

    assert is_final_value(r"v_A = \left(0\hat{i} + 20\hat{j}\right)\,\mathrm{m/s}")
    assert not is_final_value(r"y = \left(x + 1\right)")
