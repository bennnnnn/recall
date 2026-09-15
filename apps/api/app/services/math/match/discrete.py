"""Stats / combinatorics / number-theory / matrix cues."""

from __future__ import annotations

import math
import re

from app.services.math.match.scan import word_index
from app.services.math.match.types import CombinatoricsOp, MatrixOp, NumberTheoryOp, StatsOp

# Longest/most-specific phrase first so e.g. "standard deviation" is found
# before a later, coincidental bare "deviation" would matter. "sample …"
# and "population …" qualifiers must be matched before the bare forms so
# "sample standard deviation" is not swallowed by the plain "standard
# deviation" entry (which defaults to the population statistic).
_STATS_WORDS: tuple[tuple[str, StatsOp], ...] = (
    ("interquartile range", "iqr"),
    ("quartiles", "quartiles"),
    ("quartile", "quartiles"),
    ("percentile", "percentile"),
    ("iqr", "iqr"),
    ("range", "range"),
    ("sample standard deviation", "sample_stdev"),
    ("sample std dev", "sample_stdev"),
    ("sample stdev", "sample_stdev"),
    ("sample variance", "sample_variance"),
    ("population standard deviation", "stdev"),
    ("population std dev", "stdev"),
    ("population stdev", "stdev"),
    ("population variance", "variance"),
    ("standard deviation", "stdev"),
    ("std dev", "stdev"),
    ("stdev", "stdev"),
    ("variance", "variance"),
    ("median", "median"),
    ("mode", "mode"),
    ("average", "mean"),
    ("mean", "mean"),
)

_DATA_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_DATA_VALUE = re.compile(rf"{_DATA_NUMBER}(?:\s*/\s*{_DATA_NUMBER})?")


def numeric_data_values(text: str) -> list[float] | None:
    """Read whole numeric data items, never the digits inside a fraction."""
    if len(text) > 1000:
        return None
    matches = list(_DATA_VALUE.finditer(text))
    if len(matches) < 2 or len(matches) > 200:
        return None
    values: list[float] = []
    last = matches[0].start()
    for match in matches:
        if values and match.start() == last:
            return None
        gap = text[last : match.start()].strip(" ,;{}[]()")
        if gap not in {"", "and"}:
            return None
        parts = match.group(0).split("/")
        try:
            value = float(parts[0])
            if len(parts) == 2:
                value /= float(parts[1])
        except (ValueError, ZeroDivisionError):
            return None
        if not math.isfinite(value):
            return None
        values.append(value)
        last = match.end()
    if text[last:].strip(" ,;{}[]().?!") not in {"", "please"}:
        return None
    return values


def stats_signal(text: str) -> tuple[StatsOp, list[float]] | None:
    """ "mean/median/mode/standard deviation/variance of <numbers>" — requires
    BOTH the keyword AND 2+ numbers after it, so plain prose ("what do you
    mean by X") without any data list never matches."""
    lower = text.lower()
    if "weight" in lower:
        return None
    best: tuple[int, StatsOp, str] | None = None
    for phrase, op in _STATS_WORDS:
        idx = word_index(lower, phrase)
        if idx != -1 and (best is None or idx < best[0]):
            after = lower[idx + len(phrase) :].lstrip()
            if op == "mean" and (after.startswith("speed") or after.startswith("velocity")):
                continue
            best = (idx, op, phrase)
    if best is None:
        return None
    idx, op, phrase = best
    numbers = numeric_data_values(text[idx + len(phrase) :])
    if numbers is None:
        return None
    return op, numbers


def _digits_immediately_before(text: str, idx: int) -> int | None:
    j = idx
    while j > 0 and text[j - 1].isdigit():
        j -= 1
    if j > 0 and text[j - 1] in ".-/":
        return None
    return int(text[j:idx]) if j < idx else None


def _digits_immediately_after(text: str, idx: int) -> tuple[int, int] | None:
    """(value, index just past the digit run) starting exactly at idx."""
    j = idx
    n = len(text)
    while j < n and text[j].isdigit():
        j += 1
    if j < n and (text[j] == "/" or (text[j] == "." and j + 1 < n and text[j + 1].isdigit())):
        return None
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
            nums = numeric_data_values(text[idx + len(word) :])
            if (
                nums is not None
                and len(nums) == 2
                and nums[0].is_integer()
                and nums[1].is_integer()
            ):
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
        if after is not None:
            rest = lower[after[1] :].lstrip()
            if rest.startswith("prime") or rest.startswith("a prime"):
                return "is_prime", after[0], None
        idx = lower.find("is ", idx + 1)
    if "[[" not in text and "inverse" in lower and (" mod " in lower or " modulo " in lower):
        idx = lower.find("inverse")
        a_hit = _digits_immediately_after(text, idx + len("inverse"))
        if a_hit is None:
            of_at = lower.find(" of ", idx)
            if of_at != -1:
                a_hit = _digits_immediately_after(text, of_at + len(" of "))
        mod_at = lower.find(" mod ", idx)
        if mod_at == -1:
            mod_at = lower.find(" modulo ", idx)
            width = len(" modulo ")
        else:
            width = len(" mod ")
        b_hit = _digits_immediately_after(text, mod_at + width) if mod_at != -1 else None
        if a_hit is not None and b_hit is not None:
            return "mod_inverse", a_hit[0], b_hit[0]
    for prefix in ("euler totient of ", "totient of "):
        idx = lower.find(prefix)
        if idx != -1:
            after = _digits_immediately_after(text, idx + len(prefix))
            if after is not None:
                return "totient", after[0], None
    phi_at = lower.find("phi(")
    if phi_at != -1:
        after = _digits_immediately_after(text, phi_at + 4)
        if after is not None:
            return "totient", after[0], None
    idx = lower.find(" mod ")
    if idx != -1:
        a = _digits_immediately_before(text, idx)
        after = _digits_immediately_after(text, idx + len(" mod "))
        if a is not None and after is not None:
            return "mod", a, after[0]
    return None


