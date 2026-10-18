"""The one thing a turn asks about ("what is a capybara"), for the photo above the answer.

The general photo rule sits deep in a long prompt, and the small chat model skipped
it: "what is a capybara", "tell me about Lalibela" and "who is Haile Gebrselassie"
came back without a photo, while "where is kenya", which gets its own short hint,
always opened with one. This names the subject in a hint of its own; the model
still decides whether the thing is worth seeing ("what is recursion" is not).
"""

from __future__ import annotations

import re

_ASKS_ABOUT = re.compile(
    r"^\s*(?:(?:hey|so|ok(?:ay)?|and)[,\s]+)?(?:please\s+)?"
    r"(?:what(?:['\u2019]s|\s+is|\s+are|\s+was|\s+were)\s+(?:an?\s+)?"
    r"|who(?:['\u2019]s|\s+is|\s+are|\s+was|\s+were)\s+"
    r"|(?:(?:can|could)\s+you\s+)?tell\s+me\s+(?:a\s+(?:little\s+)?bit\s+)?about\s+(?:the\s+)?)"
    r"(?P<subject>[^\W\d_][\w'\u2019 .-]*?)\s*[?.!]*\s*$",
    re.IGNORECASE,
)
# Not one thing to look at: the asker, a pronoun, a lookup with a "the … of" frame.
_NOT_A_THING = re.compile(
    r"^(?:it|this|that|these|those|he|she|they|you|me|i|we|him|her|them|his|their"
    r"|(?:your|my|our)sel(?:f|ves)|the\s+(?:time|date|weather|answer|difference|best|meaning))\b"
    # "a good name for my cat" asks for an answer, not about a thing.
    r"|\b(?:my|your|our|for|to|with|that|which|should|good|best|the\s+\w+\s+of)\b",
    re.IGNORECASE,
)
_MAX_SUBJECT_WORDS = 5


def asked_about_subject(text: str) -> str | None:
    """``capybara`` for "what is a capybara"; None when the turn names no one thing."""
    match = _ASKS_ABOUT.match(text or "")
    if match is None:
        return None
    subject = match.group("subject").strip(" .")
    if not subject or len(subject.split()) > _MAX_SUBJECT_WORDS or _NOT_A_THING.search(subject):
        return None
    return subject


def subject_photo_hint(subject: str) -> str:
    """The photo rule for this turn's one subject; the model judges if it is worth seeing."""
    return (
        f'This turn asks about "{subject}". If that is something people would want to see (a '
        "place, landmark, animal, plant, person, food, product, vehicle or artwork), open the "
        f"reply with ```photo\n{subject}\n```, then answer as usual. An idea, a word, a feeling, "
        "or a process or concept from science, history or economics gets no photo, even when "
        'something visible is involved ("photosynthesis", "recursion", "inflation", "love").'
    )
