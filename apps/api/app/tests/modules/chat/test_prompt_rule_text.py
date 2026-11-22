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
# then the chat's summary named as part of the conversation (SUMMARY_LEAD), then maths' pack
# saying a shape is never drawn by the model, and so when the app draws none, while code,
# SVG, HTML or ASCII art the user asks for is theirs (GRAPH_NO_SUBSTITUTE_CLAUSE), then physics'
# letters as a school textbook writes them (PHYSICS_SYMBOLS: v_i and v_f, s and d, E_k), then
# a formula with no name under **Solution**, never a bare **Formula** (2026-11-11), then
# a short message read with the conversation that fills it in and a reply to the assistant's
# own question taken as its answer (UNCLEAR_MESSAGE_HINT, CONFIRMED_HINT, and FOLLOW_NOTES
# beside a message the turn's read calls an answer or a change), and no claim that the app
# cannot look public facts up unless search is off, by the user or the server
# (FACT_GROUNDING_HINT, WEB_SEARCH_OFF_HINT, SEARCH_UNAVAILABLE_HINT), and a reply's second
# call told it can, after the first said it couldn't (DENIAL_RETRY_NOTE), then maths' pack
# saying the app draws the graph, number line or figure a maths question asks to see, so the
# model never says it cannot draw, never gives sketching steps and never draws a number line
# in characters (GRAPH_NO_SUBSTITUTE_CLAUSE, the textbook run 2026-11-13), then a given that
# carries no part's letter but where one symbol has a value per part, in the layout a model
# writes (services/workout._GIVEN_ONCE) and in a ```worked block's records, then a lesson's
# shape that follows what it teaches (a language's words, a concept, a process as a ```steps
# card), its practice an unnumbered `### Your turn`, the next lesson's contract and the grading
# of a card's answer (prompt_constants.teaching, lesson_flow, practice), and a how-to's steps
# as the ```steps flow card (STEPS_FORMAT_HINT), the owner's chat 2026-11-14; then the cards
# a chat already showed listed whole and a card's answer graded by the server (practice), the
# steps card restated beside a how-to's message (STEPS_CONTRACT), READER_NOTE's numbered list
# yielding to it, and a yes to another offer after a lesson's card done, beside the message
# when the read says it is one (LESSON_ASIDE_NOTE) (review, 2026-11-14); then a pick after
# a question offering choices taken among them, the list above it the other reading
# (prompt_constants.list_reference, UNCLEAR_MESSAGE_HINT); then a card's verdict naming the
# option by its words, and one answer to several cards asked about first (QUIZ_WHICH_NOTE)
# (review, 2026-11-14); then options lettered "A) …", an ordinary personal request helped, a
# frightening turn met plainly with no weapon use told and a retraction never dropping talk of
# self-harm, and "how" after a reply about something to do read as how to do it
# (OPTION_LETTERS_RULE, prompt_constants.care, REPLY_HOW_HINT); then maths' contract asking a
# reply to describe the picture a maths question asks to see in a ```draw block, the one
# exception to its never-draw rule (math.drawing.contract.DRAW_CONTRACT, 2026-11-15), its
# graphs too (the "plot" items: curves, tangents, asymptotes, shading, rectangles, slices);
# then a picture asked beside a solved problem left to the solve, and no reply placing or
# promising a picture (multi_part.PROBLEM_PICTURE_NOTE, services.picture_copy), and a
# ```worked block naming the language of its reply first (prompt_constants.worked, live and
# review 2026-11-15); then a ```worked measured answer to 3 significant figures and a yes-or-no
# part answered in words (prompt_constants.worked, phys30 2026-11-16); then maths' reply
# policy writing its working once, never a recheck or a second attempt (math.reply_policy,
# unit-5 round 2026-11-16); the solid a shaded region sweeps (the "solid" item, 2026-11-16);
# then physics' contract asking a reply to describe an electric field's picture in a
# ```draw block (physics.field_lines.contract), physics' pack saying a situation is never
# drawn in characters, a table or Mermaid (PHYSICS_NO_SKETCH), and a sentence around the
# working stating only numbers the working shows (VERIFIED_SOLVE_SAFETY_HINT; the owner's
# GCSE set, 2026-11-16); then physics' scene contract, a problem's setup described by the
# scene and the question's values, never a coordinate (physics.scene_drawing.contract, the
# owner's round of 30 hard problems, 2026-11-16), naming a horizontal launch, bodies moving
# the same way and the situations it never draws; no spring or wave, which no reader confirms
# (its reviews, 2026-11-16); then no biology presentation hint, biology being out of v1
# (2026-11-18); then the summary saying it stands for the chat's first messages, so the start of the
# chat is in it (SUMMARY_SPAN), and a short line's note naming the message and part it follows
# (FOLLOW_UP_NOTE), the Grade 8 chat, 2026-11-18; then a circuit and a plane mirror described in the
# same way, no flowchart for a thing or a motion, a motion's graphs in stages, and a reply never
# writing that a picture is shown or mentioning its block (physics.scene_drawing.contract, Grade 8
# round, 2026-11-18); then a ```worked part asked in words, said in `say` lines and answered in one
# sentence (prompt_constants.worked, G8 round t42, 2026-11-18), and its answer record's value and
# its substitution left unrounded, the "3 significant figures" gone: the server rounds every card by
# one rule (services.rounding_rule, the owner, 2026-11-18); then a conversation about the user's own
# life answered as one (an 80-message chat, 2026-11-19): no offer or list in it, no news read as a
# yes to an offer, a concern said once, a known day not dated again, emoji that fit their line, a
# safety check asked once and 911 kept for a stated threat (FORMAT_CONTRACT, READER_NOTE,
# UNCLEAR_MESSAGE_HINT, NO_RECAP_NOTE, the clock block, EMOJI_HINTS, DISTRESS_RULE,
# PERSONAL_HELP_RULE); then, from its replay, the summary keeping no advice of the assistant's
# (ASSISTANT_CONCERNS_RULE, SUMMARY_LEAD), advice not tied to each new detail, the safety check
# asked once in any words and a crisis line kept to its cases, and news never set against the date;
# then a physics hint saying a change is final minus initial and a result keeps its formula's sign
# (PHYSICS_SIGNS, the owner, 2026-11-20); then the turn after a reply cut off told to go on from
# where it stopped, in any language (CUT_OFF_REPLY_NOTE, the 20-part question, 2026-11-18); then
# each value its own answer record, a vector by its components or its size and direction
# (prompt_constants.worked, the owner's chat, 2026-11-20); then Hindi in place of German and
# Italian: the worked block's language codes, the To-do screen's names, and the readers' German
# and Italian home-chip and capability phrases gone (the owner, 2026-11-20); then a note for each
# kind of texted reply the read names (accept, decline, pick, more, explain, react; FOLLOW_NOTES,
# 100 texted chats, 2026-11-21).
_RULES = 211
_RULE_GRAMS = 20159
_RULE_GRAMS_SHA = "f626abb70e91e964"


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
