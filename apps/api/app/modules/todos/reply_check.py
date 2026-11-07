"""Whether a reply about reminders says only what the server saved.

A model "Set:" line or "I've set a reminder" is not a save. When nothing was
saved, ``reply_when_nothing_saved`` asks for the missing time or says nothing
changed; the classifiers here tell a reply about the user's reminders from one
that only mentions the word. ``reply_claims`` finds the claim sentences.
"""

from __future__ import annotations

import re

from app.modules.todos.reminder_fence_parse import explicitly_declines_reminder_creation
from app.modules.todos.reply_claims import (
    CLAIM_VERBS,
    COLON_CLAIM_RE,
    PROSE_CLAIM_RE,
    is_claim,
    split_sentences,
    without_claim_lines,
)
from app.modules.todos.spoken_add import (
    ADD_REQUEST_RE,
    FILLER_RE,
    WORD_RE,
    adds_content,
    asks_to_add,
    is_reminder_request,
    parse_spoken_add,
    user_named_a_clock,
    which_half_question,
)
from app.modules.todos.spoken_change import parse_spoken_reminder_change
from app.modules.todos.spoken_clauses import asked_when
from app.services.draft_fences import has_draft
from app.services.md_fence_scan import iter_fences, without_fences
from app.services.text_normalize import straighten_apostrophes as straighten

NEED_A_TIME = "When should I remind you?"
# There is no undated list (.cursor/rules/chat-ux-bans.mdc §8): "put buy groceries on my
# list" and "no time, just put it on the list" got "Added to your list" with nothing saved
# (2026-11-06). What chat can keep is a reminder, and it needs a time.
KEEP_AS_REMINDER = "I can keep that as a reminder with a time. When should I remind you?"
_DECLINE_SAVE_RE = re.compile(
    r"\b(?:i (?:set|added|saved|scheduled)|reminder (?:is |was )?set)\b",
    re.IGNORECASE,
)
_DECLINE_NEGATION_RE = re.compile(
    r"\b(?:no reminder|not set|didn(?:'|\u2019)t|did not|won(?:'|\u2019)t|will not|without)\b",
    re.IGNORECASE,
)
_CHANGE_LEADS = (
    "cancel ",
    "undo ",
    "make ",
    "change ",
    "set ",
    "put ",
    "mark ",
    "complete ",
    "finish ",
    "reopen ",
    "uncheck ",
    "delete ",
    "remove ",
    "move ",
    "reschedule ",
)
_COMMON_WORDS = frozenset(
    {
        "about",
        "after",
        "all",
        "and",
        "any",
        "are",
        "before",
        "but",
        "can",
        "did",
        "for",
        "from",
        "get",
        "got",
        "had",
        "has",
        "have",
        "her",
        "his",
        "how",
        "into",
        "its",
        "just",
        "let",
        "may",
        "more",
        "not",
        "now",
        "off",
        "one",
        "our",
        "out",
        "some",
        "that",
        "the",
        "this",
        "too",
        "use",
        "was",
        "who",
        "why",
        "with",
        "yes",
        "you",
        "your",
    }
)
_ASKS_WHEN_RE = re.compile(r"\b(?:when|what time|which day)\b", re.IGNORECASE)
# A reply is about the user's reminders when it says so, or confirms a dated
# one the way the app does ("Set: read — Monday, Oct 12, 8:00 AM.").
_REMINDER_TALK_RE = re.compile(
    r"\b(?:remind(?:er|ers)?|to-?dos?|to-do list|task list"
    r"|your (?:grocery list|shopping list|list|schedule|calendar))\b",
    re.IGNORECASE,
)
# "Quick reminder: it's 9/5 + 32" teaches a fact; it is not about saved reminders.
_FACT_REMINDER_RE = re.compile(
    r"\b(?:quick|friendly|gentle)\s+reminder\b\s*[\u2014\u2013:,-]", re.IGNORECASE
)
_SAVED_TALK_RE = re.compile(
    r"\b(?:your\s+(?:reminders?|to-?dos?|to-do\s+list|task\s+list|list|schedule)"
    r"|remind\s+you|reminder\s+(?:is\s+|was\s+)?set|(?:is|are|was)\s+set\s+for"
    r"|you\s+have\s+(?:\w+\s+)?(?:reminders?|to-?dos?|tasks?)"
    r"|due\s+(?:today|tomorrow|tonight)|next\s+up"
    r"|marked\s+\**[^*\n]{1,60}\**\s+as\s+(?:done|complete))\b",
    re.IGNORECASE,
)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_DATED_CLAIM_RE = re.compile(
    rf"(?:^|\n|!\s*)\s*{CLAIM_VERBS}\s*:\s+[^\n]+?\s[\u2014\u2013]\s+[^\n]*"
    r"(?:\d|today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|daily|weekly|weekdays|monthly)",
    re.IGNORECASE,
)


