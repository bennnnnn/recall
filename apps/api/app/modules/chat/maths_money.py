"""A sum of money set in a word or bold group inside maths: ``$M \\approx \\textbf{\\$773}$``.

A loan reply (the owner's chat, 2026-11-22) ended its working on that line, and the phone
drew it "M ≈ {\\773}$ per month": the group's escaped dollar ended the formula, its brace
was left open, and the rest showed as source. A sum of money is no maths to draw. At the
end of a formula it leaves the maths as the price it is, bold when it was bold
(``$M \\approx$ **$773**``); anywhere else it loses only its group (``\\$773``), the escaped
dollar the phone reads as the sign. A line the phone would then pair differently keeps the
second form, and a line with no such group is left as written. Code, fences and display
maths are not touched.
"""

from __future__ import annotations

import re

from app.modules.chat.inline_code import read_inline_code_span
from app.modules.chat.markdown_regions import leave_prose_line, map_prose_outside_fences
from app.modules.chat.math_padding import maths_pair_end

# A word or bold group holding only an escaped dollar and an amount: "\textbf{\$773}",
# "\mathbf{\$1{,}720.50}", "\text{ \$40,000 }". Linear: each piece is one character class.
MONEY_GROUP = re.compile(
    r"\\(textbf|mathbf|boldsymbol|bm|text|textrm|textnormal|mathrm|mbox)[ \t]*+\{[ \t]*+"
    r"\\\$[ \t]*+(\d(?:[\d.,]|\{,\})*+)[ \t]*+\}"
)
_BOLD = frozenset({"textbf", "mathbf", "boldsymbol", "bm"})


def money_out_of_maths(text: str) -> str:
    """The reply with each sum of money in a word or bold group taken out of its maths."""
    if "\\$" not in text:
        return text
    return map_prose_outside_fences(text, _prose)


def _prose(prose: str) -> str:
    return "\n".join(
        line if leave_prose_line(line) or "\\$" not in line else _line(line)
        for line in prose.split("\n")
    )


def _spans(line: str) -> list[tuple[int, int]]:
    """Each ``$…$`` pair the phone reads in ``line``: (start, end). Code is no maths."""
    found: list[tuple[int, int]] = []
    index = 0
    while index < len(line):
        code_end = read_inline_code_span(line, index) if line[index] == "`" else None
        if code_end is not None:
            index = code_end
            continue
        end = maths_pair_end(line, index) if line[index] == "$" else None
        if end is None:
            index += 1
            continue
        found.append((index, end))
        index = end
    return found


def _line(line: str) -> str:
    spans = _spans(line)
    if not any(MONEY_GROUP.search(line, start, end) for start, end in spans):
        return line
    out: list[str] = []
    kept: list[str] = []
    cursor = 0
    for start, end in spans:
        out.append(line[cursor:start])
        written, body = _span(line[start + 1 : end - 1])
        out.append(written)
        if body is not None:
            kept.append(body)
        cursor = end
    out.append(line[cursor:])
    moved = "".join(out)
    if [line[s + 1 : e - 1] for s, e in _spans(moved)] == kept:
        return moved
    # The price beside the maths would pair with another dollar: keep it in the maths.
    return "".join(_ungrouped(line[s:e]) if i % 2 else line[s:e] for i, (s, e) in _pieces(line))


def _pieces(line: str) -> list[tuple[int, tuple[int, int]]]:
    """``line`` cut into prose and maths spans, alternately, maths at odd places."""
    pieces: list[tuple[int, int]] = []
    cursor = 0
    for start, end in _spans(line):
        pieces += [(cursor, start), (start, end)]
        cursor = end
    pieces.append((cursor, len(line)))
    return list(enumerate(pieces))


def _ungrouped(maths: str) -> str:
    return MONEY_GROUP.sub(lambda m: f"\\${m.group(2)}", maths)


def _span(body: str) -> tuple[str, str | None]:
    """The span as written once its sum of money is out, and the maths body it keeps (None
    when nothing is left of it)."""
    groups = list(MONEY_GROUP.finditer(body))
    if not groups:
        return f"${body}$", body
    last = groups[-1]
    if body[last.end() :].strip():
        inner = _ungrouped(body)
        return f"${inner}$", inner
    amount = "$" + last.group(2).replace("{,}", ",")
    price = f"**{amount}**" if last.group(1) in _BOLD else amount
    rest = _ungrouped(body[: last.start()]).rstrip()
    if not rest:
        return price, None
    return f"${rest}$ {price}", rest
