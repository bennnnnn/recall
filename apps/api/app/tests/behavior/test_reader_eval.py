"""The model reader's measurement judges cards as the STEM sweep does (no model call here)."""

from __future__ import annotations

from app.tests.behavior.reader_eval import Row, _judge, _same_value
from app.tests.behavior.stem_sweep import Entry


def _entry(expect: str = "answer") -> Entry:
    return Entry(id="x", area="a", prompt="p", expect=expect, answers=((15.0, "m/s"),))


def test_a_card_with_the_worked_answer_is_right_and_another_is_wrong() -> None:
    row = Row("physics", "en", _entry())
    assert not _judge(row, "15\\ \\mathrm{m/s}")
    assert _judge(row, "12\\ \\mathrm{m/s}")
    assert not _judge(row, None)


def test_any_card_on_a_question_with_no_answer_is_wrong() -> None:
    assert _judge(Row("physics", "en", _entry("decline")), "15\\ \\mathrm{m/s}")


def test_two_cards_agree_on_their_value() -> None:
    assert _same_value("15\\ \\mathrm{m/s}", "15.0\\ \\mathrm{m/s}")
    assert not _same_value("15\\ \\mathrm{m/s}", "16\\ \\mathrm{m/s}")
