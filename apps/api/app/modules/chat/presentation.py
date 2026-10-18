"""Assistant Markdown presentation: REPL transcripts, boundaries, then calculation rows.

The finalize pass, the direct replies and live talk run it before a reply is saved, so a
persisted assistant row is already presented. The phone shows rows saved from its
``SERVER_PRESENTATION_CUTOVER`` as saved and presents only the text still streaming and
older rows. Its twin is ``apps/mobile/lib/markdown/presentation.ts``;
docs/fixtures/presentation_cases.json holds both to the same output.
"""

from __future__ import annotations

import re

from app.modules.chat.calculation_layout import layout_calculations
from app.modules.chat.inline_boundaries import repair_inline_token_boundaries
from app.modules.chat.notation_spans import code_notation
from app.modules.chat.repl_transcript import fence_repl_transcripts

_WHY_QUESTION = re.compile(r"\b(?:why|explain)\b", re.IGNORECASE)
_BARE_NUMBER_LINE = re.compile(r"\d+(?:\.\d+)?")
_LEADING_NUMBER_FENCE = re.compile(
    r"\A```(?:answer|result|final)\n(?:verified: true\n)?\s*\d+(?:\.\d+)?\s*\n```\s*",
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
    """Fence REPL transcripts, keep notation as code, repair closed inline tokens, then
    split calculations."""
    if not text:
        return text
    prose = code_notation(fence_repl_transcripts(text))
    return layout_calculations(repair_inline_token_boundaries(prose))
