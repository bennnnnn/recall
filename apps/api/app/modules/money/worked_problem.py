"""A money question from a lesson: a textbook's scenario about someone else, or an order.

"Ato Alula deposited Birr 3,000 … What is the amount of interest obtained at the end of
seven years?" and "Moges wants to buy a house that costs Birr 250,000 …" got the right
numbers in two lines over a calculator card (2026-10-31): nothing a student could follow
or hand in. A worked problem's reply is laid out the way the STEM replies are.

It is read from who the question is about, never from its money words: a person or a firm
a book describes ("Ato Alula", "Moges wants", "a farmer", "the company"), or a book's order
("Calculate …", "Find …"). A message about the asker's own money ("I", "my", "we", "you")
keeps the short reply, and so does a bare question with no one in it ("What's the payment
on a $300,000 mortgage at 6.5%?").
"""

from __future__ import annotations

import re

_ASKER = re.compile(
    r"\b(?:i|i'm|i've|i'd|i'll|me|my|mine|we|we're|we've|our|ours|us|you|you're|your|yours)\b",
    re.IGNORECASE,
)
# Capitalised words that open a question or a clause, never a name.
_NOT_A_NAME = (
    r"(?!(?:What|How|Which|When|Where|Who|Why|If|Then|The|This|That|These|Those|Each|Every"
    r"|After|Before|At|In|On|For|With|Its|His|Her|Their|He|She|They|It)\b)"
)
_ACTOR = re.compile(
    r"\b(?:Ato|W/ro|Wro|Mr|Mrs|Ms|Miss|Dr)\.?\s+[A-Z][a-z]+"
    rf"|\b{_NOT_A_NAME}[A-Z][a-z]{{2,}}\s+(?:deposit|borrow|invest|save|want|take|buy|bought"
    r"|pay|paid|lend|lent|put|open|plan|get|got|receive|need|decide)\w*\b"
    r"|\b(?i:a|an|the)\s+(?i:man|woman|person|family|farmer|merchant|trader|company|firm"
    r"|business|shop|student|teacher|customer|couple|partner|bank\s+customer)s?\b"
)
_ORDER = re.compile(r"(?:^|[.?!:]\s+)(?:calculate|compute|find|determine|work\s+out)\b", re.I)


def is_worked_problem(text: str) -> bool:
    """A lesson's money problem: about someone a book describes, or a book's order, and
    not about the asker's own money."""
    if _ASKER.search(text) is not None:
        return False
    return _ACTOR.search(text) is not None or _ORDER.search(text.strip()) is not None
