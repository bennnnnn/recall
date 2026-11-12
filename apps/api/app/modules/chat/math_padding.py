"""Inline maths written with a space inside its dollars: "$2x $", "$ x$".

A reply on 2026-11-06 said "one factor starts with $2x $ and the other with $ x$". A
renderer that follows pandoc's rule (no space after the opening dollar, none before the
closing one) shows those as text with stray dollars. Only a span the phone draws as maths
is trimmed: its pairing is read here as ``apps/mobile/lib/markdown/inlineMath.ts`` reads
it, so a price ("$5 and $10", "$38.40 = $ 19.20") and prose between two dollars stay as
written. Code, fences, display maths and quotes are left alone.
"""

from __future__ import annotations

import re

from app.modules.chat.inline_code import code_span_opens_within, escaped_at, read_inline_code_span
from app.modules.chat.markdown_regions import leave_prose_line, map_prose_outside_fences

# The phone's rules (inlineMath.ts): a digit or a spaced amount after the closer is a price,
# a body that opens with an amount and goes on in words is one, and two words of three
# letters or more (outside a sub- or superscript) are prose. A TeX command makes it maths.
# An exclamation mark and a space end a price's clause too, unless an operator or a number
# goes on: then, like one that ends the span, it is a factorial (`$4!$`, `$4! + 3!$`).
_PRICE_LEAD = re.compile(
    r"\d[\d,.]*+(?:[kKmMbB]|/[A-Za-z]++)?"
    r"(?:[;:?](?:\s|$)|!\s++(?![\s=+\-\u2212\u00d7\u00f7*/\u00b7^<>\u2264\u2265\u2260)\d])"
    r"|\s++([A-Za-z]++)(.*))",
    re.DOTALL,
)
_MATH_WORD = re.compile(r"[a-z]|sin|cos|tan|sec|csc|cot|log|ln|exp|lim|max|min", re.IGNORECASE)
_TEX_COMMAND = re.compile(r"\\[A-Za-z]")
_LABEL = re.compile(r"[_^]\{[^{}]*\}")
_LONG_WORD = re.compile(r"[A-Za-z]{3,}")


def without_math_padding(text: str) -> str:
    """The reply with each padded inline ``$…$`` maths span trimmed to its maths."""
    if "$" not in text:
        return text
    return map_prose_outside_fences(text, _trim_prose)


def _trim_prose(prose: str) -> str:
    return "\n".join(
        line if leave_prose_line(line) or "$" not in line else _trim_line(line)
        for line in prose.split("\n")
    )


def _trim_line(line: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(line):
        code_end = read_inline_code_span(line, index) if line[index] == "`" else None
        end = code_end if code_end is not None else _maths_end(line, index)
        if end is None:
            out.append(line[index])
            index += 1
            continue
        span = line[index:end]
        out.append(span if code_end is not None else f"${span[1:-1].strip()}$")
        index = end
    return "".join(out)


def _maths_end(line: str, start: int) -> int | None:
    """The end of the ``$…$`` maths span opening at ``start``, as the phone pairs it."""
    if line[start] != "$" or line[start - 1 : start] == "$" or line[start + 1 : start + 2] == "$":
        return None
    if escaped_at(line, start):
        return None
    end = line.find("$", start + 1)
    while end >= 0 and escaped_at(line, end):
        end = line.find("$", end + 1)
    if end < 0:
        return None
    body = line[start + 1 : end]
    if not body.strip() or code_span_opens_within(line, start + 1, end):
        return None
    if _opens_price(line, end, body) or _price_body(body) or _prose(body):
        return None
    return end + 1


def _opens_price(line: str, dollar: int, body: str) -> bool:
    if line[dollar + 1 : dollar + 2].isdigit():
        return True
    if not line[dollar - 1 : dollar].isspace() or not body.lstrip()[:1].isdigit():
        return False
    # Spaces or tabs, then a digit: "$ 5". Scanned, not matched, so a long run is one pass.
    after = len(line) - len(line[dollar + 1 :].lstrip(" \t"))
    return after > dollar + 1 and line[after : after + 1].isdigit()


def _price_body(body: str) -> bool:
    if _TEX_COMMAND.search(body):
        return False
    # A span padded on its left ("$ 4! $") is read without its padding: the space before
    # its closer is padding, not the space after a price's "!" ("$5! $x$").
    lead = _PRICE_LEAD.match(body.strip() if body[:1].isspace() else body.lstrip())
    if lead is None:
        return False
    word, rest = lead.group(1), lead.group(2) or ""
    if word is None or not _MATH_WORD.fullmatch(word):
        return True
    return sum(1 for w in _LONG_WORD.findall(rest) if not _MATH_WORD.fullmatch(w)) >= 2


def _prose(body: str) -> bool:
    if _TEX_COMMAND.search(body):
        return False
    return len(_LONG_WORD.findall(_LABEL.sub(" ", body))) >= 2
