"""Words before a percent that make it a term: "subtract 5 from 25% of 80"."""

from __future__ import annotations

import re

from app.services.number_text import DECIMAL

# A number taken from or added to the percent, said before it: "subtract 5 from", "take 5
# away from", "5 subtracted from", "5 less than", "add 5 to", "5 more than". The percent is
# the first operand.
_LEADING_OPERATION = re.compile(
    rf"(?:\b(?P<take>subtract(?:ing)?|tak(?:e|ing)(?:\s+away)?)\s+\$?(?P<taken>{DECIMAL})"
    r"\s+(?:away\s+)?from"
    rf"|\$?(?P<subtracted>{DECIMAL})\s+(?:subtracted|taken\s+away)\s+from"
    rf"|\b(?P<add>add(?:ing)?)\s+\$?(?P<added>{DECIMAL})\s+to"
    rf"|\$?(?P<compared>{DECIMAL})\s+(?P<than>less|fewer|more)\s+than)"
    r"\s+(?:the\s+)?$",
    re.IGNORECASE,
)
# Words before the percent that make it one term of a larger request: "subtract it from",
# "the difference between", "twice".
_ARITHMETIC_BEFORE = re.compile(
    r"[+*/^=\u00d7\u00f7\u2212]|(?<![A-Za-z])-|-(?![A-Za-z])|\b(?:subtract\w*|minus|plus|add|adds|added|adding|sum|"
    r"difference|product|quotient|times|multipl\w*|divid\w*|away|less|fewer|more|increase\w*|"
    r"decrease\w*|twice|double|triple|half)\b",
    re.IGNORECASE,
)
# Where the sentence that holds the percent begins.
_SENTENCE_END = re.compile(r"[.?!;:](?=\s|$)|\n")


def leading_addend(cleaned: str, rate_start: int) -> tuple[bool, float | None]:
    """What the words before the percent do to it: (readable, the addend they give).

    "Subtract 5 from 25% of 80" is 25% of 80 - 5. Read from the percent alone it verified
    20 (2026-10-31, a translated question read back in English). Any other operation
    before the percent in its sentence makes it a term of a larger request: not readable.
    A number alone is the question's setting ("Out of 250 people, what is 30% of 80?").
    """
    head = cleaned[:rate_start]
    ends = [match.end() for match in _SENTENCE_END.finditer(head)]
    head = head[ends[-1] if ends else 0 :]
    addend: float | None = None
    lead = _LEADING_OPERATION.search(head)
    if lead is not None:
        if lead.group("take"):
            addend = -float(lead.group("taken"))
        elif lead.group("subtracted"):
            addend = -float(lead.group("subtracted"))
        elif lead.group("add"):
            addend = float(lead.group("added"))
        else:
            amount = float(lead.group("compared"))
            addend = amount if lead.group("than").lower() == "more" else -amount
        head = head[: lead.start()]
    if _ARITHMETIC_BEFORE.search(head):
        return False, None
    return True, addend
