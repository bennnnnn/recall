"""The display-maths scan jumps from mark to mark and finds what the character scan finds.

Read a character at a time in Python, a reply of 200,000 dots spent 0.14 s per pass in it,
and two passes read each line (``lead_lines`` joined ``math_padding``): CI ran the 0.5 s
presentation test past its limit (2026-11-13). The character scan below is the phone's
(apps/mobile/lib/markdown/displayDollars.ts, ``scanDisplayLine``) line for line; the rules
for one run of dollars are the module's own, so this holds the jumping, not the rule.
"""

from __future__ import annotations

import itertools
import random

import pytest

from app.modules.chat import display_dollars
from app.modules.chat.display_dollars import Closer, scan_display_line
from app.modules.chat.inline_code import read_inline_code_span


def _by_character(line: str, closer: Closer) -> Closer:
    """The phone's scan, one character at a time, counting backslashes as it passes them."""
    if display_dollars._ends_unclosed(line, closer):
        closer = None
    if "$" not in line and "\\" not in line:
        return closer
    read = display_dollars._Line(
        line,
        line.lstrip().startswith("|"),
        display_dollars._line_starts(line),
        display_dollars._last_text(line),
    )
    index = 0
    slashes = 0
    while index < len(line):
        char = line[index]
        code_end = read_inline_code_span(line, index) if closer is None and char == "`" else None
        if code_end is not None:
            index, slashes = code_end, 0
            continue
        if char == "$" and slashes % 2 == 0:
            end = display_dollars._run_end(line, index)
            if (
                end - index == 2
                and closer != "\\]"
                and not display_dollars._bracketed_tier(line, index, end)
                and not display_dollars._range_end(line, index)
            ):
                closer, index = display_dollars._dollar_mark(read, index, end, closer, None)
            else:
                index = end
            slashes = 0
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
_CLOSERS: list[Closer] = [None, "$$", "$$ ", "$$\n", "\\]"]


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
