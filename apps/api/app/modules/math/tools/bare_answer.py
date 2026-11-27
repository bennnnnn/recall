"""A message that is only an answer ("x = 6"), with no problem to check it against.

The fallback extractor read "x = 6" as an equation to solve, and the reply was a
verified card saying x = 6. There is nothing to verify: ask what it answers.
A claim after a problem ("check my answer: x = 6") is the follow-up path's.
"""

from __future__ import annotations

import re

from app.modules.math.reply_policy import MATH_REPLY_POLICY

_BARE_ANSWER = re.compile(r"[a-z]\s*=\s*[-+]?\d+(?:\.\d+)?(?:\s*/\s*\d+)?", re.IGNORECASE)

BARE_ANSWER_NOTE = (
    "In one short sentence, ask which problem this value for a letter answers, so you can "
    "check it: with no problem there is nothing to verify, so write no answer card or "
    "solution.\n\n"
    f"{MATH_REPLY_POLICY}"
)


def bare_answer(text: str) -> bool:
    """True for "x = 6" or "y=-2.5" alone."""
    return _BARE_ANSWER.fullmatch(" ".join(text.split()).rstrip(".?! ")) is not None
