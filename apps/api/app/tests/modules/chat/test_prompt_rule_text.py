"""The prompt's rules as one text: what the leak pass checks a reply against.

Structure ticket ST-04 moved the readers out of chat's prompt constants and the chemistry
fence hint into chemistry. Their words stay in the rules, so a reply that copies one is
still caught: the rule strings and the grams each one makes are held to their values
before the move. A change to the prompt's copy changes both; update them with it.
"""

from __future__ import annotations

import hashlib

from app.modules.chat.prompt_leaks import _grams
from app.modules.chat.prompt_rule_text import prompt_rule_text
from app.modules.chemistry.reply_policy import CHEMISTRY_FENCE_HINT

# Distinct rule strings and the 4-grams within each: before ST-04 (main e4c784a5a), then with
# the worked layout's Required heading and its Solve-for step, then with physics'
# PHYSICS_VELOCITY_NOTATION (initial and final velocity written v_i and v_f), then the
# ```worked block's contract (prompt_constants.worked), then the calculation layout's rule
# that multiplication is written \times, never a dot, then the formula headed by its name
# ("Average speed formula", never the name after the formula) and the Solution heading, then
# the ```worked contract asking for one `required` per part and each part's givens after its label,
# then one Given for a question in parts: every given first, a part's own lettered `given (a):`,
# then nothing after the block restating the answer its card shows, then the contract for a
# message that only states results to check (prompt_constants.worked.RESULT_CHECK_CONTRACT),
# then one note per memory command (remember, forget, mute, correct) from one template, in
# place of the remember note, then the assistant's name (ASSISTANT_NAME_RULE), then the lesson
# and teach-me shapes restated beside the message (prompt_constants.teaching LESSON_CONTRACT,
# TEACH_CONTRACT, OUTLINE_CONTRACT and the parts they share), then a quote card naming the
# person quoted and the reply's own writing never signed (FORMAT_CONTRACT, PROSE_WRITING_HINT),
# then an answer record's note kept to a label, an explanation in a sentence after the block,
# then owning a mistake on every turn and a number after a list naming its item
# (OWN_MISTAKE_HINT, UNCLEAR_MESSAGE_HINT), then a layout that follows what the reply holds
# (FORMAT_CONTRACT), a reply laid out to be scanned beside every message (READER_NOTE) and a
# fact the user adds checked against the chat (OWN_MISTAKE_HINT), then a follow-up that leaves
# out what it is about read as about the last reply (UNCLEAR_MESSAGE_HINT), then a checked
# answer redone from its unrounded values before it is given up (OWN_MISTAKE_HINT), then a
# reply that tells the truth (2026-11-06): no praise, knowledge note or recap
# (NO_SELF_TALK_RULE, NO_RECAP_NOTE), no excuse for a wrong figure (OWN_MISTAKE_HINT), drafts
# without invented details, earlier chats only when referred back to, no undated to-dos, and a
# missed reply re-explained, then no "live" part in a message of several requests: whether one
# needs the web is the reply model's call (multi_part), then every teach-me taught at once, one
# item per section (prompt_constants.teaching), then the person spoken to as "you", never
# about, and memory never quoted (NO_SELF_TALK_RULE), then a plan in weeks or months laid out
# by week or month, not by day (LEARNING_PLAN_HINT), then a **Choose A if** line only when the
# user asks to pick between named options, and no word about how the search went (READER_NOTE),
# then the chat's summary named as part of the conversation (SUMMARY_LEAD).
_RULES = 175
_RULE_GRAMS = 15966
_RULE_GRAMS_SHA = "c9fc1ba120307a35"


def _rules() -> list[str]:
    from app.modules.chat.prompt_rule_text import _rule_sources, _source_rules, _strings
    from app.modules.chat.prompt_subjects import SUBJECT_HINTS

    rules = [rule for source in _rule_sources() for rule in _source_rules(source)]
    for hints in SUBJECT_HINTS.values():
        for short in (False, True):
            rules += _strings(list(hints.presentation(short)))
        rules += _strings(hints.closing)
    return rules


def test_the_rule_text_is_the_rules_joined() -> None:
    assert "\n".join(_rules()) == prompt_rule_text()


def test_the_rules_and_their_grams_are_what_they_were() -> None:
    rules = set(_rules())
    grams = set().union(*(_grams(rule, 4) for rule in rules))
    digest = hashlib.sha256("\n".join(sorted(grams)).encode()).hexdigest()[:16]
    assert (len(rules), len(grams), digest) == (_RULES, _RULE_GRAMS, _RULE_GRAMS_SHA)


def test_the_chemistry_fence_hint_is_still_a_rule() -> None:
    assert CHEMISTRY_FENCE_HINT in prompt_rule_text()


def test_a_readers_word_list_is_still_a_rule() -> None:
    from app.modules.turn_reading.capabilities import _CAPABILITIES_EXACT

    text = prompt_rule_text()
    assert all(phrase in text for phrase in _CAPABILITIES_EXACT if len(phrase) >= 40)


def test_a_reply_copying_the_chemistry_fence_hint_loses_it() -> None:
    from app.modules.chat.prompt_leaks import _rule_grams, drop_prompt_leaks

    reply = (
        "Ethanol is CH3CH2OH.\n\n"
        "Use verified SMILES from the system block verbatim when present.\n\n"
        "Do not emit a molecule card unless this turn is actually about a chemical structure."
    )
    assert drop_prompt_leaks(reply, "what is ethanol?", rules=_rule_grams()) == (
        "Ethanol is CH3CH2OH.\n"
    )
