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


def test_a_brace_that_closes_nothing_leaves_the_record_out() -> None:
    assert read_record(r"substitution: v = \frac{20}}{2}") is None


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
    # A short label keeps its brackets.
    assert _laid_out("required: s | displacement", "answer: s | 2400 | m | east").endswith(
        r"$s = 2400\,\mathrm{m}$ (east)"
    )
