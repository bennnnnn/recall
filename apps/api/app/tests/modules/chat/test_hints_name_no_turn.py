"""A prompt hint says what to write, never what kind of turn it is.

Told "This is a how-to task", the reply to "How to look handsome" opened "It's a how-to" (the
owner, 2026-11-27); told "This is a physics problem", a reply opened "This is a physics
question". A model repeats the label it is given, so no hint labels the message or calls it
"this turn" (the prompt's word, never the user's). Read here:

- every rule constant (``prompt_rule_text``, the subjects' presentation, closing and worked
  hints), the money card's rules and the subjects' follow-up hints;
- the hints functions build (a draft's revision, the day's reflection);
- the system messages of every battery turn's real prompt (``test_battery`` asks
  ``prompt_labels`` of each), where the per-turn notes are.

A quoted example of a label ("This is a … question", in the rule against labelling) is none.
"""

from __future__ import annotations

import re

from app.modules.chat.prompt_constants.writing import draft_followup_hint
from app.modules.chat.prompt_format import _DAY_REFLECTION_HINT
from app.modules.chemistry.followup import CHEMISTRY_FOLLOWUP_HINT
from app.modules.math.followup import MATH_FOLLOWUP_HINT
from app.modules.money import block as money_block
from app.modules.physics.followup import PHYSICS_FOLLOWUP_HINT
from app.tests.modules.chat.test_prompt_rule_text import _rules

# A sentence that names the turn's kind, or calls the message "this turn" or "this short
# request", outside quotes and brackets.
_LABEL = re.compile(
    r"(?<![\"“(\'])\b(?:This is an?|This turn\b|This short request\b|This message is an?"
    r"|This question is an?|It(?:'|’)s an?|It is an?) ?",
)


def prompt_labels(text: str) -> list[str]:
    """Each label ``text`` gives the turn, with a little of what is around it."""
    return [text[max(0, m.start() - 40) : m.end() + 40] for m in _LABEL.finditer(text)]


def _money_rules() -> list[str]:
    return [
        value
        for name, value in vars(money_block).items()
        if name.isupper() and isinstance(value, str)
    ]


def _built_hints() -> list[str]:
    return [
        draft_followup_hint("email", drafted=True),
        draft_followup_hint("email", drafted=False),
        _DAY_REFLECTION_HINT,
        MATH_FOLLOWUP_HINT,
        PHYSICS_FOLLOWUP_HINT,
        CHEMISTRY_FOLLOWUP_HINT,
    ]


def test_no_rule_names_the_kind_of_turn() -> None:
    texts = [*_rules(), *_money_rules(), *_built_hints()]
    assert [label for text in texts for label in prompt_labels(text)] == []


def test_the_check_finds_a_label_and_passes_a_quoted_one() -> None:
    assert prompt_labels("This is a how-to task. Under the short answer…")
    assert prompt_labels("Physics answers:\n  - This is a physics problem. Do not…")
    assert prompt_labels("This turn changes the draft you wrote earlier.")
    assert prompt_labels("This short request continues the preceding physics problem.")
    assert not prompt_labels('Never label the message ("This is a … question").')
