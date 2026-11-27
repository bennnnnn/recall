"""``$$`` display maths, as every reader reads it.

The phone's twin is apps/mobile/lib/markdown/displayDollars.ts, and
docs/fixtures/display_math_cases.json holds the two to one answer. remark-math's rule, as a
reader reads a price list:

- a delimiter is a run of exactly two unescaped dollars: three or more (``$$$``) are a price
  tier, never maths, and so is one in brackets (``($$)``);
- it opens display maths at the start of a line (after its indent, a quote mark or a list
  marker), and the formula may run on over the lines below to the next ``$$``;
- mid-line it is maths only as ``$$x$$``, nothing between the dollars and the formula, closed
  on the same line ("Californian, $$-$$$" and "Cafe - $$." are prices);
- a formula never reaches across a list item or a table row, and a pair on a table row never
  spans a ``|``.

Inline code holds no maths: outside a formula a code span is skipped.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

from app.modules.chat.inline_code import escaped_at, read_inline_code_span

Closer = Literal["$$", "\\]"] | None
# What a scan reports: a formula opened, closed, or one left open dropped (offset -1).
Emit = Callable[[str, int], None]

# A line's text before a delimiter that still counts as the line's start.
_LINE_START = re.compile(r"[ \t]*(?:>[ \t]?)*(?:(?:[-*+]|[0-9]{1,9}[.)])[ \t]+)?")
# A line that starts a list item or a table row: an open formula ends before it.
_ENDS_FORMULA = re.compile(r"[ \t]*(?:(?:[-*+]|[0-9]{1,9}[.)])[ \t]|\|)")
# Something a formula is made of; a dash or ", " between two dollar pairs is not one.
_FORMULA_CHAR = re.compile(r"[A-Za-z0-9\\]")
_TIER_BEFORE = re.compile(r"\(\s*\Z")
_TIER_AFTER = re.compile(r"\s*\)")
# What the scan stops at: a dollar, a backslash, or a backtick that may open code.
_MARK = re.compile(r"[$\\`]")
_DOLLAR_OR_SLASH = re.compile(r"[$\\]")


def _run_end(text: str, at: int) -> int:
    end = at
    while end < len(text) and text[end] == "$":
        end += 1
    return end


def _bracketed_tier(line: str, start: int, end: int) -> bool:
    """A price tier in brackets, ``( $$ )``: no delimiter."""
    return bool(_TIER_BEFORE.search(line, 0, start)) and bool(_TIER_AFTER.match(line, end))


def _tight_closer(line: str, start: int, table: bool) -> int | None:
    """The closer of a ``$$x$$`` pair whose opener ends at ``start``, on the same line."""
    if start >= len(line) or line[start].isspace() or line[start] == "$":
        return None
    index = start
    slashes = 0
    while (found := _DOLLAR_OR_SLASH.search(line, index)) is not None:
        at = found.start()
        if at > index:
            slashes = 0
        if line[at] == "\\":
            slashes += 1
            index = at + 1
            continue
        if slashes % 2:
            slashes = 0
            index = at + 1
            continue
        end = _run_end(line, at)
        if end - at != 2:
            # A lone dollar may sit inside the formula; a longer run ends the hope of one.
            if end - at > 2:
                return None
            index, slashes = end, 0
            continue
        body = line[start:at]
        if body[-1:].isspace() or not _FORMULA_CHAR.search(body) or _bracketed_tier(line, at, end):
            return None
        if table and "|" in body:
            return None
        return at
    return None


def scan_display_line(
    line: str,
    before: Closer,
    brackets: bool = False,
    emit: Emit | None = None,
) -> Closer:
    """The closer still awaited after ``line``, given the one awaited before it.

    With ``brackets``, ``\\[ … \\]`` is read too (a ``$$`` inside one is its text). ``emit``
    hears each ``$$`` delimiter by its offset in the line, and a formula a list item or table
    row ended unclosed. It jumps from one mark to the next: read a character at a time in
    Python, a reply of 200,000 dots spent 0.14 s here per pass (2026-11-13).
    """
    closer = before
    if closer == "$$" and _ENDS_FORMULA.match(line):
        closer = None
        if emit:
            emit("drop", -1)
    if "$" not in line and not (brackets and "\\" in line):
        return closer
    table = line.lstrip().startswith("|")
    index = 0
    # The backslashes just before ``index``: an odd run escapes the character there.
    slashes = 0
    while (found := _MARK.search(line, index)) is not None:
        at = found.start()
        if at > index:
            slashes = 0
        char = line[at]
        if char == "`":
            code_end = read_inline_code_span(line, at) if closer is None else None
            index, slashes = (code_end, 0) if code_end is not None else (at + 1, 0)
            continue
        if char == "$" and slashes % 2 == 0:
            end = _run_end(line, at)
            index, slashes = end, 0
            if end - at != 2 or closer == "\\]" or _bracketed_tier(line, at, end):
                continue
            if closer == "$$":
                closer = None
                if emit:
                    emit("close", at)
            elif _LINE_START.fullmatch(line, 0, at):
                closer = "$$"
                if emit:
                    emit("open", at)
            elif (close := _tight_closer(line, end, table)) is not None:
                if emit:
                    emit("open", at)
                    emit("close", close)
                index = close + 2
            continue
        if brackets and char == "\\" and slashes % 2 == 0:
            following = line[at + 1 : at + 2]
            if following == "[" and closer is None:
                closer, index, slashes = "\\]", at + 2, 0
                continue
            if following == "]" and closer == "\\]":
                closer, index, slashes = None, at + 2, 0
                continue
        slashes = slashes + 1 if char == "\\" else 0
        index = at + 1
    return closer


def display_dollar_pair_end(text: str, start: int) -> int | None:
    """The end of the ``$$`` formula whose opener is at ``start`` in ``text``.

    The formula is read from its line's start, so code spans and earlier pairs on the line
    are read as they are. None when no formula opens there, or it is not closed.
    """
    if not text.startswith("$", start) or escaped_at(text, start):
        return None
    if start > 0 and text[start - 1] == "$" and not escaped_at(text, start - 1):
        return None
    line_start = text.rfind("\n", 0, start) + 1
    closer: Closer = None
    state = {"opened": False, "dropped": False}
    found: list[int] = []
    while True:
        newline = text.find("\n", line_start)
        offset = line_start
        line = text[line_start : newline if newline >= 0 else len(text)]

        def heard(kind: str, at: int, offset: int = offset) -> None:
            if found or state["dropped"]:
                return
            if kind == "open" and not state["opened"]:
                state["opened"] = offset + at == start
            elif kind == "close" and state["opened"]:
                found.append(offset + at + 2)
            elif kind == "drop" and state["opened"]:
                state["dropped"] = True

        closer = scan_display_line(line, closer, emit=heard)
        if found:
            return found[0]
        if state["dropped"] or not state["opened"] or closer is None or newline < 0:
            return None
        line_start = newline + 1
