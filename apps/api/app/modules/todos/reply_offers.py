"""A reply's offer to set a reminder, which chat cannot do: the question goes.

Chat never adds a to-do (owner, 2026-11-27), and a removed feature is never offered back:
"Would you like me to set up that **Practice list comprehensions** reminder for tomorrow at
7:00 PM?" or "Want me to add it to your list?" closing a reply offers what the app no longer
does. ``without_reminder_offers`` drops that question and keeps the rest; "Want a quiz on
this, or should I set a reminder?" keeps the quiz. The reminder is what is set, not where
something goes ("add error handling to the reminder service") or a thing about reminders
("a to-do list app", "a reminder of the key steps"). A reply holding code offers code
("Should I add a reminder field to the form?"), whatever its words, so it is left alone.
"""

from __future__ import annotations

import re

from app.services.md_fence_scan import iter_fences, line_fences

_ASKS = (
    r"(?:(?:would|do) you (?:like|want) me to|want me to|shall i|should i|can i)\s+"
    r"(?:(?:go ahead and|also|quickly)\s+)?"
)
_NOT_A_REMINDER = (
    r"(?!\s+(?:lists?\b|(?:lists?\s+)?(?:of|on how|about how|app|apps|system|tool|service|services|feature"
    r"|features|function|component|module|class|code|template|logic|api|screen|page|banner"
    r"|field|button|card|section|widget|bar|popup|modal|email|message|text|note|letter|post"
    r")\b))"
)
# Words between the verb and the reminder, none of them a preposition: "set up that
# Practice list comprehensions reminder", not "add error handling to the reminder".
_OBJECT_WORDS = r"(?:(?!(?:to|for|in|on|of|with|from|into|about)\b)[\w'-]+\s+){0,5}?"
_OFFER = re.compile(
    rf"\b{_ASKS}(?:set(?: up)?|add|create|schedule|make|save|delete|remove|move|change"
    rf"|cancel|reschedule|update|mark)\s+{_OBJECT_WORDS}"
    rf"(?:reminders?|to-?dos?){_NOT_A_REMINDER}\b"
    rf"|\b{_ASKS}(?:add|put|save)\s+[^?]{{0,80}}?\s+(?:to|on|in)\s+your\s+"
    r"(?:(?:to-?do|grocery|shopping)\s+)?(?:list|to-?dos|reminders)\b(?!\s+(?:app|of)\b)"
    rf"|\b{_ASKS}remind you\b(?!\s+(?:how|what|why|of|that|about how)\b)"
    rf"|\b(?:would|do) you (?:like|want) (?:a|that|this)\s+reminders?\b{_NOT_A_REMINDER}",
    re.IGNORECASE,
)
# A question, with the sentence break before it.
_QUESTION = re.compile(r"[^.!?\n]*\?")
# "Want a quiz on this, or should I set a reminder?": the quiz is still offered. "…at 7 or
# 8?" is the reminder's own: the other side is too short to be another offer.
_OR = re.compile(r",?\s+or\s+", re.IGNORECASE)
_CHOICE_WORDS = 3
# A choice that is an offer of its own opens like one: "Want a quiz", "should I draw it".
# "…tomorrow morning, or on your way home at 6 PM?" is the reminder's own time.
_AN_OFFER_OPENS = re.compile(
    r"^\W*(?:want|would|do|shall|should|can|could|how about|maybe|need)\b", re.IGNORECASE
)
# Every fence the phone draws as a card (``apps/mobile/lib/fence/registry.ts``, held to it by
# test_reply_offers) and the server's worked layout. Any other fence holds code.
CARD_LANGS = frozenset(
    {
        "3dmol", "answer", "arithmetic", "array", "blockquote", "calculator", "callout",
        "caption", "chart", "chem_scene", "chemistry", "clarify", "clock", "compare",
        "comparison", "copy", "email", "facebook", "fb", "fields", "final", "geometry", "graph",
        "ig", "important", "info", "insta", "instagram", "keyvalue", "kv", "latex", "linkedin",
        "math", "mermaid", "message", "mol3d", "molecule", "molecule3d", "note", "places",
        "plot", "pros", "quiz", "quote", "reply", "result", "simulation", "smiles", "sms",
        "social", "sources", "step", "steps", "tex", "threads", "tiktok", "time", "tip",
        "todo_link", "tweet", "twitter", "vega", "vega-lite", "warning", "x", "worked",
    }
)  # fmt: skip


