"""A worked answer's card shows its value by the one rule (``services.rounding_rule``).

phys30 (2026-11-16): "29.008 N" on a card. Review of the first fix: rounding from the
working rewrote exact values on every worked block ("6185 students" became 6190, "3 groups
of 40 from 130" became 3.25): a whole number stays whole, and nothing is ever replaced by the
working's value. The owner's standard (2026-11-18): two decimal places, zeros kept, at
least three figures, every subject.
"""

from __future__ import annotations

import re

import pytest

from app.modules.chat.worked_figures import card_answer
from app.modules.chat.worked_render import WorkedLayout, render_worked
from app.modules.chat.worked_solution import Answer, assemble, read_record


@pytest.mark.parametrize(
    ("value", "note", "card", "kept_note"),
    [
        ("29.008", "", "29.01", ""),
        ("5.488", "down", "5.49", "down"),
        ("2.4499", "to 4 s.f.", "2.45", ""),
        ("1.4142", "", "1.41", ""),
        # Two places, zeros kept; a whole number exact as written.
        ("3.2", "to 2 s.f.", "3.20", ""),
        ("3.24", "", "3.24", ""),
        ("4.8", "away from the wall", "4.80", "away from the wall"),
        ("96", "", "96", ""),
        ("4186", "", "4186", ""),
        ("65536", "", "65536", ""),
        ("6185", "", "6185", ""),
        # A carry into the next place (Gemini on #2489): the figure count holds.
        ("9.996", "", "10.00", ""),
        ("-9.996", "", "-10.00", ""),
        ("0.09996", "", "0.100", ""),
        ("0.0009996", "", "1.00 \\times 10^{-3}", ""),
        ("99.96", "", "99.96", ""),
        ("999.6", "", "999.60", ""),
    ],
)
def test_a_card_rounds_once_by_the_rule(
    value: str, note: str, card: str, kept_note: str
) -> None:
    out = card_answer(Answer(symbol="F", value=value, unit="N", note=note))
    assert (out.value, out.note) == (card, kept_note)


@pytest.mark.parametrize("value", ["\\frac{1}{2}", "9.79 \\times 10^{5}", "x + 2"])
def test_a_card_that_is_no_plain_decimal_stays(value: str) -> None:
    answer = Answer(symbol="v", value=value, unit="m/s")
    assert card_answer(answer) == answer


def _rendered(records: list[str], *, physics: bool) -> str:
    solution = assemble([record for line in records if (record := read_record(line)) is not None])
    return render_worked(solution, WorkedLayout(law_heading=physics))


@pytest.mark.parametrize(
    ("working", "answer", "shown"),
    [
        # The review's repros: exact values, floor and ceiling answers, money, a molar mass.
        ("n = 1237 \\times 5 = 6185", "n | 6185 | students", "6185"),
        ("y = 2026 + 5 = 2031", "y | 2031 |", "2031"),
        ("n = 2^{16} = 65536", "n | 65536 |", "65536"),
        ("E = 1 \\times 4186 \\times 1 = 4186", "E | 4186 | J", "4186"),
        ("C = 1234.56", "C | 1234.56 | dollars", "1234.56"),
        ("M = 180.156", "M | 180.156 | g/mol", "180.16"),
        ("g = \\frac{130}{40} = 3.25", "g | 3 | groups", "3"),
        ("p = \\frac{5}{2} = 2.5", "p | 2 | pieces", "2"),
        ("t = \\frac{20}{3} = 6.67", "t | 7 | trips", "7"),
    ],
)
def test_a_card_outside_physics_follows_the_rule_and_keeps_its_counts(working: str, answer: str, shown: str) -> None:
    text = _rendered([f"substitution: {working}", f"answer: {answer}"], physics=False)
    card = text.split("**Answer**")[-1]
    assert re.search(rf"(?<![\d.]){re.escape(shown)}(?![\d.])", card), card


def test_a_physics_card_never_takes_the_working_s_value() -> None:
    text = _rendered(
        ["substitution: T = 3.2439\\,\\mathrm{N}", "answer: T | 3.2 | N"], physics=True
    )
    assert "3.24" not in text.split("**Answer**")[-1]


@pytest.mark.parametrize("unit", ["$", "dollars", "USD", "€", "£", "cents", "\\$"])
def test_a_sum_of_money_is_never_rounded(unit: str) -> None:
    """Gemini on #2489: an electricity bill of $12.34 is exact to the cent."""
    answer = Answer(symbol="C", value="1234.56", unit=unit)
    assert card_answer(answer) == answer


@pytest.mark.parametrize(
    ("value", "unit", "card"),
    [("12.345", "kWh", "12.35"), ("29.008", "pounds", "29.01"), ("29.008", "lb", "29.01")],
)
def test_a_measured_quantity_still_rounds(value: str, unit: str, card: str) -> None:
    """Claude on #2489: "pounds" is a force or a mass in physics, rounded as one."""
    assert card_answer(Answer(symbol="F", value=value, unit=unit)).value == card


@pytest.mark.parametrize(
    ("question", "value", "card"),
    [
        ("Find the force, to 4 s.f.", "12.3456", "12.35"),
        ("Find the force, to 4 s.f.", "12.35", "12.35"),
        ("Find the force to 2 d.p.", "12.3456", "12.35"),
        ("Find the force to 2 decimal places.", "1.5", "1.50"),
        ("Find the force to the nearest tenth.", "29.008", "29.0"),
        ("Find the force.", "12.3456", "12.35"),
    ],
)
def test_a_card_keeps_the_precision_the_question_asks(question: str, value: str, card: str) -> None:
    """Claude on #2489: "to 4 s.f." came back to 3, its note dropped."""
    from app.services.school_rounding import asked_rounding

    figures, places, _ = asked_rounding(question)
    answer = Answer(symbol="F", value=value, unit="N", note="to 4 s.f.")
    out = card_answer(answer, (figures, places))
    assert out.value == card
    if figures or places >= 0:
        assert out.note == "to 4 s.f."


@pytest.mark.parametrize(
    ("question", "asked"),
    [
        ("Find the force to 3 s.f.", (3, -1)),
        ("Find the force to 3 sf", (3, -1)),
        ("Find the force to 3 S.F.", (3, -1)),
        ("Find the force to 2 d.p.", (0, 2)),
        # Gemini on #2489: a sentence's stop and a line break are no abbreviation's.
        ("The force acts from t = 0 to 1 s. F(t) = 5t^2 N. Find the impulse.", (0, -1)),
        ("The force acts from t = 0 to 1 s\nf = 5 N on the block.", (0, -1)),
    ],
)
def test_the_asked_precision_is_read_on_one_line(question: str, asked: tuple[int, int]) -> None:
    from app.services.school_rounding import asked_rounding

    figures, places, _ = asked_rounding(question)
    assert (figures, places) == asked


def test_a_precision_beyond_what_a_card_keeps_leaves_the_value() -> None:
    """Gemini on #2489: "to 30 d.p." asked Decimal for more digits than it holds."""
    answer = Answer(symbol="F", value="1.23456789", unit="N")
    assert card_answer(answer, (0, 30)) == answer
    assert card_answer(answer, (40, -1)) == answer
