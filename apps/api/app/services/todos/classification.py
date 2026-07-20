"""Regex bank and query/transcript classifiers for Reminders & Lists."""

from __future__ import annotations

import re

_BULK_SHIFT_TO_TOMORROW = re.compile(
    r"("
    r"\b(move|shift|reschedule|push)\b.{0,40}\b(all|every|remaining|the rest|my reminders?)\b"
    r"|"
    r"\b(all|every|my)\b.{0,20}\b(reminders?|todos?|tasks?)\b.{0,40}\b(today|due today)\b.{0,40}\btomorrow\b"
    r"|"
    r"\b(reminders?|todos?|tasks?)\b.{0,30}\b(due )?today\b.{0,30}\btomorrow\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)
_TODO_QUERY = re.compile(
    r"\b("
    r"todo|todos|task|tasks|reminder|reminders|list|lists|checklist|"
    r"grocery|groceries|shopping|errand|errands|due|overdue|"
    r"what('?s| is) (?:on|in) my|show my|my (?:list|lists|reminders?|tasks?)|"
    r"add .+ to (?:my )?list|mark .+ (?:done|complete)|"
    r"move .+ to tomorrow|reschedule|shopping list"
    r")\b",
    re.IGNORECASE,
)
_TODO_SYNC_TRANSCRIPT = re.compile(
    r"\b("
    r"added (?:to|on)|removed from|marked (?:as )?(?:done|complete)|"
    r"new (?:list|reminder|task)|delete(?:d)? (?:the )?list|delete all|"
    r"delete overdue|removed (?:those |the )?overdue|"
    # Overdue nudge → model says "I'll delete …" (prompted future tense)
    r"I(?:'ll| will) delete|I deleted|I(?:'ve| have) (?:removed|deleted)|"
    r"deleting (?:the )?(?:reminder|task|todo)|"
    r"delete(?:d)? (?:the )?(?:reminder|task|todo|it)|"
    r"delete it|remove(?:d)? (?:the )?(?:reminder|task|todo)|"
    r"set (?:a )?(?:due|reminder)|moved .+ to tomorrow|"
    r"check(?:ed)? off|uncheck(?:ed)?|groceries|shopping list|"
    r"reminder for|due (?:at|on|tomorrow|today)|"
    # Past-tense / emoji confirms the model still emits despite the future-tense hint
    r"reminder set|reminders? (?:are |is )?set|"
    r"I(?:'ve| have) set (?:a |the |your )?reminder|"
    r"I(?:'ll| will) set (?:a |the |your )?reminder|"
    r"I set (?:a |the |your )?reminder"
    r")\b",
    re.IGNORECASE,
)
# "Delete" / "Delete overdue" / "Delete them" — current-turn user line.
_USER_DELETE_TURN = re.compile(
    r"(?:^|\n)User:\s*delete(?:\s+(?:it|them|all|overdue|those|these|my|the)){0,5}"
    r"(?:\s+reminders?)?\.?!?\s*(?:\n|$)",
    re.IGNORECASE,
)
_DELETE_OVERDUE = re.compile(
    r"("
    r"\bdelete\b.{0,40}\boverdue\b|"
    r"\bremove\b.{0,40}\boverdue\b|"
    r"\bdelete\b.{0,20}\b(all|every|them|those|these)\b.{0,40}\b(overdue|reminders?)\b|"
    r"\bI(?:'ve| have)?\s+(?:removed|deleted)\b.{0,60}\boverdue\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)
_AFFIRMATIVE = re.compile(
    r"^(yes|yeah|yep|sure|ok(?:ay)?|do it|confirm(?:ed)?|go ahead|please)\.?!?$",
    re.IGNORECASE,
)
_USER_LINE = re.compile(r"(?:^|\n)User:\s*(.+?)(?:\n|$)", re.IGNORECASE)
_ASSISTANT_BLOCK = re.compile(r"(?:^|\n)Assistant:\s*(.+)\Z", re.IGNORECASE | re.DOTALL)
_REMINDER_OR_TODO_WORD = re.compile(r"\b(reminders?|todos?|tasks?|lists?)\b", re.IGNORECASE)


def _transcript_implies_bulk_shift_to_tomorrow(transcript: str) -> bool:
    """True only for an explicit bulk reschedule (not vague 'fix it' complaints)."""
    text = transcript.strip()
    if not text:
        return False
    return bool(_BULK_SHIFT_TO_TOMORROW.search(text))


def _transcript_implies_delete_overdue(transcript: str) -> bool:
    text = transcript.strip()
    if not text:
        return False
    return bool(_DELETE_OVERDUE.search(text))


def query_implies_todos(query_text: str | None) -> bool:
    text = (query_text or "").strip()
    if not text:
        return False
    return bool(_TODO_QUERY.search(text))


def transcript_implies_todo_sync(transcript: str) -> bool:
    text = transcript.strip()
    if not text:
        return False
    if _transcript_implies_bulk_shift_to_tomorrow(text):
        return True
    if _transcript_implies_delete_overdue(text):
        return True
    if _USER_DELETE_TURN.search(text):
        return True
    if _TODO_SYNC_TRANSCRIPT.search(text):
        return True
    # "Yes" / "Sure" after a reminder offer — assistant reply mentions reminder/todo.
    user_m = _USER_LINE.search(text)
    asst_m = _ASSISTANT_BLOCK.search(text)
    if (
        user_m
        and asst_m
        and _AFFIRMATIVE.match(user_m.group(1).strip())
        and _REMINDER_OR_TODO_WORD.search(asst_m.group(1))
    ):
        return True
    return False


def should_pre_sync_todos(user_message: str, transcript: str) -> bool:
    if query_implies_todos(user_message):
        return True
    if transcript_implies_todo_sync(transcript):
        return True
    text = user_message.strip()
    if _AFFIRMATIVE.match(text) and re.search(r"\bdelete\b", transcript, re.IGNORECASE):
        return True
    return False
