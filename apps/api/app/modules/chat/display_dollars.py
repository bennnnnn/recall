"""``$$`` display maths, as every reader reads it.

The phone's twin is apps/mobile/lib/markdown/displayDollars.ts, and
docs/fixtures/display_math_cases.json holds the two to one answer. remark-math's rule, as a
reader reads a price list:

- a delimiter is a run of exactly two unescaped dollars: three or more (``$$$``) are a price
  tier, never maths, and so is one in brackets (``($$)``) or one that ends a range
  (``$-$$``);
- at the start of a line (after its indent, a quote mark or a list marker) it opens a formula
  that runs on over the lines below to the next ``$$``;
- mid-line it is maths as ``$$x$$``, nothing between the dollars and the formula, or as a
  padded ``$$ x = 1 $$`` that reads as maths, closed on the same line ("Californian, $$-$$$"
  and "Cafe - $$." are prices); or as a ``$$`` that ends a sentence's line ("Therefore: $$"),
  closed by a ``$$`` that starts a line before a blank line;
- a ``$$`` alone on its line, or with TeX after it, opens a block nothing but its closer ends:
  a line inside it that looks like a list item or a table row (``|x| < 5``, ``- 3x &= 2``) is
  maths. One with words after it ("$$ = moderate") or in a list item reads as prose: a blank
  line, a list item or a table row ends it unclosed;
- a pair on a table row never spans a ``|``.

Inline code holds no maths: outside a formula a code span is skipped. The line's start, list
markers and bracketed tiers are read by loops, not patterns, so no run is read twice; each
line is read once, so a line of many pairs costs its length.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from app.modules.chat.inline_code import escaped_at, read_inline_code_span

# The closer a line leaves awaited, or none:
# - "$$": a block nothing but its closer ends;
# - "$$ ": a formula opened in prose; a blank line, a list item or a table row ends it
#   unclosed;
# - "$$\n": a formula opened at a line's end; only a ``$$`` that starts a line closes it, and
#   a blank line ends it unclosed;
# - "\\]": ``\[ … \]`` maths (read only when brackets are).
Closer = Literal["$$", "$$ ", "$$\n", "\\]"] | None
# What a scan reports: a formula opened, closed, or one left open dropped (offset -1).
Emit = Callable[[str, int], None]
StartKind = Literal["line", "item"] | None

_DOLLARS = frozenset({"$$", "$$ ", "$$\n"})
# Something a formula is made of, in any script ("π", "∞"); a dash or ", " is not one.
_FORMULA_CHAR = re.compile(r"[^\W_]|[\\∞]")
# Text after an opening ``$$`` that is TeX, not words.
_TEX = re.compile(r"[\\^_{}]")
# A mark only maths writes: a relation, a script, a command, a bar.
_MATH_MARK = re.compile(r"[=<>^_\\|]")
# A TeX group of words (``\text{Total cost}``, ``\mathrm{ m/s}``): a formula's unit or label.
_WORD_GROUP = re.compile(
    r"\\(?:text|textrm|textbf|textit|mathrm|mathbf|mathit|mbox|operatorname)\s*\{[^{}]*\}"
)
# A TeX command and the environment name after it (``\begin{aligned}``).
_COMMAND = re.compile(r"\\[A-Za-z]+(?:\{[A-Za-z*]*\})?")
_WORD = re.compile(r"[A-Za-z]{3,}")
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


def _line_starts(line: str) -> tuple[int, int]:
    """Where a delimiter stands at ``line``'s start: after its indent and quote marks, and
    after a list marker there too (-1 when there is none). Read once per line."""
    at = _after_blanks(line)
    while at < len(line) and line[at] == ">":
        at += 1
        if at < len(line) and line[at] in " \t":
            at += 1
    return at, _after_list_marker(line, at)


def _start_kind(starts: tuple[int, int], index: int) -> StartKind:
    if index == starts[0]:
        return "line"
    return "item" if index == starts[1] else None


def _last_text(line: str) -> int:
    """The last character of ``line`` that is not a blank, or -1."""
    at = len(line) - 1
    while at >= 0 and line[at].isspace():
        at -= 1
    return at


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


# A dash that joins two price tiers ("$-$$", "$$-$$$"), en and em dashes included.
_RANGE_DASHES = "-\u2013\u2014"
# What may come before a price tier: the line's start, a blank or an opening mark.
_TIER_BEFORE = " \t(,:;"


def _range_end(line: str, start: int) -> bool:
    """The run of two at ``start`` ends a price range, ``$-$$`` or ``$ - $$``: a dash before it
    and a tier before the dash that starts a word, with no blank between unless that tier is a
    lone ``$`` (never a delimiter). "Burmese, $-$$" at a line's end opened a formula there
    (2026-11-27)."""
    at = start - 1
    while at >= 0 and line[at] in " \t":
        at -= 1
    spaced = at < start - 1
    if at < 0 or line[at] not in _RANGE_DASHES:
        return False
    at -= 1
    dash = at
    while at >= 0 and line[at] in " \t":
        at -= 1
    if at < 0 or line[at] != "$":
        return False
    first = at
    while first > 0 and line[first - 1] == "$":
        first -= 1
    # A tier starts a word: "$a$ - $$b$$" closes a formula with its "$", which is no tier.
    if first > 0 and line[first - 1] not in _TIER_BEFORE:
        return False
    return first == at or (not spaced and at == dash)


def _prose_words(text: str) -> int:
    """Words of three letters or more, TeX aside (word groups whatever they hold, commands and
    their environment names): "a night, and suites" holds two, "v = 20 \\text{ meters per
    second}" none."""
    return len(_WORD.findall(_COMMAND.sub(" ", _WORD_GROUP.sub(" ", text))))


