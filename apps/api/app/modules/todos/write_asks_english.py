"""Which English messages ask chat for a reminder, an alarm or a list item.

Chat only reads to-dos (``chat_language``), so such a request is answered by the server:
one line and the Open To-do button, no model call (``write_asks.todo_screen_reply``).

A request opens on it: "remind me to …", "can you set a reminder …", "add a reminder for
…", "set an alarm for 7", or puts something on their list in their own words ("add milk
to my list", "put eggs on the shopping list"). "Remind me how to convert Celsius" asks to
be taught, "you forgot to remind me" asks nothing, "add a line saying the rent is paid" and
"add two more examples" edit what the assistant wrote, and "my list of reasons" is no list.
"""

from __future__ import annotations

import re

from app.modules.todos.spoken_when import find_when

# "Remind me how to convert Celsius" asks to be taught, not reminded.
_REMIND_ME_OF_A_FACT = r"(?!\s+(?:how|what|why|who|whom|whose|which|where|whether|if)\b)"
_LEAD = r"(?:(?:always|also|just|and|so|now|then)\s+)?"
# The message opens by asking for a reminder: "remind me to …", "can you set a
# reminder to …", "add a reminder for …". "You forgot to remind me …" does not.
_REMINDER_REQUEST_RE = re.compile(
    rf"^{_LEAD}(?:(?:please|pls|plz)\s+)?(?:(?:can|could|will|would)\s+(?:you|u)\s+)?(?:please\s+)?"
    r"(?:remind\s+me" + _REMIND_ME_OF_A_FACT + r"|(?:set|create|add|make)\s+(?:me\s+)?"
    r"(?:a\s+)?(?:reminder|to-?do|task)\b|reminder\b)",
    re.IGNORECASE,
)
# "Make a to-do plan for my day", "create a task list app": a thing to write or build.
_A_THING_MADE_RE = re.compile(
    r"\b(?:reminder|to-?do|task)s?\s+(?:plan|list|app|apps|template|system|schedule)\b",
    re.IGNORECASE,
)
# An alarm is asked as a reminder.
_ALARM_RE = re.compile(r"^set (?:a |an )?alarm\b", re.IGNORECASE)
# Filler a spoken request starts with: "ok can you remind me …".
_FILLER_RE = re.compile(r"^(?:(?:wait|ok|okay|actually|oh|no|nah|sorry|hmm)[,!.]?\s+)+")
# "Put milk on my list", "add eggs to the shopping list": an add in the user's own words for
# a list. "My list of reasons" is not one.
# "The list" alone is one in the chat (a packing list): "add sunscreen to the list" edits it.
_ONTO_LIST_RE = re.compile(
    r"^(?:(?:please|pls|also|just|and|can you|could you)\s+)*(?:add|put|stick|pop|jot)\b.*"
    r"\b(?:to|on|onto|in)\s+(?:(?:my|our)\s+(?:to-?do\s+|todo\s+|task\s+|reminders?\s+"
    r"|shopping\s+|grocery\s+)?|the\s+(?:to-?do\s+|todo\s+|task\s+|shopping\s+|grocery\s+))"
    r"(?:list|to-?dos?|reminders|tasks)\b(?!\s+of\b)",
    re.IGNORECASE,
)
# The request may follow a clause of its own: "no time, just put it on the list".
_CLAUSE_RE = re.compile(r"[,;.!]\s+")
# "Add a line …", "add a rest day", "add two more examples": a part of what
# the assistant just wrote.
_CONTENT_ADD_RE = re.compile(
    r"^\s*(?:please\s+|pls\s+)?(?:(?:can|could)\s+you\s+)?(?:also\s+)?add\s+(?:in\s+)?"
    r"(?:a|an|one|another|some|the|more|two|three|\d+)\s+(?:[\w'-]+\s+){0,2}?"
    r"(?:lines?|sentences?|paragraphs?|sections?|bullets?|points?|p\.?s\.?|emojis?|jokes?"
    r"|titles?|headings?|subheadings?|signature|greeting|examples?|comments?|columns?|rows?"
    r"|tests?|steps?|stops?|days?|nights?|breaks?|visits?|detours?|chorus|verses?|hashtags?"
    r"|captions?|quotes?|details?|links?|footnotes?|references?|citations?|questions?"
    r"|options?|slides?|ingredients?)\b",
    re.IGNORECASE,
)
_NAMES_REMINDERS_RE = re.compile(
    r"\b(?:remind(?:er|ers)?|to-?dos?|tasks?|(?:my|your)\s+schedule"
    r"|as\s+(?:done|complete|completed|finished))\b",
    re.IGNORECASE,
)
_TYPOS = {
    "remimd": "remind",
    "remaind": "remind",
    "remid": "remind",
    "rmind": "remind",
}
_TOKEN_RE = re.compile(r"[^\W\d_]+")
_REMIND_ME_RE = re.compile(r"\bremind\s+me\b", re.IGNORECASE)
# "remind me to …", "remind me tomorrow to …", "remind me 2 buy milk".
_TO_A_TASK_RE = re.compile(r"(?:[^?]{0,60}?\s)?(?:to|2)\s+\w", re.IGNORECASE)


def is_reminder_request(text: str | None) -> bool:
    """The message opens by asking for a reminder: "remind me to …", "set a reminder …"."""
    cleaned = _FILLER_RE.sub("", _fix_typos((text or "").strip()).lower())
    return _REMINDER_REQUEST_RE.match(cleaned) is not None


def asks_for_reminder(text: str | None) -> bool:
    """The request asks for a reminder or an alarm (the plan's "reminder" part)."""
    return is_reminder_request(text) or _ALARM_RE.match((text or "").strip()) is not None


def asks_in_english(text: str | None) -> bool:
    """The message asks for a reminder, an alarm, or to put something on their list.

    "Remind me" asks for a reminder with a task ("… to call mom") or a time ("… tomorrow
    about the dentist"): "can you remind me the quadratic formula", "remind me of the plot
    of Inception" and "remind me again how much water?" ask to be told.
    """
    if not text or _adds_content(text):
        return False
    return any(_asks(clause) for clause in _CLAUSE_RE.split(text.strip()) if clause)


def _asks(text: str) -> bool:
    if _ONTO_LIST_RE.search(text) is not None:
        return True
    if not asks_for_reminder(text) or _A_THING_MADE_RE.search(text):
        return False
    fixed = _fix_typos(text)
    said = _REMIND_ME_RE.search(fixed)
    if said is None:
        return True
    rest = fixed[said.end() :]
    return _TO_A_TASK_RE.match(rest) is not None or bool(find_when(rest).spans)


def _adds_content(text: str) -> bool:
    """ "Add a line saying the rent is paid", "add a rest day": an edit, not a task."""
    return bool(_CONTENT_ADD_RE.search(text)) and not _NAMES_REMINDERS_RE.search(text)


def _fix_typos(text: str) -> str:
    return _TOKEN_RE.sub(lambda match: _TYPOS.get(match.group(0).lower(), match.group(0)), text)
