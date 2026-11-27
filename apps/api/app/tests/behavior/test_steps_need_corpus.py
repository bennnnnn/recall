"""Questions labelled by whether their answer is one procedure done in order (``steps_need_corpus``).

The Decider's ``steps`` is measured with real calls (``steps_need_eval``); this holds offline
that the set is whole, that its words no longer pick the card, and the measure.
"""

from __future__ import annotations

from app.modules.chat.prompt_constants.format import STEPS_FORMAT_HINT
from app.modules.chat.prompt_format import _style_format_hints
from app.tests.behavior.steps_need_eval import Outcome, StepsTurn, load, rates

TURNS = load()


def test_the_set_is_whole() -> None:
    ids = [turn.id for turn in TURNS]
    assert len(ids) == len(set(ids)), "turn ids repeat"
    assert len(TURNS) >= 60
    for group in ([t for t in TURNS if not t.holdout], [t for t in TURNS if t.holdout]):
        assert sum(turn.steps for turn in group) >= len(group) / 3
        assert sum(not turn.steps for turn in group) >= len(group) / 3


def test_the_words_of_a_plain_how_to_pick_no_card() -> None:
    """The owner's chat, 2026-11-27: "How to look handsome" got its tips in the card."""
    handsome = next(turn for turn in TURNS if turn.prompt == "How to look handsome")
    assert not handsome.steps
    hints = _style_format_hints(
        query_text=handsome.prompt, is_day_plan=False, minimal_personal_context=False
    )
    assert STEPS_FORMAT_HINT not in hints


def test_the_measure_counts_cards_on_procedures_and_on_tips() -> None:
    def outcome(steps: bool, odds: list[float]) -> Outcome:
        return Outcome(StepsTurn(id="t", steps=steps, prompt="p"), odds=odds)

    outcomes = [outcome(True, [0.9, 0.4]), outcome(False, [0.7, 0.1])]
    assert rates(outcomes, 0.6) == (0.5, 0.5)
