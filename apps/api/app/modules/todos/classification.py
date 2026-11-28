"""Regex bank and query/transcript classifiers for To-do."""

from __future__ import annotations

import re

# Fixed-keyword branch only — phrases with unbounded ``.+`` are linear scans below.
# The list goes by the app's own name, To-do, however it is spelled: "what's on my to-do
# list?" and "my to do list" loaded nothing (2026-10-25), and the reply was made up from
# the chat. "Things to do" and "what to do" name no list.
_TODO_QUERY_FIXED = re.compile(
    r"\b("
    r"todo|todos|to-dos?|to do lists?|task|tasks|reminder|reminders|"
    r"what do i have (?:on |planned |going on )?(?:today|tonight|tomorrow|this week(?:end)?)|"
    r"remind me|"
    r"due|overdue|"
    r"what('?s| is) (?:on|in) my (?:reminders?|schedule|todos?|tasks?|calendar)|"
    r"show my (?:reminders?|schedule|todos?|tasks?|lists?|grocery list)|"
    r"my (?:reminders?|schedule|todos?|tasks?|lists?|grocery list)|"
    r"reschedule|uncheck|(?:check|tick|cross)\s+(?:it|that|them|this)\s+off"
    r")\b",
    re.IGNORECASE,
)
# Bound gaps for linear "move X to tomorrow" scans (no ``.+`` ReDoS).
_TODO_PHRASE_GAP = 80


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


# A to-do named in its own words: a reminder, a to-do, their list, an alarm, or ticking
# one off. "Remind me the quadratic formula" and "create a task queue" name none.
_NAMES_A_TODO = re.compile(
    r"\breminders?\b|\bto-?dos?\b|\balarms?\b"
    r"|\b(?:my|our|the)\s+(?:to-?do\s+|shopping\s+|grocery\s+)?list\b(?!\s+of\b)"
    r"|\b(?:mark|tick|check|cross)\b[^.!?\n]{0,40}?\b(?:done|complete|completed|off)\b",
    re.IGNORECASE,
)


def names_a_todo(text: str | None) -> bool:
    """Whether ``text`` speaks of a to-do in to-do words (see ``_NAMES_A_TODO``)."""
    return bool(text and _NAMES_A_TODO.search(text))


def query_implies_todos(query_text: str | None) -> bool:
    text = (query_text or "").strip()
    if not text:
        return False
    if _TODO_QUERY_FIXED.search(text):
        return True
    from app.modules.turn_reading.locale_cues import has_locale_cue

    if has_locale_cue(text, "todos"):
        return True
    from app.services.time_context import is_scheduled_event_time_question

    if is_scheduled_event_time_question(text):
        return True
    low = text.lower()
    return _implies_mark_done(low) or _implies_move_to_tomorrow(low)
