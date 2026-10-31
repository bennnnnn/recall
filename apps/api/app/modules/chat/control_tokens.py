"""Chat-template control tokens a model leaks into its reply.

A provider's end-of-turn token is the model's own signal, never text for a reader: a
Grade 10 answer card ended "2 x 10^-8 s<|im_end|>" and the reply then ran "</|im_end|>"
for 1,100 lines, to the length limit (2026-10-30). A reply about chat templates writes the
same tokens on purpose, so only a leak's own shape is acted on: a token ending the reply or
an answer card, or one token over and over. Code a reply quotes (a fence, `inline` code) is
never touched.
"""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator, AsyncIterator

from app.services.answer_fence import OWNED_FENCE_LANGS
from app.services.md_fence_scan import iter_fences, last_fence

# "<|im_end|>", "</|im_end|>", "<|endoftext|>", "<|eot_id|>", and the full-width bar form
# one provider ends a sentence with.
_BAR = chr(0xFF5C)
_TOKEN = rf"</?\|[a-z_]{{2,24}}\|>|<{_BAR}[^{_BAR}\n]{{1,40}}{_BAR}>"
CONTROL_TOKEN = re.compile(_TOKEN)
# One token over and over: the model is no longer writing a reply.
_RUN = re.compile(rf"({_TOKEN})(?:\s*\1){{2,}}")
# A token a stretch of reply text ends on: the reply's last line, or an answer card's.
_ENDING = re.compile(rf"(?:{_TOKEN})\s*\Z")
_INLINE_CODE = re.compile(r"``[^\n]*?``|`[^`\n]*`")
_BLANK_RUN = re.compile(r"\n(?:[ \t]*\n){2,}")


def _reply_parts(text: str) -> list[tuple[str, bool]]:
    """The reply in order as (piece, is_reply_text): prose and the app's own cards are
    its text; any other fence is code it quotes."""
    parts: list[tuple[str, bool]] = []
    cursor = 0
    for fence in iter_fences(text):
        parts.append((text[cursor : fence.body_start], True))
        parts.append((text[fence.body_start : fence.body_end], fence.lang in OWNED_FENCE_LANGS))
        cursor = fence.body_end
    parts.append((text[cursor:], True))
    return parts


def _outside_inline_code(piece: str) -> str:
    return _INLINE_CODE.sub(lambda code: " " * len(code.group(0)), piece)


def strip_control_tokens(text: str) -> str:
    """``text`` without a leak's control tokens and the blank lines a run of them leaves;
    a reply that only quotes them, or writes them in code, is left as it is."""
    if CONTROL_TOKEN.search(text) is None:
        return text
    parts = _reply_parts(text)
    own_text = [_outside_inline_code(piece) for piece, own in parts if own]
    visible = "\n".join(own_text)
    if _RUN.search(visible) is None and not any(_ENDING.search(piece) for piece in own_text):
        return text
    cleaned = "".join(_strip_piece(piece) if own else piece for piece, own in parts)
    return cleaned.rstrip() + ("\n" if text.endswith("\n") else "")


def _strip_piece(piece: str) -> str:
    """One stretch of reply text without its control tokens; inline code keeps them."""
    pieces: list[str] = []
    cursor = 0
    for code in _INLINE_CODE.finditer(piece):
        pieces.append(CONTROL_TOKEN.sub("", piece[cursor : code.start()]))
        pieces.append(code.group(0))
        cursor = code.end()
    pieces.append(CONTROL_TOKEN.sub("", piece[cursor:]))
    return _BLANK_RUN.sub("\n\n", "".join(pieces))


async def until_control_run(tokens: AsyncIterator[str]) -> AsyncGenerator[str]:
    """``tokens`` until one control token repeats outside code; the rest of the stream is
    read but not shown, so the provider's usage, model and tool calls are still recorded."""
    text = ""
    ran = False
    async for token in tokens:
        if ran:
            continue
        text += token
        run = _RUN.search(text, max(0, len(text) - len(token) - 200))
        if run is not None and not _in_open_fence(text[: run.start()]):
            ran = True
            continue
        yield token


def _in_open_fence(text: str) -> bool:
    fence = last_fence(text)
    return fence is not None and not fence.closed
