"""A request to see something: "draw it", "graph the curve", "show it", "a picture of it".

Only the words are read here. A request whose object is a pronoun names nothing of its own;
what "it" is, is read from the chat by a model (``chat.referent_read``), never by a word
rule: an ordinary follow-up ("what is the domain?", "wow") is no new subject, and a word
list that guessed otherwise drew nothing after it.
"""

from __future__ import annotations

import re

from app.services.text_normalize import collapse_ws

# "Draw it", "graph this", "can you plot that please": a request to see the subject.
_SEE_VERBS = ("graph", "plot", "sketch", "draw", "visualize", "visualise", "chart")
_POLITE_PREFIXES = ("please ", "can you ", "could you ")
# The objects that name nothing: the subject is one the chat named.
_PRONOUN_OBJECTS = frozenset({"", "it", "this", "that"})
# "Show it", "can I see it", "a picture of it": asked to be shown, in words a photo lookup
# uses too. Live (2026-11-09) "show it" after sin(x) searched photos for "it". "Give me
# that" and "send me that" accept an offer, and stay out.
_SHOW_LEADS = (
    "show me ",
    "show us ",
    "show ",
    "let me see ",
    "can i see ",
    "could i see ",
    "may i see ",
    "i want to see ",
)
_PICTURE_OF = re.compile(
    r"(?:(?:a|an|the) )?(?:picture|photo|image|pic|drawing|diagram|sketch|graph|plot) of "
)


def _without_politeness(lower: str) -> str:
    text = lower
    changed = True
    while changed:
        changed = False
        if text.startswith("please "):
            text = text[7:].strip()
            changed = True
        if text.endswith(" please"):
            text = text[:-7].strip()
            changed = True
        for prefix in _POLITE_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()
                changed = True
                break
    return text


def see_request_object(line: str) -> str | None:
    """What a request to see names: "" for the verb alone ("Plot"), "it" for "draw it",
    "the curve" for "graph the curve"; None for a line that is no such request."""
    lower = _without_politeness(collapse_ws(line).lower().rstrip(".!?"))
    for verb in _SEE_VERBS:
        if lower == verb:
            return ""
        if lower.startswith(f"{verb} "):
            return lower[len(verb) + 1 :].strip()
    return None


def _shown_object(line: str) -> str | None:
    """What a request to see or be shown names ("it" for "show me a picture of it"), or
    None for a line that is no such request."""
    rest = see_request_object(line)
    if rest is None:
        lower = _without_politeness(collapse_ws(line).lower().rstrip(".!?"))
        rest = next((lower[len(lead) :] for lead in _SHOW_LEADS if lower.startswith(lead)), None)
        if rest is None and _PICTURE_OF.match(lower) is None:
            return None
        rest = lower if rest is None else rest
    picture = _PICTURE_OF.match(rest)
    return (rest[picture.end() :] if picture else rest).strip()


def asks_to_see(line: str) -> bool:
    """ "Draw it", "graph this", "Plot", "show it", "can I see that?", "a picture of it": a
    request to see something the chat named, and nothing of its own."""
    return _shown_object(line) in _PRONOUN_OBJECTS
