"""The display-maths scan jumps from mark to mark and finds what the character scan finds.

Read a character at a time in Python, a reply of 200,000 dots spent 0.14 s per pass in it,
and two passes read each line (``lead_lines`` joined ``math_padding``): CI ran the 0.5 s
presentation test past its limit (2026-11-13). The character scan below is the phone's
(apps/mobile/lib/markdown/displayDollars.ts, ``scanDisplayLine``) line for line.
"""

from __future__ import annotations

import itertools
import random
import re

import pytest

from app.modules.chat.display_dollars import Closer, scan_display_line
from app.modules.chat.inline_code import read_inline_code_span

_LINE_START = re.compile(r"[ \t]*(?:>[ \t]?)*(?:(?:[-*+]|[0-9]{1,9}[.)])[ \t]+)?")
_ENDS_FORMULA = re.compile(r"[ \t]*(?:(?:[-*+]|[0-9]{1,9}[.)])[ \t]|\|)")


def _run_end(line: str, at: int) -> int:
    while at < len(line) and line[at] == "$":
        at += 1
    return at


def _tier(line: str, start: int, end: int) -> bool:
    return bool(re.search(r"\(\s*\Z", line[:start])) and bool(re.match(r"\s*\)", line[end:]))


def _tight(line: str, start: int, table: bool) -> int | None:
    if start >= len(line) or line[start].isspace() or line[start] == "$":
        return None
    slashes = 0
    index = start
    while index < len(line):
        if line[index] == "$" and slashes % 2 == 0:
            end = _run_end(line, index)
            if end - index != 2:
                if end - index > 2:
                    return None
                index, slashes = end, 0
                continue
            body = line[start:index]
            if (
                body[-1:].isspace()
                or not re.search(r"[A-Za-z0-9\\]", body)
                or _tier(line, index, end)
            ):
                return None
            return None if table and "|" in body else index
        slashes = slashes + 1 if line[index] == "\\" else 0
        index += 1
    return None


def _by_character(line: str, closer: Closer) -> Closer:
    """The phone's scan, one character at a time, counting backslashes as it passes them."""
    if closer == "$$" and _ENDS_FORMULA.match(line):
        closer = None
    if "$" not in line and "\\" not in line:
        return closer
    table = line.lstrip().startswith("|")
    index = 0
    slashes = 0
    while index < len(line):
        char = line[index]
        code_end = read_inline_code_span(line, index) if closer is None and char == "`" else None
        if code_end is not None:
            index, slashes = code_end, 0
            continue
        if char == "$" and slashes % 2 == 0:
            end = _run_end(line, index)
            if end - index == 2 and closer != "\\]" and not _tier(line, index, end):
                if closer == "$$":
                    closer = None
                elif _LINE_START.fullmatch(line[:index]):
                    closer = "$$"
                elif (close := _tight(line, end, table)) is not None:
                    index, slashes = close + 2, 0
                    continue
            index, slashes = end, 0
            continue
        if char == "\\" and slashes % 2 == 0:
            following = line[index + 1 : index + 2]
            if following == "[" and closer is None:
                closer, index, slashes = "\\]", index + 2, 0
                continue
            if following == "]" and closer == "\\]":
                closer, index, slashes = None, index + 2, 0
                continue
        slashes = slashes + 1 if char == "\\" else 0
        index += 1
    return closer


_PIECES = [
    "$",
    "$$",
    "$$$",
    "\\",
    "\\\\",
    "[",
    "]",
    "`",
    "``",
    "a",
    " ",
    "x = 1",
    "- ",
    "(",
    ")",
    "|",
]
_CLOSERS: list[Closer] = [None, "$$", "\\]"]


def test_every_short_line_of_marks_ends_as_the_character_scan() -> None:
    for size in range(1, 5):
        for pieces in itertools.product(_PIECES, repeat=size):
            line = "".join(pieces)
            for closer in _CLOSERS:
                assert scan_display_line(line, closer, True) == _by_character(line, closer), (
                    line,
                    closer,
                )


def test_long_random_lines_end_as_the_character_scan() -> None:
    chosen = random.Random(2026_11_13)  # noqa: S311 - a fixed sample, not a secret
    for _ in range(4000):
        line = "".join(chosen.choice(_PIECES) for _ in range(chosen.randint(1, 40)))
        closer = chosen.choice(_CLOSERS)
        assert scan_display_line(line, closer, True) == _by_character(line, closer), (line, closer)


@pytest.mark.wall_clock
def test_a_long_line_with_one_mark_is_read_in_one_search() -> None:
    import time

    line = "$x = 1$" + "." * 200_000
    started = time.perf_counter()
    for _ in range(10):
        scan_display_line(line, None, True)
    assert time.perf_counter() - started < 0.1