def _padded_formula(body: str) -> bool:
    """A padded mid-line pair's text that is a formula: a maths mark, and words at most one."""
    return _MATH_MARK.search(body) is not None and _prose_words(body) < 2


def _tight_closer(line: str, start: int, table: bool) -> int | None:
    """The closer of a mid-line pair whose opener ends at ``start``, on the same line.

    Tight on both sides (``$$x$$``, ``$$π$$``), any formula; padded on either side
    (``$$ x = 1 $$``, ``$$x = 1 $$``), only one that reads as maths, not words ("Rooms are $$ a
    night, and suites $$ more.", "$$, and Zuni $$").
    """
    if start >= len(line) or line[start] == "$":
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
        if not _FORMULA_CHAR.search(body) or _bracketed_tier(line, at, end):
            return None
        padded = body[:1].isspace() or body[-1:].isspace()
        if padded and not _padded_formula(body):
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
    """Whether ``line`` ends a formula ``closer`` awaits, unclosed, before it is read.

    One opened in prose ends at a blank line, a list item or a table row; one opened at a
    line's end, whose formula lines may start like a row or an item ("|x - 3| < 5",
    "+ 2x + 1"), at a blank line.
    """
    if closer == "$$ ":
        return not line.strip() or _starts_item_or_row(line)
    if closer == "$$\n":
        return not line.strip()
    return False


@dataclass(slots=True)
class _Line:
    """What a scan knows of its line before reading any delimiter on it."""

    text: str
    table: bool
    starts: tuple[int, int]
    last: int


def _dollar_mark(
    line: _Line, at: int, end: int, closer: Closer, emit: Emit | None
) -> tuple[Closer, int]:
    """Read the run of two dollars at ``at``: the closer after it and where the scan goes on."""
    start = _start_kind(line.starts, at)
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
        return _line_opener(line.text, end, start), end
    if (close := _tight_closer(line.text, end, line.table)) is not None:
        if emit:
            emit("open", at)
            emit("close", close)
        return closer, close + 2
    if end > line.last:
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
    read = _Line(line, line.lstrip().startswith("|"), _line_starts(line), _last_text(line))
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
            if (
                end - at == 2
                and closer != "\\]"
                and not _bracketed_tier(line, at, end)
                and not _range_end(line, at)
            ):
                closer, index = _dollar_mark(read, at, end, closer, emit)
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


@dataclass(slots=True)
class _Reading:
    """What one read of a text found: each formula's end by its start."""

    text: str
    ends: dict[int, int] = field(default_factory=dict)


def _read_text(text: str) -> _Reading:
    """Read ``text`` (prose, no fences) once, line by line, carrying what each line leaves open."""
    reading = _Reading(text)
    closer: Closer = None
    open_at = [-1]
    line_start = 0
    for line in text.split("\n"):

        def heard(kind: str, at: int, offset: int = line_start) -> None:
            if kind == "open":
                open_at[0] = offset + at
            elif kind == "close":
                reading.ends[open_at[0]] = offset + at + 2

        closer = scan_display_line(line, closer, emit=heard)
        line_start += len(line) + 1
    return reading


# The last text read, kept while a reader asks about each of its ``$$`` in turn: an inline
# reader asks once per delimiter, so one read serves a line of many pairs.
_last_reading: list[_Reading] = []


def _reading(text: str) -> _Reading:
    if not _last_reading or _last_reading[0].text is not text:
        _last_reading[:] = [_read_text(text)]
    return _last_reading[0]


def find_display_dollars(text: str) -> list[tuple[int, int]]:
    """Each display formula in ``text`` (prose, no fences): its start and the end past its ``$$``."""
    return list(_read_text(text).ends.items())


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

    Read as the whole text reads, once for all its delimiters (an inline reader asks about
    each in turn), so code spans and earlier pairs are read as they are. None when no formula
    opens there, or it is not closed.
    """
    if not text.startswith("$", start) or escaped_at(text, start):
        return None
    return _reading(text).ends.get(start)
