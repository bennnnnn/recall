"""Assistant Markdown presentation: boundaries, then calculation rows.

Server persist, direct replies, and the mobile preprocessor share this
contract. The mobile copy lives in ``lib/markdown/presentation.ts``.
"""

from __future__ import annotations

import re

from app.services.chat.calculation_layout import layout_calculations
from app.services.chat.inline_boundaries import repair_inline_token_boundaries

_WHY_QUESTION = re.compile(r"\b(?:why|explain)\b", re.IGNORECASE)
_BARE_NUMBER_LINE = re.compile(r"\d+(?:\.\d+)?")
_LEADING_NUMBER_FENCE = re.compile(
    r"\A```(?:answer|result|final)\n\s*\d+(?:\.\d+)?\s*\n```\s*",
    re.IGNORECASE,
)


def drop_orphan_leading_answer(reply: str, user_text: str) -> str:
    """A why-question with no digits does not open with the previous sum.

    Tapping "why are positive sums larger?" after 3 + 4 = 7 used to print
    that 7 on its own line, then the explanation.
    """
    if not reply or not user_text or any(char.isdigit() for char in user_text):
        return reply
    if _WHY_QUESTION.search(user_text) is None:
        return reply
    text = _LEADING_NUMBER_FENCE.sub("", reply, count=1).lstrip()
    lines = text.split("\n")
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines) and _BARE_NUMBER_LINE.fullmatch(lines[index].strip()):
        text = "\n".join(lines[index + 1 :]).strip()
    return text


def present_assistant_markdown(text: str) -> str:
    """Repair closed inline tokens, then split multi-step calculations."""
    if not text:
        return text
    return layout_calculations(repair_inline_token_boundaries(text))
