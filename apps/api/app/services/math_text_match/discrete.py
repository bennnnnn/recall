"""Stats / combinatorics / number-theory / matrix cues."""

from __future__ import annotations

import re

from app.services.math_text_match.scan import _NUM
from app.services.math_text_match.types import CombinatoricsOp, MatrixOp, NumberTheoryOp, StatsOp

# Longest/most-specific phrase first so e.g. "standard deviation" is found
# before a later, coincidental bare "deviation" would matter.
_STATS_WORDS: tuple[tuple[str, StatsOp], ...] = (
    ("standard deviation", "stdev"),
    ("std dev", "stdev"),
    ("stdev", "stdev"),
    ("variance", "variance"),
    ("median", "median"),
    ("mode", "mode"),
    ("average", "mean"),
    ("mean", "mean"),
)


def stats_signal(text: str) -> tuple[StatsOp, list[float]] | None:
    """ "mean/median/mode/standard deviation/variance of <numbers>" — requires
    BOTH the keyword AND 2+ numbers after it, so plain prose ("what do you
    mean by X") without any data list never matches."""
    lower = text.lower()
    best: tuple[int, StatsOp] | None = None
    for phrase, op in _STATS_WORDS:
        idx = lower.find(phrase)
        if idx != -1 and (best is None or idx < best[0]):
            best = (idx, op)
    if best is None:
        return None
    idx, op = best
    numbers = [float(m.group(0)) for m in _NUM.finditer(text, idx)]
    if len(numbers) < 2:
        return None
    return op, numbers[:200]


def _digits_immediately_before(text: str, idx: int) -> int | None:
    j = idx
    while j > 0 and text[j - 1].isdigit():
        j -= 1
    return int(text[j:idx]) if j < idx else None


def _digits_immediately_after(text: str, idx: int) -> tuple[int, int] | None:
    """(value, index just past the digit run) starting exactly at idx."""
    j = idx
    n = len(text)
    while j < n and text[j].isdigit():
        j += 1
    return (int(text[idx:j]), j) if j > idx else None


_BARE_FACTORIAL_BANG = re.compile(r"^\s*(\d+)\s*!\s*[.?!]*\s*$")


def _factorial_signal(text: str) -> int | None:
    """Bare "5!" / "5 factorial" / "factorial of 5" -> 5.

    Mid-sentence excitement ("I have 5!") must not count as factorial.
    """
    lower = text.lower()
    idx = lower.find("factorial of ")
    if idx != -1:
        after = _digits_immediately_after(text, idx + len("factorial of "))
        if after is not None:
            return after[0]
    idx = lower.find(" factorial")
    if idx != -1:
        n = _digits_immediately_before(text, idx)
        if n is not None:
            return n
    bare = _BARE_FACTORIAL_BANG.fullmatch(text)
    if bare is not None:
        return int(bare.group(1))
    return None


def _paren_pair(text: str, open_idx: int) -> tuple[int, int] | None:
    """Parse "(<int>,<int>)" starting at text[open_idx] == '('."""
    close = text.find(")", open_idx)
    if close == -1:
        return None
    parts = text[open_idx + 1 : close].split(",")
    if len(parts) != 2:
        return None
    a_raw, b_raw = parts[0].strip(), parts[1].strip()
    if not a_raw.isdigit() or not b_raw.isdigit():
        return None
    return int(a_raw), int(b_raw)


def _ncr_npr_signal(text: str, word: str | None, letter: str) -> tuple[int, int] | None:
    """ "<n> <word> <k>" (e.g. "5 choose 2"), "<letter>(<n>,<k>)" (e.g.
    "C(5,2)"), or "<n><letter><k>" compact (e.g. "5C2")."""
    lower = text.lower()
    if word is not None:
        needle = f" {word} "
        idx = lower.find(needle)
        if idx != -1:
            n = _digits_immediately_before(text, idx)
            after = _digits_immediately_after(text, idx + len(needle))
            if n is not None and after is not None:
                return n, after[0]
    for i, ch in enumerate(text):
        if ch.upper() != letter:
            continue
        if i + 1 < len(text) and text[i + 1] == "(":
            pair = _paren_pair(text, i + 1)
            if pair is not None:
                return pair
        n = _digits_immediately_before(text, i)
        after = _digits_immediately_after(text, i + 1)
        if n is not None and after is not None:
            return n, after[0]
    return None


