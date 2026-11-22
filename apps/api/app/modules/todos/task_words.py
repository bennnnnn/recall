"""The words of a reminder's task: what two wordings of it share, and what says nothing of it.

A leaf, below the read's check (``read_check``) and the saved rows (``reminder_writes``),
which both compare a task the user named with another wording of it.
"""

from __future__ import annotations

import re

WORD = re.compile(r"[^\W\d_]{3,}")
NOT_TASK_WORDS = frozenset(
    "the and for with about remind reminder reminders please can you could would tomorrow "
    "today tonight tmrw this that then them they she her his him my our your its it's at on "
    "in to of me set make sure don't dont forget ping".split()
)


def stem(word: str) -> str:
    return word.casefold()[:4]


def same_task(title: str, other: str) -> bool:
    """Two wordings of one task: they share two of its words (one, for a one-word task),
    "call mom" and "Call mom tonight"; "call grandma" is another."""
    words = {stem(w) for w in WORD.findall(title) if w.casefold() not in NOT_TASK_WORDS}
    theirs = {stem(w) for w in WORD.findall(other) if w.casefold() not in NOT_TASK_WORDS}
    return bool(words) and len(words & theirs) >= min(2, len(words), len(theirs) or 1)
