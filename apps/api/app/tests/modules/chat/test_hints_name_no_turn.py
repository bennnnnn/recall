"""A prompt hint says what to write, never what kind of turn it is.

Told "This is a how-to task", the reply to "How to look handsome" opened "It's a how-to" (the
owner, 2026-11-27); told "This is a physics problem", a reply opened "This is a physics
question". A model repeats the label it is given, so no rule labels the message: every rule
the prompt can send (``prompt_rule_text``, the subjects' hints included) and the money card's
rules are read here, and a quoted example of a label ("This is a … question", in the rule
against labelling) is no label.
"""

from __future__ import annotations

import re

from app.modules.money import block as money_block
from app.tests.modules.chat.test_prompt_rule_text import _rules

# A sentence that names the turn's kind, not inside quotes or brackets.
_LABEL = re.compile(
    r"(?<![\"“(\'])\b(?:This is an?|This turn (?:is|asks|asked|names)|This message is an?"
    r"|This question is an?|It(?:'|’)s an?|It is an?) ",
)


def _money_rules() -> list[str]:
    return [
        value
        for name, value in vars(money_block).items()
        if name.isupper() and isinstance(value, str)
    ]


def _labels(texts: list[str]) -> list[str]:
    return [
        text[max(0, m.start() - 40) : m.end() + 40] for text in texts for m in _LABEL.finditer(text)
    ]


def test_no_rule_names_the_kind_of_turn() -> None:
    assert _labels([*_rules(), *_money_rules()]) == []


def test_the_check_finds_a_label_and_passes_a_quoted_one() -> None:
    assert _labels(["This is a how-to task. Under the short answer…"])
    assert _labels(["Physics answers:\n  - This is a physics problem. Do not…"])
    assert not _labels(['Never label the message ("This is a … question").'])
