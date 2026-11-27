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

import importlib
import re

from app.modules.chat.prompt_constants.writing import draft_followup_hint
from app.modules.chat.prompt_format import _DAY_REFLECTION_HINT
from app.modules.chemistry.followup import CHEMISTRY_FOLLOWUP_HINT
from app.modules.math.followup import MATH_FOLLOWUP_HINT
from app.modules.money import block as money_block
from app.modules.physics.followup import PHYSICS_FOLLOWUP_HINT
from app.services.prompt_safety import strip_untrusted_blocks, wrap_saved_memory
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


# A sentence whose subject is the person or their message, said as a fact about this turn
# ("They want more of what you were saying.", "The user is correcting something…"): told so,
# free-chat opened "The user asks what Bahir Dar has, a follow-up to the size question, so I
# give new points, not a recap." (2026-11-27). Every rule is an instruction to the writer.
_DESCRIBES = re.compile(
    r"(?:^|(?<=[.!?:]\s)|(?<=\n))\s*(?:The user(?:'s)? |They |This message |The message "
    r"|It asks |This asks\b|This (?:turn|request|question) (?:is|asks|writes|changes|says)"
    r"|The person |The (?:learner|student) (?:is|wants|asks))"
)
# Prompt copy outside chat's prompt constants and the subjects' hints, which ``_rules`` reads:
# maths' tool notes, the search and place notes, memory's notes (review of #2610).
_MORE_PROMPT_MODULES = (
    "app.modules.math.tools.prompt",
    "app.modules.math.tools.bare_answer",
    "app.modules.web_search.formatting",
    "app.modules.chat.prompt_memory",
    "app.modules.chat.json_output",
)


def prompt_descriptions(text: str) -> list[str]:
    """Each sentence of ``text`` that describes the user or the message, outside the user's
    own wrapped content (memory, a summary, a file)."""
    prose = strip_untrusted_blocks(text)
    return [prose[m.start() : m.end() + 60] for m in _DESCRIBES.finditer(prose)]


def _strings(value: object) -> list[str]:
    """Every string in a constant: itself, or the strings a dict, tuple or list of them holds."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, tuple | list):
        return [text for item in value for text in _strings(item)]
    return []


def _module_rules() -> list[str]:
    """The constants of those modules, dicts of copy included, and the memory-command notes
    built from one (review of #2610: a dict and a builder escaped the scan)."""
    from app.modules.chat.prompt_memory import _MEMORY_COMMAND_DOES, _memory_command_note

    texts: list[str] = [_memory_command_note(command) for command in _MEMORY_COMMAND_DOES]
    for name in _MORE_PROMPT_MODULES:
        for key, value in vars(importlib.import_module(name)).items():
            if key.lstrip("_").isupper():
                texts += [text for text in _strings(value) if len(text) >= 40]
    return texts


def test_no_rule_describes_the_user_or_the_message() -> None:
    texts = [*_rules(), *_money_rules(), *_built_hints(), *_module_rules()]
    assert [found for text in texts for found in prompt_descriptions(text)] == []


def test_the_check_finds_a_description_and_passes_an_instruction() -> None:
    assert prompt_descriptions("They want more of what you were saying. Go on.")
    assert prompt_descriptions("Note. The user is correcting something you said.")
    assert prompt_descriptions("This message follows up your reply.")
    assert prompt_descriptions("This asks for the best picks.")
    assert not prompt_descriptions("Go on with what your replies have not covered yet.")
    assert not prompt_descriptions("When they sound frustrated, answer the feeling first.")
    assert not prompt_descriptions(wrap_saved_memory("The user prefers short replies."))