def combinatorics_signal(text: str) -> tuple[CombinatoricsOp, int, int | None] | None:
    """Factorial / combinations ("choose", "C(n,k)", "nCk") / permutations
    ("P(n,k)", "nPk"). Returns (op, n, k) — k is None for factorial."""
    n = _factorial_signal(text)
    if n is not None:
        return "factorial", n, None
    combo = _ncr_npr_signal(text, "choose", "C")
    if combo is not None:
        return "combinations", combo[0], combo[1]
    perm = _ncr_npr_signal(text, None, "P")
    if perm is not None:
        return "permutations", perm[0], perm[1]
    return None


_GCD_LCM_WORDS: tuple[tuple[str, NumberTheoryOp], ...] = (
    ("greatest common divisor", "gcd"),
    ("greatest common factor", "gcd"),
    ("gcd", "gcd"),
    ("least common multiple", "lcm"),
    ("lcm", "lcm"),
)
_FACTORIZE_PREFIXES = ("prime factorization of ", "prime factors of ", "factorize ")


def number_theory_signal(text: str) -> tuple[NumberTheoryOp, int, int | None] | None:
    """gcd/lcm of two ints, prime factorization / primality of one int, or
    "<a> mod <b>". Returns (op, a, b) — b is None for factorize/is_prime."""
    lower = text.lower()
    for word, op in _GCD_LCM_WORDS:
        idx = lower.find(word)
        if idx != -1:
            nums = [float(m.group(0)) for m in _NUM.finditer(text, idx + len(word))]
            if len(nums) >= 2:
                return op, int(nums[0]), int(nums[1])
    for prefix in _FACTORIZE_PREFIXES:
        idx = lower.find(prefix)
        if idx != -1:
            after = _digits_immediately_after(text, idx + len(prefix))
            if after is not None:
                return "factorize", after[0], None
    idx = lower.find("is ")
    while idx != -1:
        after = _digits_immediately_after(text, idx + len("is "))
        if after is not None and lower[after[1] :].lstrip().startswith("prime"):
            return "is_prime", after[0], None
        idx = lower.find("is ", idx + 1)
    idx = lower.find(" mod ")
    if idx != -1:
        a = _digits_immediately_before(text, idx)
        after = _digits_immediately_after(text, idx + len(" mod "))
        if a is not None and after is not None:
            return "mod", a, after[0]
    return None


def matrix_signal(text: str) -> tuple[MatrixOp, list[list[float]]] | None:
    """ "determinant of [[1,2],[3,4]]" / "inverse of [[2,0],[1,3]]" -> (op,
    rows). Only explicit [[...],[...]] bracket notation is recognized — a
    best-effort structural match, not general NL parsing."""
    lower = text.lower()
    op: MatrixOp
    if "determinant" in lower or "det(" in lower.replace(" ", ""):
        op = "determinant"
    elif "inverse" in lower:
        op = "inverse"
    else:
        return None
    start = text.find("[[")
    if start == -1:
        return None
    end = text.find("]]", start)
    if end == -1:
        return None
    body = text[start : end + 2].strip("[]")
    rows: list[list[float]] = []
    for row_text in body.split("],["):
        cells = [c.strip() for c in row_text.strip("[]").split(",") if c.strip()]
        if not cells:
            return None
        try:
            rows.append([float(c) for c in cells])
        except ValueError:
            return None
    if len(rows) < 2 or len(rows) > 4 or any(len(r) != len(rows) for r in rows):
        return None
    return op, rows
