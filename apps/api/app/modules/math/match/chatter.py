"""A maths question after a few words of chat: "ok cool. what is 2+2".

The readers take the whole message, so the chat before a question kept it from the
solver: "lol got the second one wrong. random but whats 72 fahrenheit in celsius" and
"random question but what is 2+2" went to the model unchecked. Sentences before it that
hold no given are chat, so the question is the last sentence, without "random but",
"btw" or "ok cool". A digit before it may be a given ("x = 3. What is 2x + 1?"), and so
is a sentence that states a situation ("An eight-sided die is rolled.", "A biased coin is
tossed.", "Suppose the die is loaded."): the question after it is about that, so then
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

# A thing introduced and stated in the present: an article or a count, a few words, then
# is/are/has/contains ("A die is rolled", "Two dice are thrown", "Suppose the bag
# contains"). "This is so hard", "That was annoying" and "The test was hard" are remarks:
# a demonstrative points back at the chat and the past tense tells of it. "Let i be the
# interest rate" names a letter, which the reading of the question already sees.
_SITUATION = re.compile(
    r"^(?:(?:let|suppose|assume|given|if|when)\s+(?:that\s+)?)?(?:a|an|the|one|two|three"
    r"|four|five|six|seven|eight|nine|ten|twelve|some|each|every)\s+(?:[\w'-]+\s+){0,4}?"
    r"(?:is|are|has|have|contains?|holds?|shows?)\b",
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
    if any(_SITUATION.match(_CHAT_LEAD.sub("", sentence)) for sentence in before):
        return None
    question = _CHAT_LEAD.sub("", last).strip()
    if not question or question == cleaned:
        return None
    return question
