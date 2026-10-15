"""Inline code and inline maths stay apart before a reply is saved.

Mirrors apps/mobile/lib/__tests__/inlineCodeMath.test.ts: the phone and the
server must make the same call, because the server's presented text replaces
the streamed one when the turn finishes.
"""

from __future__ import annotations

import pytest

from app.modules.chat.inline_code import code_span_opens_within, read_inline_code_span
from app.modules.chat.presentation import present_assistant_markdown

REPORTED = (
    "- **Iteration 1**: `n` is $2$. `total += n` means `total = total + n`. "
    "So, `total` becomes $0 + 2 = 2$."
)


@pytest.mark.parametrize(
    "line",
    [
        REPORTED,
        "**Line 1:** `total = 0`\nCreates a variable `total` and sets it to `0`.",
        "`total` is `$5` and `x$` then $y = 2$.",
        "Each loop adds `n` to `total`: $2 + 4 + 6 = 12$.",
        "It costs $5 and the tip is $10.",
    ],
)
def test_presentation_leaves_code_and_maths_as_written(line: str) -> None:
    assert present_assistant_markdown(line) == line


def test_a_code_span_is_read_like_markdown_it() -> None:
    text = "a `b` c ``d ` e`` f `g"
    assert read_inline_code_span(text, 2) == 5
    assert read_inline_code_span(text, 8) == 17
    assert read_inline_code_span(text, text.rindex("`")) is None
    assert code_span_opens_within(text, 0, 4)
    assert not code_span_opens_within("no code here", 0, 12)
