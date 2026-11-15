"""A how-to's steps reach the phone as the flow card (``chat.steps_flow``).

"If I ask how to do something, I need to see a flow with arrows" (the owner, 2026-11-14); a
live "how do I make a budget" came back as a numbered list of bold labels instead.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.chat.prompt_constants import STEPS_FORMAT_HINT
from app.modules.chat.steps_flow import as_step_flow, hold_step_flow

_BUDGET = (
    "Start with what comes in.\n\n"
    "1. **Add up your income:** Use the take-home amount, not the gross.\n"
    "2. **List fixed costs:** Rent, utilities and loan repayments.\n"
    "3. **Set a savings goal** — move it out first.\n"
    "4. **Track it weekly.**\n\n"
    "A common rule is 50/30/20."
)
_BUDGET_CARD = (
    "Start with what comes in.\n\n```steps\n"
    "1. **Add up your income**\nUse the take-home amount, not the gross.\n"
    "2. **List fixed costs**\nRent, utilities and loan repayments.\n"
    "3. **Set a savings goal**\nmove it out first.\n"
    "4. **Track it weekly**\n```\n\nA common rule is 50/30/20."
)


def test_a_numbered_list_of_labelled_steps_becomes_the_card() -> None:
    assert as_step_flow(_BUDGET) == _BUDGET_CARD


def test_the_lines_under_an_item_stay_with_it_and_the_needs_list_stays_a_list() -> None:
    reply = (
        "You need:\n\n1. **Flour** 500 g\n2. **Water** 300 ml\n3. **Yeast** 7 g\n\n"
        "Then:\n\n1. **Mix** it all.\n2. **Knead**\n   until smooth.\n3. **Rise** for an hour."
    )
    out = as_step_flow(reply)
    assert out.startswith("You need:\n\n1. **Flour** 500 g\n")
    assert out.endswith(
        "Then:\n\n```steps\n1. **Mix**\nit all.\n2. **Knead**\nuntil smooth.\n"
        "3. **Rise**\nfor an hour.\n```"
    )


@pytest.mark.parametrize(
    "reply",
    [
        # Plain items, a list too short for a flow, bullets (the ways layout), a card already.
        "1. Mix the flour.\n2. Add water.\n3. Knead.",
        "1. **Mix** it.\n2. **Bake** it.",
        "- **Spend less** on food.\n- **Earn more** on the side.\n- **Automate** saving.",
        "```steps\n1. **Mix**\n2. **Bake**\n```\n\n1. **A** x\n2. **B** y\n3. **C** z",
        # One item without a label: no sequence the card can name.
        "1. **Mix** it.\n2. Bake it.\n3. **Cool** it.",
        # A list inside a fence is code, not steps.
        "```text\n1. **Mix** it.\n2. **Bake** it.\n3. **Cool** it.\n```",
    ],
    ids=["plain", "short", "ways", "card", "unlabelled item", "in a fence"],
)
def test_other_lists_stay_as_written(reply: str) -> None:
    assert as_step_flow(reply) == reply


def _state(text: str, *, asked: bool) -> Any:
    system = f"rules\n\n{STEPS_FORMAT_HINT}" if asked else "rules"
    return SimpleNamespace(
        text=text,
        server_text=False,
        was_cancelled=False,
        ctx=SimpleNamespace(prompt_messages=[{"role": "system", "content": system}]),
    )


def test_only_a_turn_that_asked_for_steps_gets_the_card() -> None:
    assert hold_step_flow(_state(_BUDGET, asked=True)) == _BUDGET_CARD
    # "Ways to save money" outside a how-to, a lesson's stages: as written.
    assert hold_step_flow(_state(_BUDGET, asked=False)) == _BUDGET
