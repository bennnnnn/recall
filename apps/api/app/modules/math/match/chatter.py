"""A maths question after a few words of chat: "ok cool. what is 2+2".

The readers take the whole message, so the chat before a question kept it from the
solver: "lol got the second one wrong. random but whats 72 fahrenheit in celsius" and
"random question but what is 2+2" went to the model unchecked. Sentences before it that
hold no digit are chat, so the question is the last sentence, without "random but",
"btw" or "ok cool". A digit before it may be a given ("x = 3. What is 2x + 1?"), so then
nothing is dropped.
"""

from __future__ import annotations

import re

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_CHAT_LEAD = re.compile(
    r"^(?:(?:lol|lmao|haha|ha|ok(?:ay)?|cool|nice|so|and|also|anyway|btw|by\s+the\s+way|hey|"
    r"hmm|oh|wait|alright|random(?:\s+question)?|quick\s+question|unrelated|"
    r"different\s+question|one\s+more|another\s+one)\s*[,:!.]?\s*(?:but\s+)?)+",
    re.IGNORECASE,
)


def question_after_chat(text: str) -> str | None:
    """The question after the chat before it, or None when nothing was chat."""
    cleaned = " ".join(text.split())
    sentences = [part for part in _SENTENCE_END.split(cleaned) if part]
    if not sentences:
        return None
    *before, last = sentences
    if any(char.isdigit() for sentence in before for char in sentence):
        return None
    question = _CHAT_LEAD.sub("", last).strip()
    if not question or question == cleaned:
        return None
    return question