def reply_when_nothing_saved(
    text: str,
    user_text: str | None,
    *,
    about_reminders: bool = False,
    prior_assistant: str | None = None,
    prior_user: str | None = None,
) -> str:
    """The model must not confirm a reminder the server did not save.

    Only a reply about reminders is checked: one with a reminder fence
    (``about_reminders``), or one that talks about reminders or confirms a
    dated one. "Can you add 3 + 4?" answered with "3 + 4 = 7", or an answer
    with a "Created: 1991" line, is not one. ``prior_assistant`` and ``prior_user``: the
    exchange before this turn; after it asked when to remind, or asked anything about an add
    the user had just asked for, this message goes on with that add.
    """
    if not (
        about_reminders
        or mentions_reminders(text)
        or explicitly_declines_reminder_creation(user_text)
    ):
        return text
    words = _without_code(text)
    pending = asked_when(prior_assistant) or _asked_about_an_add(prior_assistant, prior_user)
    asked = pending or _asked_to_change_or_add(user_text)
    colon = bool(COLON_CLAIM_RE.search(words))
    prose = bool(asked and (PROSE_CLAIM_RE.search(words) or _claims_in(words)))
    lines = text.splitlines()
    kept = without_claim_lines(lines)
    changed = len(kept) != len(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip() if changed else text
    if _needs_time(user_text) or (pending and _wants_no_time(user_text)):
        if _ASKS_WHEN_RE.search(cleaned) and not colon and not prose:
            return cleaned
        return _when_question(user_text)
    if explicitly_declines_reminder_creation(user_text) and _DECLINE_SAVE_RE.search(cleaned):
        if not _DECLINE_NEGATION_RE.search(cleaned):
            return "I didn't set a reminder."
    if colon or prose:
        # Asked when, they answered with no time: what chat can keep still needs one.
        return KEEP_AS_REMINDER if pending and not user_named_a_clock(user_text) else _UNCHANGED
    if changed and not cleaned.strip():
        return _UNCHANGED
    return cleaned if changed else text


_UNCHANGED = "I didn't change your reminders."


def _asked_about_an_add(prior_assistant: str | None, prior_user: str | None) -> bool:
    """The last reply asked a question about the add the user's message before asked for:
    "when should I set 'Buy groceries' for?" after "add buy groceries to my list"."""
    if not prior_assistant or not prior_assistant.rstrip().endswith("?"):
        return False
    return asks_to_add(prior_user)


def _needs_time(user_text: str | None) -> bool:
    """The message adds something (to a list, or as a reminder) and names no clock."""
    if not user_text or adds_content(user_text) or user_named_a_clock(user_text):
        return False
    return bool(ADD_REQUEST_RE.search(user_text) or asks_to_add(user_text))


# "No time, just put it on the list", "whenever", "I don't need a reminder, just add it".
_NO_TIME_RE = re.compile(
    r"\b(?:no (?:time|date|reminder|alarm|due date)|without (?:a |any )?(?:time|date|reminder)"
    r"|any ?time|whenever|just (?:put|add|list|keep|save|write)"
    r"|don'?t (?:need|want|set) (?:a |any )?(?:time|reminder|date|alarm))\b",
    re.IGNORECASE,
)


def _wants_no_time(user_text: str | None) -> bool:
    """The answer to "when?" asks for the item with no time, which chat cannot keep."""
    return bool(user_text) and _NO_TIME_RE.search(straighten(user_text or "")) is not None


def _when_question(user_text: str | None) -> str:
    """What to ask for an add with no clock: only the half of the day when the user said
    "tomorrow at 6"; when for a reminder they asked for; and for an add to a list, that it
    can be kept only as a reminder with a time."""
    half = which_half_question(parse_spoken_add(user_text))
    if half is not None:
        return half
    return NEED_A_TIME if is_reminder_request(user_text) else KEEP_AS_REMINDER


def _claims_in(words: str) -> bool:
    """A sentence of the reply that says a change was made ("it's on your list")."""
    return any(is_claim(part) for line in words.splitlines() for part in split_sentences(line))


def mentions_reminders(text: str | None) -> bool:
    """A reply that talks about reminders or confirms a dated one.

    Code is not talk: a React ``todos`` array or ``done: false`` is not a reminder.
    """
    if not text:
        return False
    words = _FACT_REMINDER_RE.sub(" ", _without_code(text))
    return bool(_REMINDER_TALK_RE.search(words) or _DATED_CLAIM_RE.search(words))


def claims_a_reminder_change(text: str | None) -> bool:
    """A reply line in the app's own result shape, such as "Reopened: buy milk."."""
    if not text:
        return False
    lines = _without_code(text).splitlines()
    return len(without_claim_lines(lines)) != len(lines)


def edits_prior_reply(subject: str, *, prior_assistant: str | None, reply: str | None) -> bool:
    """ "Add a stop in Bahir Dar on Saturday at 9am" right after a trip plan edits the plan.

    So does "remove the gym on Monday" after a workout plan: the saved "gym"
    reminder is not touched. True when the reply before this turn is not
    about saved reminders, this reply says nothing about them, and what the
    message names is part of that earlier reply. The caller checks that the
    message itself does not say reminder or task.
    """
    if not prior_assistant or about_saved_reminders(prior_assistant):
        return False
    if mentions_reminders(reply) or claims_a_reminder_change(reply):
        return False
    earlier = {word.lower() for word in WORD_RE.findall(prior_assistant)}
    named = {word.lower() for word in WORD_RE.findall(subject)} - _COMMON_WORDS
    return bool(named & earlier)


def about_saved_reminders(text: str | None) -> bool:
    """A reply about the user's saved reminders, as the app writes one.

    "Set: gym — Thursday, 6:00 PM.", "your reminders", "is set for Friday".
    An email headed "Reminder: assignment due Friday" is someone else's deadline.
    """
    if not text or has_draft(text):
        return False
    if any(fence.lang == "reminder_proposal" for fence in iter_fences(text)):
        return True
    words = _FACT_REMINDER_RE.sub(" ", _without_code(text))
    return bool(
        _SAVED_TALK_RE.search(words)
        or _DATED_CLAIM_RE.search(words)
        or claims_a_reminder_change(text)
    )


def _without_code(text: str) -> str:
    return _INLINE_CODE_RE.sub(" ", without_fences(text, " "))


def _asked_to_change_or_add(user_text: str | None) -> bool:
    if not user_text or adds_content(user_text):
        return False
    if ADD_REQUEST_RE.search(user_text):
        return True
    if FILLER_RE.sub("", user_text.strip().lower()).startswith(_CHANGE_LEADS):
        return True
    return parse_spoken_reminder_change(user_text) is not None
