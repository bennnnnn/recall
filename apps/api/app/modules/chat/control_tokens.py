"""Chat-template control tokens a model leaks into its reply.

A provider's end-of-turn token is the model's own signal, never text for a reader: a
Grade 10 answer card ended "2 x 10^-8 s<|im_end|>" and the reply then ran "</|im_end|>"
for 1,100 lines, to the length limit (2026-10-30). The stream stops at a run of them
(``until_control_run``), and the saved reply loses every one (``strip_control_tokens``),
except where it quotes one as code for someone asking about them (`<|im_end|>` in
backticks, or inside a ```python block).
"""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator, AsyncIterator

from app.services.answer_fence import OWNED_FENCE_LANGS
from app.services.md_fence_scan import iter_fences

# "<|im_end|>", "</|im_end|>", "<|endoftext|>", "<|eot_id|>", and the full-width bar form
# one provider ends a sentence with.
_BAR = "\uff5c"
CONTROL_TOKEN = re.compile(rf"</?\|[a-z_]{{2,24}}\|>|<{_BAR}[^{_BAR}\n]{{1,40}}{_BAR}>")
# Two in a row: the model is no longer writing a reply.
_CONTROL_RUN = re.compile(rf"(?:(?:{CONTROL_TOKEN.pattern})\s*){{2,}}")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
# Fences whose body is the reply's own text, not code it quotes.
_TEXT_FENCES = frozenset({*OWNED_FENCE_LANGS, "", "text", "plain", "copy", "math", "latex", "tex"})
_BLANK_RUN = re.compile(r"\n(?:[ \t]*\n){2,}")
# Enough of the reply's end to hold a run split across tokens.
_TAIL = 160


def strip_control_tokens(text: str) -> str:
    """``text`` without control tokens outside quoted code, and without the blank lines a
    run of them leaves."""
    if CONTROL_TOKEN.search(text) is None:
        return text
    pieces: list[str] = []
    cursor = 0
    for fence in iter_fences(text):
        pieces.append(_without_tokens(text[cursor : fence.body_start]))
        body = text[fence.body_start : fence.body_end]
        pieces.append(CONTROL_TOKEN.sub("", body) if fence.lang in _TEXT_FENCES else body)
        cursor = fence.body_end
    pieces.append(_without_tokens(text[cursor:]))
    return "".join(pieces).rstrip() + ("\n" if text.endswith("\n") else "")


def _without_tokens(prose: str) -> str:
    """Prose without its control tokens; inline code keeps them."""
    pieces: list[str] = []
    cursor = 0
    for code in _INLINE_CODE.finditer(prose):
        pieces.append(CONTROL_TOKEN.sub("", prose[cursor : code.start()]))
        pieces.append(code.group(0))
        cursor = code.end()
    pieces.append(CONTROL_TOKEN.sub("", prose[cursor:]))
    return _BLANK_RUN.sub("\n\n", "".join(pieces))


async def until_control_run(tokens: AsyncIterator[str]) -> AsyncGenerator[str]:
    """``tokens`` until the reply runs into two control tokens in a row. The caller closes
    the provider's stream, so the rest of the run is neither shown nor paid for."""
    tail = ""
    async for token in tokens:
        yield token
        tail = (tail + token)[-_TAIL:]
        if _CONTROL_RUN.search(tail):
            return