# The fences a reply about a to-do change holds: the button, an old card or fence.
_TODO_FENCES = frozenset({"todo_link", "reminder_proposal", "reminder"})
# "When should I remind you?", "What time works for the reminder?": a reminder's question.
_ASKS_WHEN = re.compile(
    r"\b(?:when|what time|which day|what day)\b[^?]*\b(?:remind|reminder)"
    r"|\b(?:remind|reminder)\b[^?]*\b(?:when|what time|which day|what day)\b"
    r"|\b(?:am|a\.m\.) or (?:pm|p\.m\.)\?",
    re.IGNORECASE,
)
# "What time tomorrow?", "6 am or 6 pm?": a question asking when.
_ASKS_A_TIME = re.compile(
    r"\b(?:when|what time|which day|what day)\b|\b(?:am|a\.m\.) or (?:pm|p\.m\.)",
    re.IGNORECASE,
)
_TAIL_CHARS = 300


def follows_todo_reply(prior_reply: str | None) -> bool:
    """Whether the reply before a message was about a to-do change: the To-do button, an
    old reminder card, or a last question that offered a reminder or asked when to remind.
    A time after it ("6pm") asks for that change; old chats end on such a question, and a
    model may still write one."""
    if not prior_reply:
        return False
    if any(fence.lang.lower() in _TODO_FENCES for fence in iter_fences(prior_reply)):
        return True
    return asked_about_a_change(prior_reply)


def asked_about_a_change(prior_reply: str | None) -> bool:
    """Whether the reply's last question offered a reminder or asked when to remind: a yes
    to it ("yes", "sure") asks for that reminder."""
    if not prior_reply or holds_code(prior_reply):
        return False
    questions = _QUESTION.findall(prior_reply.rstrip()[-_TAIL_CHARS:])
    return bool(questions) and (_offers(questions[-1]) or bool(_ASKS_WHEN.search(questions[-1])))


def asks_when(text: str) -> bool:
    """Whether a reply asks when: under a request for a to-do change, it took on a change
    chat cannot make ("What time on Thursday?")."""
    return any(_ASKS_A_TIME.search(question) for question in _QUESTION.findall(text))


# "I can set a reminder for that instead.": the same offer, said as a statement. "I can't
# set reminders" is no offer.
_CAN_SET = re.compile(
    r"[^.!?\n]*\b(?:i|we)\s+(?:can|could)\s+(?:also\s+|always\s+|easily\s+)?(?:set(?: up)?|add"
    r"|create|schedule)\s+(?:a|an|the|one|that|this|you\s+a)\s+(?:[\w'-]+\s+){0,2}?reminders?\b"
    rf"{_NOT_A_REMINDER}[^.!?\n]*[.!]?",
    re.IGNORECASE,
)


def holds_code(text: str) -> bool:
    """Whether ``text`` holds a fence the app does not draw as a card: code."""
    return any(fence.lang.lower() not in CARD_LANGS for fence in iter_fences(text))


def without_reminder_offers(text: str) -> str:
    """The reply without a question offering to set a reminder or add to a list."""
    if not (_offers(text) or _CAN_SET.search(text.replace("*", ""))) or holds_code(text):
        return text
    lines = [
        line if fence is not None else _without_offer(line)
        for line, fence in zip(text.split("\n"), line_fences(text), strict=True)
    ]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _without_offer(line: str) -> str:
    kept = _CAN_SET.sub("", _QUESTION.sub(_kept_choice, line))
    if kept == line:
        return line
    indent = line[: len(line) - len(line.lstrip())]
    return indent + " ".join(kept.split())


def _offers(text: str) -> bool:
    """Whether ``text`` offers a reminder, read without its bold: "set up that **Practice**
    reminder"."""
    return _OFFER.search(text.replace("*", "")) is not None


def _kept_choice(match: re.Match[str]) -> str:
    """The question's choices that offer something else, or nothing."""
    question = match.group(0)
    if not _offers(question):
        return question
    lead = question[: len(question) - len(question.lstrip())]
    kept = [part for part in _OR.split(question.strip().rstrip("?")) if not _offers(part)]
    if not kept or any(
        len(part.split()) < _CHOICE_WORDS or not _AN_OFFER_OPENS.match(part) for part in kept
    ):
        return ""
    return f"{lead}{' or '.join(kept)}?"
