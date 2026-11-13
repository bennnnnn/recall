"""Questions labelled by whether the reply works a result out (``work_need_corpus.json``).

The Decider's ``work`` is measured with real calls (``work_need_eval``); this holds offline
that the set is whole, what the fallback (a number and a subject) does, and the measure.
"""

from __future__ import annotations

from app.tests.behavior.work_need_eval import Outcome, WorkTurn, load, rates, rules_work

TURNS = load()


def test_the_set_is_whole() -> None:
    ids = [turn.id for turn in TURNS]
    assert len(ids) == len(set(ids)), "turn ids repeat"
    assert len(TURNS) >= 100
    assert 0.4 <= sum(turn.work for turn in TURNS) / len(TURNS) <= 0.6
    assert any(turn.holdout for turn in TURNS)
    # Most of the questions that work nothing out have a number in them: the rules' miss.
    plain = [turn for turn in TURNS if not turn.work]
    assert sum(any(c.isdigit() for c in turn.prompt) for turn in plain) / len(plain) >= 0.75


def test_the_rules_lay_out_the_phrases_question() -> None:
    """Phone, 2026-11-13: what a turn falls back on with no read gives it a Given and a
    Required for its 7."""
    seven_x = next(
        turn for turn in TURNS if turn.prompt.startswith("Translate the algebraic expression 7x")
    )
    assert not seven_x.work
    assert rules_work(seven_x) is True


def test_the_measure_counts_recall_and_false_layouts() -> None:
    def outcome(work: bool, odds: list[float]) -> Outcome:
        return Outcome(WorkTurn(id="t", area="maths", work=work, prompt="p"), odds=odds)

    outcomes = [outcome(True, [0.9, 0.4]), outcome(False, [0.6, 0.1])]
    assert rates(outcomes, 0.5) == (0.5, 0.5)
