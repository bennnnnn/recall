"""A formula the model put in a plain code block is a line of the reply, not code.

Worked chemistry and gas-law steps came as ``` blocks with no language
(2026-10-24): "2h₂ + o₂ → 2h₂o", "moles of h₂ = 4.0 g ÷ 2.02 g/mol = 1.98 mol",
"p₁v₁ = p₂v₂". The phone drew each as a grey code card in a monospace font. A block
with no language that holds one to three short lines, each an equation or a reaction
written with the signs of typeset maths (subscripts, superscripts, arrows, times and
division signs, roots), is written as plain lines instead. Plain ASCII stays a code block
whatever it holds (``PORT=8000``, ``count += 1``, ``UPDATE users SET active = 1``), as
does a block with a language, a line with code's marks, and a line markdown would turn
into a heading or a list item.
"""

from __future__ import annotations

import re

from app.modules.chat.inline_code import read_inline_code_span
from app.services.md_fence_scan import Fence, block_end, line_fences, map_fence_blocks

_MAX_LINES = 3
_MAX_CHARS = 90
_EQUATION = re.compile("=|\u2192|\u21cc|\u00f7|\u00d7")
# Subscripts, superscripts and maths signs make a line a formula, never code: "p₁v₁ = p₂v₂".
_MATH_SIGNS = re.compile(
    "[\u2080-\u2089\u2070-\u2079\u00b2\u00b3\u00b9\u2192\u21cc\u00f7\u00d7\u221a\u03c0]"
)
# Marks no typeset formula carries, even beside a subscript.
_CODE = re.compile(
    r"[;{}`]|==|=>|//|\b(?:def|return|import|print|const|let|var|function|class)\b",
    re.IGNORECASE,
)
# Out of its fence, markdown would read this line as a heading, a list or a quote.
_BLOCK_START = re.compile(r"^(?:#|[-*+>]\s|\d+[.)]\s)")


def _formula_lines(body: str) -> list[str] | None:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not 1 <= len(lines) <= _MAX_LINES:
        return None
    for line in lines:
        if len(line) > _MAX_CHARS or not _EQUATION.search(line):
            return None
        if not _MATH_SIGNS.search(line) or _CODE.search(line) or _BLOCK_START.match(line):
            return None
    return lines


def unfence_formulas(text: str) -> str:
    """Each plain code block holding only a short formula, as plain lines."""
    if "```" not in text:
        return text

    def replace(fence: Fence, body: str) -> str:
        lines = None if fence.lang or fence.opener.prefix.strip() else _formula_lines(body)
        if lines is None:
            return text[fence.start : block_end(text, fence)]
        indent = fence.opener.prefix
        lead = "\n" if fence.start else ""
        # A blank line after it too, so the next line is not joined to the formula.
        end = block_end(text, fence)
        tail = "\n" if end < len(text) and not text.startswith("\n\n", end) else ""
        return lead + "\n\n".join(f"{indent}{line}" for line in lines) + tail

    return map_fence_blocks(text, replace)


# A maths span the model wrapped in inline code showed its source in a grey code box
# (2026-10-25): "`$14,000 + (14,000 \times 0.07) = 14,980$`", "`$M = 11,980 \times
# 0.020143$`". A code span outside fenced code that is one ``$…$`` (or ``$$…$$``) span and
# nothing else is that maths. Asked how to write it ("how do I type a fraction in LaTeX?"),
# the source is the answer, and every code span stays.
_DOLLAR_MATHS = re.compile(r"(\${1,2})(?!\s)[^$`\n]+(?<!\s)\1")
_ASKS_FOR_SOURCE = re.compile(
    r"\b(?:latex|katex|mathjax|overleaf|tex|markdown|typeset|syntax|source|code|type|write)\b",
    re.IGNORECASE,
)


def unwrap_code_maths(text: str, request: str | None) -> str:
    """Each inline code span that is only a maths span, as that maths."""
    if "`$" not in text or (request and _ASKS_FOR_SOURCE.search(request)):
        return text
    lines = text.split("\n")
    for index, (line, fence) in enumerate(zip(lines, line_fences(text), strict=True)):
        if fence is None and "`$" in line:
            lines[index] = _unwrapped(line)
    return "\n".join(lines)


def _unwrapped(line: str) -> str:
    out: list[str] = []
    at = 0
    while (tick := line.find("`", at)) >= 0:
        end = read_inline_code_span(line, tick)
        if end is None:
            out.append(line[at : tick + 1])
            at = tick + 1
            continue
        span = line[tick:end]
        body = span.strip("`")
        maths = body.strip()
        out.append(line[at:tick])
        out.append(maths if body == maths and _DOLLAR_MATHS.fullmatch(maths) else span)
        at = end
    out.append(line[at:])
    return "".join(out)
