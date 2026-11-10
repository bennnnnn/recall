"""Questions labelled by whether the answer must be reasoned out (``think_need_corpus.json``).

The read's ``think`` is measured with real model calls (``think_need_eval``); this holds
offline that the set is whole and what the fallback (the word rules) and the measure do.
"""

from __future__ import annotations

from app.tests.behavior.think_need_eval import Outcome, ThinkTurn, load, rates, rules_think

TURNS = load()


def test_the_set_is_whole() -> None:
    ids = [turn.id for turn in TURNS]
    assert len(ids) == len(set(ids)), "turn ids repeat"
    assert len(TURNS) >= 100
    hard = sum(turn.think for turn in TURNS)
    assert 0.35 <= hard / len(TURNS) <= 0.5
    assert any(turn.holdout for turn in TURNS)
    # The case that started it (2026-11-09): four runners, their speeds, a chart.
    assert any("Four runners" in turn.prompt and turn.think for turn in TURNS)


def test_the_word_rules_miss_the_runners_problem() -> None:
    """What a turn falls back on when the read gives no answer in time."""
    runners = next(turn for turn in TURNS if "Four runners" in turn.prompt and not turn.history)
    assert rules_think(runners) is False


def test_the_measure_counts_recall_false_thinking_and_precision() -> None:
    def outcome(think: bool, thought: list[bool]) -> Outcome:
        return Outcome(ThinkTurn(id="t", area="a", think=think, prompt="p"), thought=thought)

    outcomes = [outcome(True, [True]), outcome(True, [False]), outcome(False, [True])]
    assert rates(outcomes, 0) == (0.5, 1.0, 0.5)