def crt_signal(text: str) -> tuple[int, int, int, int] | None:
    lower = text.lower()
    if "chinese remainder" not in lower and word_index(lower, "crt") == -1:
        return None
    pairs: list[tuple[int, int]] = []
    start = 0
    while True:
        idx = lower.find(" mod ", start)
        if idx == -1:
            break
        a = _digits_immediately_before(text, idx)
        after = _digits_immediately_after(text, idx + len(" mod "))
        if a is None or after is None:
            return None
        pairs.append((a, after[0]))
        start = idx + 1
    if len(pairs) != 2:
        return None
    return pairs[0][0], pairs[0][1], pairs[1][0], pairs[1][1]


def _rows_from_brackets(body: str) -> list[list[float]] | None:
    inner = body.strip()
    if not inner.startswith("[[") or not inner.endswith("]]"):
        return None
    core = inner[1:-1]
    rows: list[list[float]] = []
    for row_text in core.split("],["):
        cells = [cell.strip() for cell in row_text.strip("[]").split(",") if cell.strip()]
        if not cells:
            return None
        try:
            rows.append([float(cell) for cell in cells])
        except ValueError:
            return None
    if len(rows) < 2 or len(rows) > 4:
        return None
    width = len(rows[0])
    if width < 1 or width > 4 or any(len(row) != width for row in rows):
        return None
    return rows


def bracket_matrices(text: str, limit: int = 2) -> list[list[list[float]]] | None:
    """Parse up to ``limit`` explicit ``[[...],[...]]`` matrices, left to right."""
    found: list[list[list[float]]] = []
    search = 0
    while len(found) < limit:
        start = text.find("[[", search)
        if start == -1:
            break
        end = text.find("]]", start)
        if end == -1:
            return None
        rows = _rows_from_brackets(text[start : end + 2])
        if rows is None:
            return None
        found.append(rows)
        search = end + 2
    return found or None


def _matrix_op_from_text(text: str) -> MatrixOp | None:
    lower = text.lower()
    if "determinant" in lower or "det(" in lower.replace(" ", ""):
        return "determinant"
    if "inverse" in lower:
        return "inverse"
    if "rref" in lower or "row echelon" in lower:
        return "rref"
    if "eigenvector" in lower:
        return "eigenvectors"
    if "eigen" in lower:
        return "eigenvalues"
    if "nullspace" in lower or "null space" in lower or word_index(lower, "kernel") != -1:
        return "nullspace"
    if "column space" in lower or "columnspace" in lower or "colspace" in lower:
        return "columnspace"
    if "row space" in lower or "rowspace" in lower:
        return "rowspace"
    if "diagonalize" in lower or "diagonalise" in lower or "diagonalization" in lower:
        return "diagonalize"
    if word_index(lower, "rank") != -1:
        return "rank"
    if "transpose" in lower:
        return "transpose"
    if word_index(lower, "add") != -1 or word_index(lower, "plus") != -1:
        return "add"
    if (
        word_index(lower, "multiply") != -1
        or "product of" in lower
        or word_index(lower, "times") != -1
    ):
        return "multiply"
    first = text.find("]]")
    second = text.find("[[", first + 2) if first != -1 else -1
    if first != -1 and second != -1:
        mid = text[first + 2 : second].strip()
        if mid in {"*", "\u00d7"}:
            return "multiply"
        if mid == "+":
            return "add"
    return None


def matrix_signal(text: str) -> tuple[MatrixOp, list[list[float]]] | None:
    """Recognize explicit small-matrix operations using ``[[...],[...]]`` notation.

    This remains a best-effort structural match rather than general natural-language
    matrix parsing. Operations that mathematically require a square matrix are
    rejected here before they reach the verified solver.
    """
    op = _matrix_op_from_text(text)
    if op is None:
        return None
    matrices = bracket_matrices(text)
    if not matrices:
        return None
    rows = matrices[0]
    if op in {"determinant", "inverse", "eigenvalues", "eigenvectors", "diagonalize"} and any(
        len(row) != len(rows) for row in rows
    ):
        return None
    if op in {"multiply", "add"} and len(matrices) != 2:
        return None
    return op, rows
