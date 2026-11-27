"""``$$`` display maths, as every reader reads it.

The phone's twin is apps/mobile/lib/markdown/displayDollars.ts, and
docs/fixtures/display_math_cases.json holds the two to one answer. remark-math's rule, as a
reader reads a price list:

- a delimiter is a run of exactly two unescaped dollars: three or more (``$$$``) are a price
  tier, never maths, and so is one in brackets (``($$)``);
- at the start of a line (after its indent, a quote mark or a list marker) it opens a formula
  that runs on over the lines below to the next ``$$``;
- mid-line it is maths as ``$$x$$``, nothing between the dollars and the formula, closed on
  the same line ("Californian, $$-$$$" and "Cafe - $$." are prices), or as a ``$$`` that ends
  a sentence's line ("Therefore: $$"), closed by a ``$$`` that starts a line before a blank
  line;
- a ``$$`` alone on its line, or with TeX after it, opens a block nothing but its closer ends:
  a line inside it that looks like a list item or a table row (``|x| < 5``, ``- 3x &= 2``) is
  maths. One with words after it ("$$ = moderate") or in a list item reads as prose: a list
  item or a table row ends it unclosed;
- a pair on a table row never spans a ``|``.

Inline code holds no maths: outside a formula a code span is skipped. The line's start, list
markers and bracketed tiers are read by loops, not patterns, so no run is read twice.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

from app.modules.chat.inline_code import escaped_at, read_inline_code_span

# The closer a line leaves awaited, or none:
# - "$$": a block nothing but its closer ends;
# - "$$ ": a formula opened in prose; a list item or a table row ends it unclosed;
# - "$$\n": a formula opened at a line's end; only a ``$$`` that starts a line closes it, and
#   a blank line, a list item or a table row ends it unclosed;
# - "\\]": ``\[ … \]`` maths (read only when brackets are).
Closer = Literal["$$", "$$ ", "$$\n", "\\]"] | None
# What a scan reports: a formula opened, closed, or one left open dropped (offset -1).
Emit = Callable[[str, int], None]

_DOLLARS = frozenset({"$$", "$$ ", "$$\n"})
# Something a formula is made of; a dash or ", " between two dollar pairs is not one.
_FORMULA_CHAR = re.compile(r"[A-Za-z0-9\\]")
# Text after an opening ``$$`` that is TeX, not words.
_TEX = re.compile(r"[\\^_{}]")
# What the scan stops at: a dollar, a backslash, or a backtick that may open code.
_MARK = re.compile(r"[$\\`]")
_DOLLAR_OR_SLASH = re.compile(r"[$\\]")


def awaits_dollars(closer: Closer) -> bool:
    """Awaiting a ``$$`` closer, of any kind."""
    return closer in _DOLLARS


def _after_blanks(text: str, at: int = 0) -> int:
    while at < len(text) and text[at] in " \t":
        at += 1
    return at


def _after_list_marker(text: str, at: int) -> int:
    """After a list marker at ``at`` and the blanks it needs (``-``, ``*``, ``+``, ``1.``); or -1."""
    end = at
    if end < len(text) and text[end] in "-*+":
        end += 1
    else:
        while end - at < 9 and end < len(text) and "0" <= text[end] <= "9":
            end += 1
        if end == at or end >= len(text) or text[end] not in ".)":
            return -1
        end += 1
    blanks = _after_blanks(text, end)
    return blanks if blanks > end else -1


def _line_start(prefix: str) -> Literal["line", "item"] | None:
    """Whether ``prefix`` (a line's text before a delimiter) is the line's start."""
    at = _after_blanks(prefix)
    while at < len(prefix) and prefix[at] == ">":
        at += 1
        if at < len(prefix) and prefix[at] in " \t":
            at += 1
    if at == len(prefix):
        return "line"
    return "item" if _after_list_marker(prefix, at) == len(prefix) else None


def _starts_item_or_row(line: str) -> bool:
    """A list item or a table row: a formula opened in prose ends before it."""
    at = _after_blanks(line)
    return (at < len(line) and line[at] == "|") or _after_list_marker(line, at) > 0


def _run_end(text: str, at: int) -> int:
    end = at
    while end < len(text) and text[end] == "$":
        end += 1
    return end


def _bracketed_tier(line: str, start: int, end: int) -> bool:
    """A price tier in brackets, ``( $$ )``: no delimiter."""
    before = start - 1
    while before >= 0 and line[before].isspace():
        before -= 1
    after = end
    while after < len(line) and line[after].isspace():
        after += 1
    return before >= 0 and line[before] == "(" and after < len(line) and line[after] == ")"


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


def _line_opener(line: str, end: int, start: Literal["line", "item"]) -> Closer:
    """The formula a ``$$`` at the start of a line opens: a block, or one read as prose."""
    rest = line[end:].strip()
    return "$$" if start == "line" and (not rest or _TEX.search(rest)) else "$$ "


def _ends_unclosed(line: str, closer: Closer) -> bool:
    """Whether ``line`` ends a formula ``closer`` awaits, unclosed, before it is read."""
    if closer == "$$ ":
        return _starts_item_or_row(line)
    if closer == "$$\n":
        return not line.strip() or _starts_item_or_row(line)
    return False


def _dollar_mark(
    line: str, at: int, end: int, closer: Closer, table: bool, emit: Emit | None
) -> tuple[Closer, int]:
    """Read the run of two dollars at ``at``: the closer after it and where the scan goes on."""
    start = _line_start(line[:at])
    if awaits_dollars(closer):
        # A formula opened at a line's end closes only at a line's start.
        if closer != "$$\n" or start:
            if emit:
                emit("close", at)
            return None, end
        return closer, end
    if start:
        if emit:
            emit("open", at)
        return _line_opener(line, end, start), end
    if (close := _tight_closer(line, end, table)) is not None:
        if emit:
            emit("open", at)
            emit("close", close)
        return closer, close + 2
    if not line[end:].strip():
        if emit:
            emit("open", at)
        return "$$\n", end
    return closer, end


def scan_display_line(
    line: str,
    before: Closer,
    brackets: bool = False,
    emit: Emit | None = None,
) -> Closer:
    """The closer still awaited after ``line``, given the one awaited before it.

    With ``brackets``, ``\\[ … \\]`` is read too (a ``$$`` inside one is its text). ``emit``
    hears each ``$$`` delimiter by its offset in the line, and a formula a line ended
    unclosed. It jumps from one mark to the next: read a character at a time in Python, a
    reply of 200,000 dots spent 0.14 s here per pass (2026-11-13).
    """
    closer = before
    if _ends_unclosed(line, closer):
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
            if end - at == 2 and closer != "\\]" and not _bracketed_tier(line, at, end):
                closer, index = _dollar_mark(line, at, end, closer, table, emit)
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


def find_display_dollars(text: str) -> list[tuple[int, int]]:
    """Each display formula in ``text`` (prose, no fences): its start and the end past its ``$$``."""
    spans: list[tuple[int, int]] = []
    closer: Closer = None
    open_at = [-1]
    line_start = 0
    for line in text.split("\n"):

        def heard(kind: str, at: int, offset: int = line_start) -> None:
            if kind == "open":
                open_at[0] = offset + at
            elif kind == "close":
                spans.append((open_at[0], offset + at + 2))

        closer = scan_display_line(line, closer, emit=heard)
        line_start += len(line) + 1
    return spans


def math_spans(text: str, others: re.Pattern[str]) -> list[tuple[int, int]]:
    """The maths a pass leaves alone in ``text``: each ``$$`` formula and each match of
    ``others`` (code, ``$…$``), left to right, none inside another."""
    dollars = find_display_dollars(text)
    spans: list[tuple[int, int]] = []
    at = 0
    following = 0
    while at <= len(text):
        while following < len(dollars) and dollars[following][0] < at:
            following += 1
        match = others.search(text, at)
        dollar = dollars[following] if following < len(dollars) else None
        if match is None and dollar is None:
            break
        if match is not None and (dollar is None or match.start() < dollar[0]):
            span = (match.start(), max(match.end(), match.start() + 1))
        elif dollar is not None:
            span = dollar
        else:
            break
        spans.append(span)
        at = span[1]
    return spans


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
