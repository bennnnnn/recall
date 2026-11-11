"""Turns labelled by how Auto should handle them (``decider_corpus.json``).

The read is measured with real model calls (``decider_eval``); this holds offline that the
set is whole, its labels are choices the read can give, and what the measure counts.
"""

from __future__ import annotations

from typing import get_args

from app.modules.chat.turn_decision import Effort, Follow, Picture, Subject
from app.tests.behavior.decider_eval import FIELDS, load, right, thinks

TURNS = load()
_CHOICES = {
    "subject": set(get_args(Subject)),
    "effort": set(get_args(Effort)),
    "picture": set(get_args(Picture)),
    "follow": set(get_args(Follow)),
}
# The check-up turns the routing failed on (2026-11-10), each held in the set.
_CHECKUP_FAILURES = (
    "P16.1", "M13.1", "M17.1", "C19.1", "C17.1", "P09.2", "P19.1", "M05.2", "P21.2", "C03.2",
    "C14.2", "M25.2", "P06.2", "C09.1", "C16.2", "M20.1", "P03.2", "M15.2", "E21.1", "E30.1",
)  # fmt: skip


def test_the_set_is_whole() -> None:
    ids = [turn.id for turn in TURNS]
    assert len(ids) == len(set(ids)), "turn ids repeat"
    assert len(TURNS) >= 300
    assert {turn.source for turn in TURNS} == {"checkup", "battery", "think_need_corpus", "new"}
    for turn_id in _CHECKUP_FAILURES:
        assert f"checkup-{turn_id}" in ids


def test_every_label_is_a_choice_the_read_can_give() -> None:
    for turn in TURNS:
        for name in FIELDS:
            assert set(turn.labels[name].split("|")) <= _CHOICES[name], (turn.id, name)


def test_a_message_with_nothing_before_it_follows_nothing() -> None:
    """The read is told so, and the server holds it (``turn_decision``)."""
    for turn in TURNS:
        if not turn.history:
            assert turn.labels["follow"] == "none", turn.id


def test_other_languages_are_in_the_set() -> None:
    prompts = " ".join(turn.prompt for turn in TURNS)
    assert "ፍታልኝ" in prompts and "¿" in prompts and "Dessine" in prompts


def test_the_measure_takes_either_answer_of_a_borderline_label() -> None:
    assert right("none|low", "low") and right("none|low", "none")
    assert not right("none", "low") and not right("none", None)
    assert thinks("none|low") == {False, True}
    assert thinks("high") == {True}
