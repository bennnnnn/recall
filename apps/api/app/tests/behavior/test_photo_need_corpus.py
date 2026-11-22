"""Questions labelled by whether their answer earns a photo above it (``photo_need_corpus.json``).

The Decider's ``seen`` is measured with real calls (``photo_need_eval``); this holds offline
that the set is whole, what the word rule it replaces does, and the measure.
"""

from __future__ import annotations

from app.tests.behavior.photo_need_eval import Outcome, PhotoTurn, load, rates, rules_photo

TURNS = load()


def test_the_set_is_whole() -> None:
    ids = [turn.id for turn in TURNS]
    assert len(ids) == len(set(ids)), "turn ids repeat"
    assert len(TURNS) >= 60
    for group in ([t for t in TURNS if not t.holdout], [t for t in TURNS if t.holdout]):
        assert sum(turn.photo for turn in group) >= len(group) / 3
        assert sum(not turn.photo for turn in group) >= len(group) / 3


def test_the_word_rule_named_ur_name_as_the_thing_to_see() -> None:
    """The owner's chat, 2026-11-22: a photo above "My name is Recall"."""
    name = next(turn for turn in TURNS if turn.prompt == "What is ur name")
    assert not name.photo
    assert rules_photo(name) is True


def test_the_measure_counts_recall_and_false_photos() -> None:
    def outcome(photo: bool, odds: list[float]) -> Outcome:
        return Outcome(PhotoTurn(id="t", photo=photo, prompt="p"), odds=odds)

    outcomes = [outcome(True, [0.9, 0.4]), outcome(False, [0.6, 0.1])]
    assert rates(outcomes, 0.5) == (0.5, 0.5)
