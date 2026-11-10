"""The turns that need a web search and the ones that don't (``search_need_corpus.json``).

Whether a turn searches is a model's call: the read beside the prep
(``web_search.live_read``), then the reply's own ``web_search`` call. ``search_need_eval``
measures both with real model calls; this holds offline what needs none: the set is whole,
each follow-up is read with what it refers to, and every turn of it leaves the search to
the model (the server forces none).
"""

from __future__ import annotations

import pytest

from app.modules.web_search import live_read
from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import route_case
from app.tests.behavior.search_need_eval import Outcome, Turn, load, rates, recent_rows

# The owner's chat (2026-11-09): six of its eleven turns searched, two needed it.
OWNER_CHAT = [
    ("Why is my computer gets hot", False),
    ("Does charging make computer hotter?", False),
    ("Macbook air", False),
    ("Who fixs it", False),
    ("Can i just buy another one", False),
    ("How to check battery health?", False),
    ("Can I replace the battery myself?", False),
    ("How much", True),
    ("Where is the nearest one", True),
    ("Can i wolk?", False),
    ("Current location", False),
]
TURNS = load()


def test_the_corpus_is_whole() -> None:
    ids = [turn.id for turn in TURNS]
    assert len(ids) == len(set(ids)), "turn ids repeat"
    tuned = [turn for turn in TURNS if not turn.holdout]
    held = [turn for turn in TURNS if turn.holdout]
    assert len(tuned) >= 100
    for group in (tuned, held):
        assert sum(turn.live for turn in group) >= len(group) * 0.4
        assert sum(not turn.live for turn in group) >= len(group) * 0.4
    for turn in TURNS:
        roles = [role for role, _text in turn.history]
        assert roles == ["user", "assistant"] * (len(roles) // 2), turn.id
        assert turn.prompt.strip() and turn.area, turn.id


def test_the_owners_chat_is_in_it_as_labelled() -> None:
    owner = [turn for turn in TURNS if turn.area == "owner chat"]
    assert [(turn.prompt, turn.live) for turn in owner] == OWNER_CHAT
    # Each turn follows the whole chat before it.
    assert [len(turn.history) for turn in owner] == list(range(0, 2 * len(OWNER_CHAT), 2))


@pytest.mark.parametrize("turn", [t for t in TURNS if t.history], ids=lambda t: t.id)
def test_a_follow_up_is_read_with_what_it_refers_to(turn: Turn) -> None:
    """A bare "How much" is a MacBook Air battery's cost only to a read that sees the chat."""
    quoted = live_read._messages(turn.prompt, live_read.earlier_turns(recent_rows(turn)))[-1]
    last_user = next(text for role, text in reversed(turn.history) if role == "user")
    assert last_user[:200] in quoted["content"]
    assert turn.history[-1][1][:200] in quoted["content"]
    assert quoted["content"].endswith(f"The user's last message: {turn.prompt}")


@pytest.mark.asyncio
@pytest.mark.parametrize("turn", TURNS, ids=lambda t: t.id)
async def test_the_turn_leaves_the_search_to_the_model(
    turn: Turn, thread_sympy_executor: None
) -> None:
    route = await route_case(
        Case(
            turn.id,
            "web search",
            turn.prompt,
            Expect(),
            "",
            history=turn.history,
            location=turn.location,
            locale=turn.locale,
        )
    )
    if turn.live:
        # The model is offered the tool (or the server searched what it works out itself).
        assert route.search in {"ask", "yes"}, route.summary()
    else:
        assert route.search != "yes", route.summary()


def test_the_measure_counts_false_searches_and_recall() -> None:
    def outcome(live: bool, searched: list[bool]) -> Outcome:
        return Outcome(Turn(id="t", area="a", live=live, prompt="p"), searched=searched)

    outcomes = [
        outcome(True, [True, False]),
        outcome(True, [True, True]),
        outcome(False, [False, True]),
        outcome(False, [False, False]),
    ]
    assert rates(outcomes, 0) == (0.0, 1.0)
    assert rates(outcomes, 1) == (0.5, 0.5)
