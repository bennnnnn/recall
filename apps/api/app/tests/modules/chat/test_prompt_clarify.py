"""Which turns may ask with a clarify card: open questions, not a set shape."""

from __future__ import annotations

import pytest

from app.modules.chat.prompt_constants import (
    CLARIFICATION_HINT,
    CLARIFY_CARD_HINT,
    COMPARISON_FORMAT_HINT,
)
from app.modules.chat.prompt_format import _style_format_hints


def _hints(query: str, *, multi: bool = False) -> list[str]:
    return _style_format_hints(
        query_text=query,
        is_day_plan=False,
        minimal_personal_context=False,
        multi=multi,
    )


@pytest.mark.parametrize(
    "query",
    [
        "how can I understand integrals",
        "What is the best country",
        "which laptop should I buy",
        "plan my week",
        "help me understand recursion",
    ],
)
def test_an_open_question_may_ask_with_a_card(query: str) -> None:
    hints = _hints(query)
    assert CLARIFY_CARD_HINT in hints
    assert CLARIFICATION_HINT in hints


@pytest.mark.parametrize(
    "query",
    [
        # A problem, a lesson, a draft with its purpose, pasted code.
        "solve 2x + 5 = 17",
        "teach me python",
        "write an email to my landlord asking him to fix the heating",
        "why does this fail?\n```python\nprint(1/0)\n```",
    ],
)
def test_a_turn_with_its_own_shape_does_not_ask(query: str) -> None:
    assert CLARIFY_CARD_HINT not in _hints(query)


def test_a_multi_part_message_does_not_ask() -> None:
    assert CLARIFY_CARD_HINT not in _hints("plan my week and tell me a joke", multi=True)


_CARD_REPLY = (
    "**But let me ask you one thing.**\n\nWhat do you mean by *best*?\n\n```clarify\n"
    '{"request":"Recommend the best country for me.","questions":[{"id":"priority",'
    '"label":"Main priority","question":"What matters most to you?","options":'
    '["💰 Making money","🌿 Quality of life"]},{"id":"region","label":"Geographic preference",'
    '"question":"Which region are you considering?","options":["🌍 Anywhere","🇪🇺 Europe"]}],'
    '"closing":"Compare the strongest options with practical pros and cons.",'
    '"submit":"Find my best country"}\n```'
)
_AFTER_CARD = [("user", "What is the best country"), ("assistant", _CARD_REPLY)]
_PICKS = (
    "Recommend the best country for me. Main priority: Making money. Geographic preference: "
    "Anywhere. Compare the strongest options with practical pros and cons."
)


def test_the_picks_get_the_answer_not_another_card() -> None:
    hints = _style_format_hints(
        query_text=_PICKS,
        is_day_plan=False,
        minimal_personal_context=False,
        prior_messages=_AFTER_CARD,
    )
    assert CLARIFY_CARD_HINT not in hints
    # The reply opens with its recommendation: the card's "compare ... pros and cons" is
    # not an X-vs-Y turn that leads with a table.
    assert COMPARISON_FORMAT_HINT not in hints


def test_a_new_question_typed_after_a_card_may_still_ask() -> None:
    hints = _style_format_hints(
        query_text="which laptop should I buy",
        is_day_plan=False,
        minimal_personal_context=False,
        prior_messages=_AFTER_CARD,
    )
    assert CLARIFY_CARD_HINT in hints


def test_the_same_words_without_a_card_still_compare() -> None:
    hints = _style_format_hints(
        query_text=_PICKS, is_day_plan=False, minimal_personal_context=False
    )
    assert COMPARISON_FORMAT_HINT in hints
