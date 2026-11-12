"""Replies labelled by whether they deny live facts (``live_denial_corpus.json``).

The check is measured with real model calls (``live_denial_eval``); this holds offline what
needs none: the set is whole, it holds the look-alikes a review named (a draft, a
translation, a package or messages the app cannot see, a quoted denial, a long answer that
mentions one, a travel answer that gives a Maps link in place of a time it cannot check), a
draft's words never reach the check, and the turns that are drafts or translations never
ask it.
"""

from __future__ import annotations

import pytest

from app.modules.chat.tool_loop import live_denial
from app.tests.behavior.live_denial_eval import Outcome, Reply, asked, load, rates

REPLIES = load()


def test_the_set_is_whole() -> None:
    ids = [reply.id for reply in REPLIES]
    assert len(ids) == len(set(ids)), "reply ids repeat"
    assert len(REPLIES) >= 60
    for group in ([r for r in REPLIES if not r.holdout], [r for r in REPLIES if r.holdout]):
        assert {reply.denies for reply in group} == {True, False}
    areas = {reply.area for reply in REPLIES if not reply.denies}
    assert {
        "drafts and translations",
        "the user's own things",
        "talk about denials",
        "long answer",
        "hedge or offer",
        # "Is it far?" answered "I can't check live traffic; here's the Maps link", as the
        # directions rule asks: no denial of public facts, and no search names the route.
        "the way to a place",
    } <= areas
    assert {"other languages", "looking it up now"} <= {r.area for r in REPLIES if r.denies}


@pytest.mark.parametrize("reply", [r for r in REPLIES if "```" in r.reply], ids=lambda r: r.id)
def test_a_fenced_draft_never_reaches_the_check(reply: Reply) -> None:
    """ "Text my coach: I can't check the live scores tonight." is the user's line."""
    from app.services.md_fence_scan import without_fences

    state = live_denial._quoted(reply.message, reply.reply)
    for line in reply.reply.split("```")[1].splitlines()[1:]:
        if line.strip():
            assert line.strip() not in state
    assert without_fences(reply.reply).strip()[:40] in state


@pytest.mark.parametrize(
    "reply", [r for r in REPLIES if r.area == "drafts and translations"], ids=lambda r: r.id
)
def test_a_draft_or_translation_turn_never_asks(reply: Reply) -> None:
    assert not asked(reply.message)


def test_plain_questions_ask() -> None:
    assert all(asked(r.message) for r in REPLIES if r.area != "drafts and translations")


def test_the_measure_counts_caught_and_retried() -> None:
    def outcome(denies: bool, retried: list[bool]) -> Outcome:
        reply = REPLIES[0]
        return Outcome(Reply(**{**reply.__dict__, "denies": denies}), retried=retried)

    outcomes = [outcome(True, [True, False]), outcome(False, [False, True])]
    assert rates(outcomes, 0) == (1, 1, 0, 1)
    assert rates(outcomes, 1) == (0, 1, 1, 1)
