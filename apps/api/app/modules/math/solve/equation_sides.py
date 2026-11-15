"""Where one side of a typed equation ends: at prose, at a sentence's stop, never mid-number.

The equation walker (``extract_eq``) steps out from each ``=`` over the characters a side
may hold and stops at the first English word or the period that ends a sentence. A run of
spaces is read once: the word beyond it decides for every space in it.
"""

from __future__ import annotations

from app.modules.math.match.letter_runs import MATH_MULTI_LETTER

EQUATION_SIDE_CHARS = frozenset(
    "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+-*/().^ "
)

# Two-letter words that sit between homework steps after collapse_ws
# ("…=0 or x-3=0"). 1-letter tokens stay variables; ln/pi stay math.
_TWO_LETTER_ENGLISH = frozenset(
    {"or", "if", "so", "to", "of", "it", "is", "be", "as", "at", "by", "an", "we", "my"}
)


def english_run_len(s: str, i: int) -> int:
    """Length of an English word starting at ``i``, else 0. Linear scan."""
    n = len(s)
    if i >= n or not s[i].isalpha():
        return 0
    j = i + 1
    while j < n and s[j].isalpha():
        j += 1
    run = s[i:j]
    low = run.lower()
    if low in MATH_MULTI_LETTER:
        return 0
    if len(run) >= 3:
        return j - i
    if len(run) == 2 and low in _TWO_LETTER_ENGLISH:
        return j - i
    return 0


def english_after(s: str, i: int) -> bool:
    """True when the next token (skipping spaces) is English.

    Inside a word there is no next token: the ``qrt`` of ``sqrt`` is not English.
    """
    n = len(s)
    if 0 < i < n and s[i - 1].isalpha() and s[i].isalpha():
        return False
    pos = i
    while pos < n and s[pos] == " ":
        pos += 1
    return english_run_len(s, pos) > 0


def english_before(s: str, i: int) -> bool:
    """True when the token ending at ``i`` (exclusive, skipping spaces) is English."""
    k = i
    while k > 0 and s[k - 1] == " ":
        k -= 1
    if k == 0 or not s[k - 1].isalpha():
        return False
    start = k - 1
    while start > 0 and s[start - 1].isalpha():
        start -= 1
    return english_run_len(s, start) > 0


def sentence_period(text: str, index: int) -> bool:
    """A `.` that ends a word or a sentence, not a decimal point (`3.14`, `.5`, `3.`).

    A decimal point is never followed by a space: ``x = 7. A tool`` ends at 7.
    """
    if index < 0 or index >= len(text) or text[index] != ".":
        return False
    prev = text[index - 1] if index else ""
    nxt = text[index + 1] if index + 1 < len(text) else ""
    return (not prev.isdigit() or nxt.isspace()) and not nxt.isdigit()


def _space_run_start(text: str, index: int) -> int:
    """The first space of the run of spaces ending at ``index`` (inclusive)."""
    while index > 0 and text[index - 1] == " ":
        index -= 1
    return index


def side_start(text: str, eq: int) -> int:
    """Where the left side of the ``=`` at ``eq`` begins.

    A run of spaces is read once: the word before it decides for every space in it.
    Walking it a space at a time and looking back over the whole run from each one took
    a second for "x" and 8,000 spaces before "=", and a 32 KB message stopped the reading.
    """
    left = eq
    while left > 0 and text[left - 1] in EQUATION_SIDE_CHARS:
        if sentence_period(text, left - 1):
            break
        if text[left - 1] == " ":
            run = _space_run_start(text, left - 1)
            if english_before(text, run):
                break
            left = run
            continue
        left -= 1
    return left


def side_end(text: str, eq: int) -> int:
    """Where the right side of the ``=`` at ``eq`` ends; a run of spaces is read once."""
    right = eq + 1
    while right < len(text) and text[right] in EQUATION_SIDE_CHARS:
        if sentence_period(text, right):
            break
        if text[right] != " ":
            if english_after(text, right):
                break
            right += 1
            continue
        after = right
        while after < len(text) and text[after] == " ":
            after += 1
        if english_run_len(text, after) > 0:
            break
        # `=0 (2x-1)(x-3)=0` — next parenthetical is another equation,
        # not part of this RHS (collapse_ws glued the two displays).
        if text[after : after + 1] == "(" and text[eq + 1 : right].strip() in {"0", "0.0"}:
            break
        right = after
    return right
