"""Regex bank and query/transcript classifiers for To-do."""

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
    r"todo|todos|task|tasks|reminder|reminders|"
    r"remind me|"
    r"due|overdue|"
    r"what('?s| is) (?:on|in) my (?:reminders?|schedule|todos?|tasks?|calendar)|"
    r"show my (?:reminders?|schedule|todos?|tasks?|lists?|grocery list)|"
    r"my (?:reminders?|schedule|todos?|tasks?|lists?|grocery list)|"
    r"reschedule"
    r")\b",
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
# Bound gaps for linear "move X to tomorrow" scans (no ``.+`` ReDoS).
_TODO_PHRASE_GAP = 80
_USER_LABEL = "user:"


def _find_ci(haystack: str, needle: str, start: int = 0) -> int:
    return haystack.find(needle, start)


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


def query_implies_todos(query_text: str | None) -> bool:
    text = (query_text or "").strip()
    if not text:
        return False
    if _TODO_QUERY_FIXED.search(text):
        return True
    from app.modules.chat import has_locale_cue

    if has_locale_cue(text, "todos"):
        return True
    from app.services.time_context import is_scheduled_event_time_question

    if is_scheduled_event_time_question(text):
        return True
    low = text.lower()
    return _implies_mark_done(low) or _implies_move_to_tomorrow(low)
