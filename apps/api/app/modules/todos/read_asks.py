"""Whether a message asks what is saved, so the saved rows answer it.

Live (2026-10-25): "ok last thing, what's on my to do list right now?" and "hmm are you
sure? check my to-do list again" were answered by the model from the chat. It listed a
reminder whose card was never tapped, and left out the one saved for that evening. Only
"what are my reminders" and the like were read, and only at the very start of the
message. The app calls the list To-do: "to-do list", "to do list" and "todo list" are how
people name it, and each is read as one. A clause that opens with a read asks it ("ok
last thing, what's on…", "are you sure? check my…") when the clauses beside it are short
and none asks for a change: "what's on my list and what's 2 + 2?" keeps its sum.
"""

from __future__ import annotations

import re

from app.modules.todos.spoken_change import _prepare

_READ_OPENINGS = (
    "what reminders do i have",
    "what are my reminders",
    "what are my todos",
    "whats on my schedule",
    "what is on my schedule",
    "what is scheduled",
    "whats scheduled",
    "what do i have scheduled",
    "what do i have on my schedule",
    "do i have any reminders",
    "do i have reminders",
    "show my reminders",
    "show my schedule",
    "show me my reminders",
    "show me my schedule",
    "list my reminders",
    "list my todos",
    "list my schedule",
    "read my reminders",
    "read my schedule",
    "whats on my todo list",
    "what is on my todo list",
    "whats in my todo list",
    "what is in my todo list",
    "whats on my todos",
    "show my todo list",
    "show me my todo list",
    "show my todos",
    "show me my todos",
    "check my todo list",
    "check my todos",
    "check my reminders",
    "read my todo list",
    "read my todos",
    "list my todo list",
)
# Openings that do not say "my": a place after them is somewhere else's schedule.
_BARE_READS = frozenset({"what is scheduled", "whats scheduled"})
_ELSEWHERE = re.compile(
    r"\s+(?:at|in)\s+(?!\d|noon\b|midnight\b|the (?:morning|afternoon|evening)\b)"
)
# The list's names, as one: "to-do list", "to do list", "todo-list", "to-dos".
_LIST_NAME = re.compile(r"\bto[- ]do(?=s?\b)")
_LIST_DASH = re.compile(r"\btodo-(?=lists?\b)")
# A change asked beside the read: the change is the turn, not the reading.
_CHANGE_LEADS = ("add ", "remind ", "make ", "delete ", "move ", "set ", "mark ", "remove ")
_CLAUSE = re.compile(r"(?:[,;:!?]|\.(?=\s))\s*|\s+(?:and|also)\s+|\s[\u2014\u2013-]\s")
# A clause beside the read that is chatter ("ok last thing", "hmm are you sure"), not a
# question of its own ("what's 2 + 2").
_ASIDE_WORDS = 4
_QUESTION_LEADS = ("what", "whats", "how", "why", "when", "where", "who", "whos", "which")


def asks_to_read_reminders(user_text: str | None) -> bool:
    """True when they asked what is saved, not to change it."""
    text = _folded(user_text)
    if not text:
        return False
    clauses = [_folded(part) for part in _CLAUSE.split(text)]
    clauses = [clause for clause in clauses if clause]
    if any(clause.startswith(_CHANGE_LEADS) for clause in clauses):
        return False
    reads = [clause for clause in clauses if _opens_a_read(clause)]
    if not reads:
        return False
    return all(clause in reads or _is_aside(clause) for clause in clauses)


def _folded(text: str | None) -> str:
    lowered = _prepare(text).lower().replace("'", "").replace("\u2019", "")
    return _LIST_DASH.sub("todo ", _LIST_NAME.sub("todo", lowered))


def _is_aside(clause: str) -> bool:
    words = clause.split()
    return len(words) <= _ASIDE_WORDS and words[0] not in _QUESTION_LEADS


def _opens_a_read(clause: str) -> bool:
    for opening in _READ_OPENINGS:
        if clause.startswith(opening):
            # "What's scheduled at the Hollywood Bowl" asks about a venue.
            return opening not in _BARE_READS or not _ELSEWHERE.match(clause[len(opening) :])
    return False
