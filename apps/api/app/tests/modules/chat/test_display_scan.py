"""The display-maths scan jumps from mark to mark and finds what the character scan found.

Read a character at a time in Python, a reply of 200,000 dots spent 0.14 s per pass in it,
and two passes read each line (``lead_lines`` joined ``math_padding``): CI ran the 0.5 s
presentation test past its limit (2026-11-13).
"""

from __future__ import annotations

import itertools
import random

import pytest

from app.modules.chat.inline_code import read_inline_code_span
from app.modules.chat.markdown_regions import _display_closer


def _by_character(line: str, closer: str | None) -> str | None:
    """The scan as it was: one character at a time, counting backslashes as it passes them."""
    if "$" not in line and "\\" not in line:
        return closer
    index = 0
    slashes = 0
    while index < len(line):
        code_end = read_inline_code_span(line, index) if closer is None else None
        if code_end is not None:
            index, slashes = code_end, 0
        elif slashes % 2 == 0 and line.startswith("$$", index):
            if closer in (None, "$$"):
                closer = "$$" if closer is None else None
            index, slashes = index + 2, 0
        elif slashes % 2 == 0 and line.startswith("\\[", index) and closer is None:
            closer = "\\]"
            index, slashes = index + 2, 0
        elif slashes % 2 == 0 and line.startswith("\\]", index) and closer == "\\]":
            closer = None
            index, slashes = index + 2, 0
        else:
            slashes = slashes + 1 if line[index] == "\\" else 0
            index += 1
    return closer


_PIECES = ["$", "$$", "\\", "\\\\", "[", "]", "`", "``", "a", " ", "x = 1"]
_CLOSERS = [None, "$$", "\\]"]


def test_every_short_line_of_marks_ends_as_before() -> None:
    for size in range(1, 5):
        for pieces in itertools.product(_PIECES, repeat=size):
            line = "".join(pieces)
            for closer in _CLOSERS:
                assert _display_closer(line, closer) == _by_character(line, closer), (line, closer)


def test_long_random_lines_end_as_before() -> None:
    chosen = random.Random(2026_11_13)  # noqa: S311 - a fixed sample, not a secret
    for _ in range(4000):
        line = "".join(chosen.choice(_PIECES) for _ in range(chosen.randint(1, 40)))
        closer = chosen.choice(_CLOSERS)
        assert _display_closer(line, closer) == _by_character(line, closer), (line, closer)


@pytest.mark.wall_clock
def test_a_long_line_with_one_mark_is_read_in_one_search() -> None:
    import time

    line = "$x = 1$" + "." * 200_000
    started = time.perf_counter()
    for _ in range(10):
        _display_closer(line, None)
    assert time.perf_counter() - started < 0.1
