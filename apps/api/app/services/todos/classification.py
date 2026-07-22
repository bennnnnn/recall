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
# Fixed-keyword branch only — phrases with unbounded ``.+`` are linear scans below.
_TODO_QUERY_FIXED = re.compile(
    r"\b("
    r"todo|todos|task|tasks|reminder|reminders|list|lists|checklist|"
    r"grocery|groceries|shopping|errand|errands|due|overdue|"
    r"what('?s| is) (?:on|in) my|show my|my (?:list|lists|reminders?|tasks?)|"
    r"reschedule|shopping list"
    r")\b",
    re.IGNORECASE,
)
_TODO_SYNC_TRANSCRIPT_FIXED = re.compile(
    r"\b("
    r"added (?:to|on)|removed from|marked (?:as )?(?:done|complete)|"
    r"new (?:list|reminder|task)|delete(?:d)? (?:the )?list|delete all|"
    r"delete overdue|removed (?:those |the )?overdue|"
    # Overdue nudge → model says "I'll delete …" (prompted future tense)
    r"I(?:'ll| will) delete|I deleted|I(?:'ve| have) (?:removed|deleted)|"
    r"deleting (?:the )?(?:reminder|task|todo)|"
    r"delete(?:d)? (?:the )?(?:reminder|task|todo|it)|"
    r"delete it|remove(?:d)? (?:the )?(?:reminder|task|todo)|"
    r"set (?:a )?(?:due|reminder)|"
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
_ASSISTANT_LABEL = re.compile(r"(?:^|\n)Assistant:\s*", re.IGNORECASE)
_REMINDER_OR_TODO_WORD = re.compile(r"\b(reminders?|todos?|tasks?|lists?)\b", re.IGNORECASE)

# Bound gaps for linear "add … to … list" style scans (no ``.+`` ReDoS).
_TODO_PHRASE_GAP = 80


def _find_ci(haystack: str, needle: str, start: int = 0) -> int:
    return haystack.find(needle, start)


def _implies_add_to_list(low: str) -> bool:
    """``add milk to my grocery list`` — linear scan, no ``add .+ to …list``."""
    start = 0
    while True:
        i = _find_ci(low, "add ", start)
        if i == -1:
            return False
        window = low[i : i + 4 + _TODO_PHRASE_GAP]
        to_i = _find_ci(window, " to ", 4)
        if to_i != -1 and "list" in window[to_i:]:
            return True
        start = i + 1


def _implies_mark_done(low: str) -> bool:
    start = 0
    while True:
        i = _find_ci(low, "mark ", start)
        if i == -1:
            return False
        window = low[i : i + 5 + _TODO_PHRASE_GAP]
        if " done" in window or " complete" in window:
            return True
        start = i + 1


def _implies_move_to_tomorrow(low: str) -> bool:
    """``move X to tomorrow`` / transcript ``moved X to tomorrow``."""
    for verb in ("move ", "moved "):
        start = 0
        while True:
            i = _find_ci(low, verb, start)
            if i == -1:
                break
            window = low[i : i + len(verb) + _TODO_PHRASE_GAP]
            if " to tomorrow" in window:
                return True
            start = i + 1
    return False


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
    if _TODO_QUERY_FIXED.search(text):
        return True
    low = text.lower()
    return _implies_add_to_list(low) or _implies_mark_done(low) or _implies_move_to_tomorrow(low)


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
    if _TODO_SYNC_TRANSCRIPT_FIXED.search(text):
        return True
    if _implies_move_to_tomorrow(text.lower()):
        return True
    # "Yes" / "Sure" after a reminder offer — assistant reply mentions reminder/todo.
    user_m = _USER_LINE.search(text)
    asst_m = _ASSISTANT_LABEL.search(text)
    if user_m and asst_m:
        asst_body = text[asst_m.end() :]
        if _AFFIRMATIVE.match(user_m.group(1).strip()) and _REMINDER_OR_TODO_WORD.search(asst_body):
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
