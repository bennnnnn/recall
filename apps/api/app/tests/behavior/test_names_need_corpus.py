"""Questions labelled by whether their answer recommends named things to look up
(``names_need_corpus``).

The Decider's ``names`` is measured with real calls (``names_need_eval``); this holds offline
that the set is whole, that no word rule picks the links, and the measure.
"""

from __future__ import annotations

from app.modules.chat.prompt_constants.format import NAME_LINK_NOTE
from app.modules.chat.prompt_format import _style_format_hints
from app.tests.behavior.names_need_eval import NamesTurn, Outcome, load, rates

TURNS = load()


def test_the_set_is_whole() -> None:
    ids = [turn.id for turn in TURNS]
    assert len(ids) == len(set(ids)), "turn ids repeat"
    assert len(TURNS) >= 60
    for group in ([t for t in TURNS if not t.holdout], [t for t in TURNS if t.holdout]):
        assert sum(turn.names for turn in group) >= len(group) / 3
        assert sum(not turn.names for turn in group) >= len(group) / 3


def test_the_words_of_a_near_me_ask_pick_no_layout() -> None:
    """Only "near me" got tappable names, from a word rule (the owner, 2026-11-27)."""
    near = next(turn for turn in TURNS if turn.prompt == "coffee shops near me")
    hints = _style_format_hints(
        query_text=near.prompt, is_day_plan=False, minimal_personal_context=False
    )
    assert NAME_LINK_NOTE not in hints


def test_the_measure_counts_links_on_picks_and_on_the_rest() -> None:
    def outcome(names: bool, odds: list[float]) -> Outcome:
        return Outcome(NamesTurn(id="t", names=names, prompt="p"), odds=odds)

    outcomes = [outcome(True, [0.9, 0.4]), outcome(False, [0.7, 0.1])]
    assert rates(outcomes, 0.5) == (0.5, 0.5)
