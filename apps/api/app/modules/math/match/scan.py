"""Number / dimension scans (CodeQL-safe, mostly linear)."""

from __future__ import annotations

import re
from typing import Literal, cast

from app.services.symbolic_text import (
    collapse_repeated_si_unit_powers as _collapse_repeated_si_unit_powers,
)
from app.services.symbolic_text import (
    fold_numeric_superscripts,
    normalize_symbolic_request,
    strip_inline_math_delimiters,
)
from app.services.text_match import has_equation, word_index
from app.services.text_normalize import collapse_ws

_MAX = 1000
# Keep a leading decimal point (and its sign) in the numeric token. Skipping
# it used to turn a sector/circle radius of .5 into a verified radius of 5.
_NUM = re.compile(r"-?(?:\d+(?:\.\d+)?|\.\d+)")
# Math keyboard / Unicode units: m/s² and m/s^{2} must match m/s^2.
_BARE_COORD = re.compile(r"^\((?P<x>-?\d+(?:\.\d+)?),(?P<y>-?\d+(?:\.\d+)?)\)$")
_CALC_OP = re.compile(
    r"\b(simplify|differentiate|derivative|integrate|integral|factor|expand|dsolve)\b",
    re.IGNORECASE,
)
_DIM_SEPS = ("\u00d7", "by", "x", "*")
_DIM_UNITS = ("units", "unit", "cm", "mm", "ft", "in", "m")

# Whole-message arithmetic cues. Longer phrases first so "what is" does not
# leave "the value of" behind.
_ARITH_CUES: tuple[str, ...] = (
    "the value of",
    "what is",
    "what's",
    "whats",
    "calculate",
    "compute",
    "evaluate",
    "please",
)
# OCR / keyboard glyphs → ASCII before SymPy. Keep ÷ unambiguous *before* this
# map so a lone ASCII `/` can still look like a date.
_ARITH_OP_ASCII: tuple[tuple[str, str], ...] = (
    ("\u00d7", "*"),
    ("\u22c5", "*"),
    ("\u00b7", "*"),
    ("\u2217", "*"),
    ("\u00f7", "/"),
    ("\u2215", "/"),
    ("\u2044", "/"),
    ("\u2212", "-"),
    ("\u2013", "-"),
    ("\u2014", "-"),
)
_UNAMBIGUOUS_ARITH = frozenset("*^" + "".join(src for src, dst in _ARITH_OP_ASCII if dst in "*/"))
_ARITH_ALLOWED = frozenset("0123456789.+-*/^() " + "".join(src for src, _ in _ARITH_OP_ASCII))
_GEOMETRY_DIM_WORDS = (
    "rectangle",
    "triangle",
    "square",
    "circle",
    "trapezoid",
    "trapezium",
    "parallelogram",
    "diagonal",
    "sector",
    "prism",
    "cuboid",
)

# Multi-letter tokens SymPy already treats as one name. Any other 3+ letter
# run is English or a command — never g*r*a*p*h, and never ``squared``/``plus``
# slipping into letter-products.
MATH_MULTI_LETTER = frozenset(
    {
        "sin",
        "cos",
        "tan",
        "sec",
        "csc",
        "cot",
        "arcsin",
        "arccos",
        "arctan",
        "sinh",
        "cosh",
        "tanh",
        "log",
        "ln",
        "sqrt",
        "exp",
        "abs",
        "min",
        "max",
        "pi",
        "oo",
        "inf",
        "infinity",
        "nan",
        "det",
        "gcd",
        "lcm",
        "mod",
        "theta",
    }
)
VIZ_COMMANDS = frozenset(
    {
        "graph",
        "plot",
        "draw",
        "show",
        "sketch",
        "visualize",
        "visualise",
        "vertical",
    }
)
# Only these may glue onto a following 1-letter variable (``graphx=4``).
# ``show``/``draw`` are too common as English prefixes (``shown``, ``drawn``).
_GLUEABLE_VIZ = frozenset({"graph", "plot"})


def _alpha_run_end(s: str, start: int) -> int:
    j = start
    n = len(s)
    while j < n and s[j].isalpha():
        j += 1
    return j


def _looks_like_math_core(s: str) -> bool:
    if not s:
        return False
    if any(ch.isdigit() for ch in s):
        return True
    if any(ch in "+-*/^()" for ch in s):
        return True
    letters = [ch for ch in s if ch.isalpha()]
    return len(letters) == 1


def peel_edge_english(side: str) -> str:
    """Trim unknown 3+ letter runs glued to an equation side.

    ``X=6graph`` → RHS ``6``. ``velocity=12`` stays (the whole side is the
    name). ``E=mc^2`` is untouched (2-letter ``mc`` is implicit product).
    """
    s = side.strip()
    i = len(s)
    while i > 0 and s[i - 1].isalpha():
        i -= 1
    run = s[i:]
    rest = s[:i].rstrip()
    if len(run) >= 3 and run.lower() not in MATH_MULTI_LETTER and _looks_like_math_core(rest):
        s = rest
    j = 0
    while j < len(s) and s[j].isalpha():
        j += 1
    run = s[:j]
    rest = s[j:].lstrip()
    if len(run) >= 3 and run.lower() not in MATH_MULTI_LETTER and _looks_like_math_core(rest):
        s = rest
    return s


def _alpha_run_is_viz(run: str, *, commands: frozenset[str], glueable: frozenset[str]) -> bool:
    low = run.lower()
    if low in commands:
        return True
    for cmd in glueable:
        if len(low) > len(cmd) and low.startswith(cmd) and _looks_like_math_core(low[len(cmd) :]):
            return True
    return False


def _text_has_command(
    text: str,
    commands: frozenset[str],
    glueable: frozenset[str] | None = None,
) -> bool:
    glue = glueable or frozenset()
    lower = text.lower()
    start = 0
    n = len(lower)
    while start < n:
        if lower[start].isalpha():
            end = _alpha_run_end(lower, start)
            if _alpha_run_is_viz(lower[start:end], commands=commands, glueable=glue):
                return True
            start = end
        else:
            start += 1
    return False


def has_viz_command(text: str) -> bool:
    """True when the user asked to graph/plot/draw — whole word or glued.

    Substring ``graph`` must not match ``paragraph``. Glued ``X=6graph``
    still counts: ``graph`` is its own letter-run, not five variables.
    ``graphx=4`` counts because ``graph`` is a prefix of the run and ``x``
    is a 1-letter variable.
    """
    lower = text.lower()
    if "visuali" in lower:
        return True
    return _text_has_command(text, VIZ_COMMANDS, _GLUEABLE_VIZ)


def mask_unknown_letter_runs(text: str) -> str:
    """Replace unknown 3+ letter runs with spaces so they are not split into
    per-letter variables (``6graph`` must not guess g,r,a,p,h)."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i].isalpha():
            j = _alpha_run_end(text, i)
            run = text[i:j]
            if len(run) >= 3 and run.lower() not in MATH_MULTI_LETTER:
                out.append(" ")
            else:
                out.append(run)
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def has_unknown_english_run(text: str) -> bool:
    """True when an alpha-run of length >= 3 is not a known math token."""
    i = 0
    n = len(text)
    while i < n:
        if text[i].isalpha():
            j = _alpha_run_end(text, i)
            if (j - i) >= 3 and text[i:j].lower() not in MATH_MULTI_LETTER:
                return True
            i = j
        else:
            i += 1
    return False


def looks_like_math_expr(text: str) -> bool:
    """Candidate is an expression, not leftover English with a digit in it."""
    stripped = text.strip()
    if not stripped:
        return False
    if has_unknown_english_run(stripped):
        return False
    return any(ch.isalnum() or ch in "+-*/^=()." for ch in stripped)


def _leibniz_op_end(text: str, start: int) -> int | None:
    """Exclusive end of ``d/dx`` or ``dy/dx`` starting at ``start``."""
    n = len(text)
    if start >= n or text[start] not in "dD":
        return None
    i = start + 1
    if i < n and text[i] == "/":
        if i + 1 < n and text[i + 1] in "dD":
            i += 2
            if i < n and text[i].isalpha() and (i + 1 == n or not text[i + 1].isalpha()):
                return i + 1
        return None
    if i < n and text[i].isalpha() and (i + 1 == n or not text[i + 1].isalpha()):
        i += 1
        if i + 1 < n and text[i] == "/" and text[i + 1] in "dD":
            i += 2
            if i < n and text[i].isalpha() and (i + 1 == n or not text[i + 1].isalpha()):
                return i + 1
    return None


def ddx_cue_at(text: str) -> int | None:
    """Index of a ``d/dx`` / ``dy/dx`` derivative cue (not ``and/or``)."""
    lower = text.lower()
    n = len(lower)
    start = 0
    while start < n:
        idx = lower.find("d", start)
        if idx == -1:
            return None
        prev_ok = idx == 0 or not lower[idx - 1].isalpha()
        if prev_ok and _leibniz_op_end(lower, idx) is not None:
            return idx
        start = idx + 1
    return None


def ddx_expr_after(text: str) -> str | None:
    idx = ddx_cue_at(text)
    if idx is None:
        return None
    end = _leibniz_op_end(text, idx)
    if end is None:
        return None
    return text[end:]


def split_glued_viz_runs(text: str) -> str:
    """``graphx=4`` → ``graph x=4`` so ``x`` is a standalone variable."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i].isalpha():
            end = _alpha_run_end(text, i)
            run = text[i:end]
            low = run.lower()
            split_at: int | None = None
            for cmd in _GLUEABLE_VIZ:
                if (
                    len(low) > len(cmd)
                    and low.startswith(cmd)
                    and _looks_like_math_core(low[len(cmd) :])
                ):
                    split_at = len(cmd)
                    break
            if split_at is not None:
                out.append(run[:split_at])
                out.append(" ")
                out.append(run[split_at:])
            else:
                out.append(run)
            i = end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _parse_unsigned_number(s: str, start: int = 0) -> tuple[float, int] | None:
    """Parse ``digits`` or ``digits.digits`` / ``digits,digits`` at ``start``.

    A comma with no space before the fraction (``3,5``) is a decimal, not a
    thousands/list split.
    """
    n = len(s)
    i = start
    if i >= n or not s[i].isdigit():
        return None
    while i < n and s[i].isdigit():
        i += 1
    if i < n and s[i] in ".,":
        j = i + 1
        if j < n and s[j].isdigit():
            while j < n and s[j].isdigit():
                j += 1
            i = j
        # else: "5." at end of a sentence — keep the integer, ignore the period.
    try:
        return float(s[start:i].replace(",", ".")), i
    except ValueError:
        return None


def strip_inline_math_delims(text: str) -> str:
    """Composer/math keyboard wraps numbers in ``$...$`` / ``\\(...\\)``.

    ``X=$6$graph`` must be seen as ``X=6graph`` — a ``$`` after ``x=`` used
    to hide the 6 from the vertical-line matcher, so we solved the equation
    in words and never attached the plot.
    """
    return strip_inline_math_delimiters(text)


def fold_match_superscripts(s: str) -> str:
    """Turn ``m/s²`` / ``m/s^{2}`` into ``m/s^2`` so unit scanners can bind.

    Linear scan — math-keyboard superscripts used to miss F=ma extract, then
    the reply still said *Couldn't verify this with SymPy.*
    """
    return fold_numeric_superscripts(s)


def collapse_repeated_si_unit_powers(s: str) -> str:
    """Stacked math-keyboard ``$^2$`` inserts: ``m/s^2^2.^2`` → ``m/s^2``.

    ``2 m/s$^2$$^2.$^2`` never bound acceleration, so F=ma shipped the
    *Couldn't verify this with SymPy.* footer under a correct 10 N.
    """
    return _collapse_repeated_si_unit_powers(s)


def prepare(text: str) -> str | None:
    return normalize_symbolic_request(text)


def _strip_arith_cues(lower: str) -> tuple[str, bool]:
    """Remove whole-word compute cues. Linear ``word_index``, no regex."""
    had = False
    s = lower
    changed = True
    while changed:
        changed = False
        for cue in _ARITH_CUES:
            idx = word_index(s, cue)
            if idx == -1:
                continue
            s = s[:idx] + " " + s[idx + len(cue) :]
            had = True
            changed = True
            break
    s = s.strip()
    while s and s[-1] in "?.!":
        s = s[:-1].rstrip()
    return collapse_ws(s), had


def _to_ascii_arith(expr: str) -> str:
    out = expr
    for src, dst in _ARITH_OP_ASCII:
        out = out.replace(src, dst)
    return out


def _binary_ops_only_minus_or_slash(compact: str) -> bool:
    """True when every binary operator is ``-`` or ``/`` (dates, phone numbers)."""
    for ch in compact.removeprefix("+"):
        if ch in "+*^":
            return False
    return True


def _looks_like_date_or_phone(compact: str) -> bool:
    """Structural dates (``9/7/2026``) and phones (``1-800-273-8255``).

    Linear scan — not a blanket reject of every ``-``/``/`` chain, so
    ``10-3-2`` and ``100/5/2`` stay calculator arithmetic.
    """
    compact = compact.removeprefix("+")
    if not compact or compact[0] == "-":
        return False
    if re.fullmatch(r"(?:\+?1-?)?\(\d{3}\)\d{3}-\d{4}", compact):
        return True
    groups: list[int] = []
    seps: list[str] = []
    i = 0
    n = len(compact)
    while i < n:
        ch = compact[i]
        if ch.isdigit():
            j = i + 1
            while j < n and compact[j].isdigit():
                j += 1
            groups.append(j - i)
            i = j
            continue
        if ch in "-/":
            seps.append(ch)
            i += 1
            continue
        return False
    if not seps or len(groups) != len(seps) + 1:
        return False
    all_slash = all(sep == "/" for sep in seps)
    all_minus = all(sep == "-" for sep in seps)
    if not (all_slash or all_minus):
        return False
    if len(groups) == 2:
        # Seven-digit phone and year-month date. A bare short subtraction
        # such as 2-6 is arithmetic; prose ranges never pass the allowlist.
        a, b = groups
        return all_minus and ((a == 3 and b == 4) or (a == 4 and b == 2))
    if len(groups) == 3:
        a, b, c = groups
        if a <= 2 and b <= 2 and c in (2, 4):
            return True
        if a == 4 and b <= 2 and c <= 2:
            return True
        return all_minus and a == 3 and b == 3 and c == 4
    return all_minus and len(groups) >= 4 and sum(groups) >= 7


def _unambiguous_single_slash(compact: str) -> bool:
    """True for a two-number division that cannot reasonably be a date.

    A bare ``9/9`` remains ambiguous, as do year/month forms such as
    ``2026/09``.  Values such as ``456/56`` are not calendar-shaped and should
    reach the arithmetic solver instead of leaving a model to improvise long
    division in plain text.
    """
    if compact.count("/") != 1 or any(ch in compact for ch in "+-*^()"):
        return False
    left, right = compact.split("/", 1)
    if not left or not right:
        return False
    if "." in left or "." in right:
        return all(part.replace(".", "", 1).isdigit() for part in (left, right))
    if not left.isdigit() or not right.isdigit():
        return False
    first, second = int(left), int(right)
    if len(left) == 4 and 1 <= second <= 12:
        return False
    could_be_month_day = (1 <= first <= 12 and 1 <= second <= 31) or (
        1 <= second <= 12 and 1 <= first <= 31
    )
    return not could_be_month_day


def _count_binary_arith_ops(compact: str) -> int:
    """Binary ``+ - * / ^`` in an ASCII expression. Leading/unary ``-`` is not an op."""
    ops = 0
    prev_was_op = True
    for ch in compact:
        if ch in "+*/^":
            ops += 1
            prev_was_op = True
            continue
        if ch == "-":
            if not prev_was_op:
                ops += 1
            prev_was_op = True
            continue
        if ch == "(":
            prev_was_op = True
            continue
        if ch == ")":
            prev_was_op = False
            continue
        prev_was_op = False
    return ops


def _arith_parens_ok(compact: str) -> bool:
    depth = 0
    for ch in compact:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def bare_arithmetic_expr(text: str) -> str | None:
    """Whole-message numeric arithmetic, or None.

    Shared by the SymPy gate and the arithmetic extractor so ``8-8*2`` cannot
    be gated as a dimension pair (``8*2``) and then fail extract.

    Bare subtraction is arithmetic; a single ``/`` needs a cue unless its
    values cannot reasonably be a date (for example ``456/56``).
    Auto-accept with a single subtraction, ``*``, ``^``, times/divide glyphs, two or
    more operators, or a cue word (``what is``, ``calculate``, ...).
    Uncued ``-``/``/`` chains that look like a date or phone are rejected;
    chained arithmetic such as ``10-3-2`` is not.
    """
    if not text or len(text) > _MAX:
        return None
    stripped, had_cue = _strip_arith_cues(text.lower())
    if not stripped or not any(ch.isdigit() for ch in stripped):
        return None
    from app.modules.math.solve.parse import _normalize_latex_to_sympy

    normalized = _normalize_latex_to_sympy(stripped)
    # Numeric radicals and keyboard braced powers use the same normalization
    # as the solver. Only sqrt is admitted here; symbols/prose stay excluded.
    numeric = normalized.replace("sqrt(", "(")
    if any(ch not in _ARITH_ALLOWED for ch in numeric):
        return None
    compact = _to_ascii_arith(numeric).replace(" ", "")
    if not compact or not _arith_parens_ok(compact):
        return None
    if compact[-1] not in "0123456789)":
        return None
    if compact[0] not in "0123456789.(+-":
        return None
    ops = _count_binary_arith_ops(compact)
    has_root = "sqrt(" in normalized
    if ops < 1 and not has_root:
        return None
    unambiguous = has_root or any(ch in stripped for ch in _UNAMBIGUOUS_ARITH)
    unambiguous = unambiguous or "**" in normalized
    unambiguous = unambiguous or _unambiguous_single_slash(compact)
    subtraction = ops == 1 and "-" in compact and not any(ch in "+*/^" for ch in compact)
    if not (unambiguous or subtraction or ops >= 2 or had_cue):
        return None
    # Dates / phones: structural ``9/7/2026`` / ``1-800-273-8255``, not
    # every minus-or-slash chain (``10-3-2``). Keep ``8-8*2`` and cued ``9/9``.
    if (
        not had_cue
        and not unambiguous
        and _binary_ops_only_minus_or_slash(compact)
        and _looks_like_date_or_phone(compact)
    ):
        return None
    return collapse_ws(_to_ascii_arith(normalized))


_WRITTEN_OPERATOR_ALIASES = (
    ("multiplied by", "*"),
    ("divided by", "/"),
    ("devided by", "/"),
    ("divide by", "/"),
    ("devide by", "/"),
    ("times", "*"),
    ("plus", "+"),
    ("minus", "-"),
    ("\u00d7", "*"),
    ("\u00f7", "/"),
    ("*", "*"),
    ("/", "/"),
    ("+", "+"),
    ("-", "-"),
)
_WRITTEN_SCHOOL_OP = {
    "+": "column_addition",
    "-": "column_subtraction",
    "*": "column_multiplication",
    "/": "long_division",
}

# Presentation methods that select the typed school-work trace rather than
# changing the arithmetic.  Keep this as a small grammar (connector + method),
# not a list of complete user sentences.  The allowed-operation set prevents
# us from silently answering a request such as "2 + 3 using borrowing" with a
# carrying trace that does not follow the requested method.
_WRITTEN_METHODS: tuple[tuple[str, frozenset[str]], ...] = (
    ("column addition", frozenset({"column_addition"})),
    ("column subtraction", frozenset({"column_subtraction"})),
    ("column multiplication", frozenset({"column_multiplication"})),
    ("long multiplication", frozenset({"column_multiplication"})),
    ("carrying", frozenset({"column_addition", "column_multiplication"})),
    ("borrowing", frozenset({"column_subtraction"})),
    ("regrouping", frozenset({"column_addition", "column_subtraction"})),
    (
        "standard algorithm",
        frozenset({"column_addition", "column_subtraction", "column_multiplication"}),
    ),
)
_WRITTEN_METHOD_CONNECTORS = ("using the", "using", "use the", "use", "with", "by")


def _strip_written_method_cues(value: str) -> tuple[str, frozenset[str] | None]:
    """Remove bounded method metadata and return the compatible school ops."""
    compatible: frozenset[str] | None = None
    stripped = value
    for method, allowed in _WRITTEN_METHODS:
        for connector in _WRITTEN_METHOD_CONNECTORS:
            phrase = f"{connector} {method}"
            index = word_index(stripped, phrase)
            if index == -1:
                continue
            if word_index(stripped[index + len(phrase) :], phrase) != -1:
                return value, frozenset()
            stripped = collapse_ws(f"{stripped[:index]} {stripped[index + len(phrase) :]}").strip(
                " :?.!"
            )
            compatible = allowed if compatible is None else compatible & allowed
    return stripped, compatible


_DIVISION_MODE_PHRASES: tuple[tuple[str, str], ...] = (
    ("quotient and remainder", "remainder"),
    ("with a remainder", "remainder"),
    ("as a remainder", "remainder"),
    ("as a fraction", "fraction"),
    ("fraction answer", "fraction"),
    ("as a decimal", "decimal"),
    ("decimal answer", "decimal"),
    ("round up", "round_up"),
    ("discard the remainder", "discard"),
    ("ignore the remainder", "discard"),
)


def _school_number(token: str) -> str | None:
    value = token.strip()
    if not value or any(not (ch.isascii() and (ch.isdigit() or ch in ",.")) for ch in value):
        return None
    if value.count(".") > 1:
        return None
    whole, dot, fraction = value.partition(".")
    if dot and (not fraction or not fraction.isdigit()):
        return None
    if "," in whole:
        groups = whole.split(",")
        if not groups[0].isdigit() or not 1 <= len(groups[0]) <= 3:
            return None
        if any(len(group) != 3 or not group.isdigit() for group in groups[1:]):
            return None
        whole = "".join(groups)
    elif not whole.isdigit():
        return None
    return whole + (f".{fraction}" if dot else "")


_POWER_ORDINALS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}


def _power_atom(token: str) -> str | None:
    number = _school_number(token)
    if number is not None:
        return number
    return token.lower() if len(token) == 1 and token.isascii() and token.isalpha() else None


def _power_exponent(token: str) -> int | None:
    lower = token.lower()
    if lower in _POWER_ORDINALS:
        return _POWER_ORDINALS[lower]
    ordinal = re.fullmatch(r"(\d+)(?:st|nd|rd|th)", lower)
    raw = ordinal.group(1) if ordinal is not None else lower
    if not raw.isdigit():
        return None
    value = int(raw)
    return value if value <= 1000 else None


def spoken_power_request(text: str) -> str | None:
    """Return canonical ``base^exponent`` for one complete spoken power ask.

    This is a bounded grammar, not a physics keyword exception.  It accepts
    both base-first (``2 to the power of 3``) and exponent-first (``the third
    power of 5``) forms only when the entire remaining request is consumed.
    """
    if not text or len(text) > _MAX:
        return None
    value, _had_cue = _strip_arith_cues(collapse_ws(text).lower())
    tokens = value.split()
    if tokens[:1] == ["the"]:
        tokens = tokens[1:]

    # 2 to the power of 3 / 2 raised to the third power
    base = _power_atom(tokens[0]) if tokens else None
    tail = tokens[1:]
    exponent_token: str | None = None
    if tail[:4] == ["to", "the", "power", "of"] and len(tail) == 5:
        exponent_token = tail[4]
    elif tail[:5] == ["raised", "to", "the", "power", "of"] and len(tail) == 6:
        exponent_token = tail[5]
    elif len(tail) == 4 and tail[:2] == ["to", "the"] and tail[3] == "power":
        exponent_token = tail[2]
    elif len(tail) == 5 and tail[:3] == ["raised", "to", "the"] and tail[4] == "power":
        exponent_token = tail[3]
    if base is not None and exponent_token is not None:
        exponent = _power_exponent(exponent_token)
        return f"{base}^{exponent}" if exponent is not None else None

    # the third power of 5
    if len(tokens) == 4 and tokens[1:3] == ["power", "of"]:
        exponent = _power_exponent(tokens[0])
        base = _power_atom(tokens[3])
        if exponent is not None and base is not None:
            return f"{base}^{exponent}"
    return None


def written_addition_request(text: str) -> list[str] | None:
    """Return every addend for one closed two-to-six-addend school sum."""
    if not text or len(text) > _MAX:
        return None
    from app.modules.math.response_intent import strip_math_response_wrappers

    value = collapse_ws(strip_math_response_wrappers(text)).strip(" :?.!").lower()
    for filler in ("for ", "of ", "me "):
        if value.startswith(filler):
            value = value[len(filler) :].lstrip()
            break
    value, _had_cue = _strip_arith_cues(value)
    if any(alias in value for alias in (" - ", " * ", " / ", "minus", "times", "divided")):
        return None
    raw_tokens = re.split(r"\s*(?:\+|\bplus\b)\s*", value)
    if not 2 <= len(raw_tokens) <= 6:
        return None
    numbers = [_school_number(token) for token in raw_tokens]
    if any(number is None for number in numbers):
        return None
    return [number for number in numbers if number is not None]


def division_answer_mode(
    text: str, left: str, right: str
) -> Literal["remainder", "fraction", "decimal", "round_up", "discard"]:
    """Select answer representation independently from response detail.

    Ordinary division means the ordinary numerical quotient.  Remainder form
    is a distinct interpretation and is selected only when the learner asks
    for it or explicitly asks to use school long division with whole numbers.
    Whether the working is displayed is decided later by response intent.
    """
    lower = collapse_ws(text).lower()
    for phrase, mode in _DIVISION_MODE_PHRASES:
        if phrase in lower:
            return cast(Literal["remainder", "fraction", "decimal", "round_up", "discard"], mode)
    if "long division" in lower and "." not in left and "." not in right:
        return "remainder"
    return "decimal"


def written_arithmetic_request(text: str) -> tuple[str, str, str, str] | None:
    """Return ``(left, right, operator, school_op)`` for one closed school sum.

    This is deliberately narrower than the general calculator grammar. It
    accepts two non-negative literals and one operation, including grouping
    commas and common spoken operators, while rejecting every leftover word.
    """
    if not text or len(text) > _MAX:
        return None
    from app.modules.math.response_intent import strip_math_response_wrappers

    value = collapse_ws(strip_math_response_wrappers(text)).strip(" :?.!").lower()
    for filler in ("for ", "of ", "me "):
        if value.startswith(filler):
            value = value[len(filler) :].lstrip()
            break
    value, had_cue = _strip_arith_cues(value)
    value, compatible_methods = _strip_written_method_cues(value)
    if compatible_methods == frozenset():
        return None
    # A bare "show" selects presentation, not an arithmetic operation.  Do
    # this after the established "show long division" grammar has seen the
    # complete phrase below.
    if value.startswith("show me "):
        value = value[8:].lstrip()
        had_cue = True
    elif value.startswith("show ") and not value.startswith("show long division"):
        value = value[5:].lstrip()
        had_cue = True
    for phrase, _mode in _DIVISION_MODE_PHRASES:
        value = collapse_ws(value.replace(phrase, " ")).strip(" :?.!")
    had_long_division_cue = "long division" in value
    for phrase in (
        "using long division to",
        "use long division to",
        "show long division",
        "using long division",
        "use long division",
        "with long division",
    ):
        value = collapse_ws(value.replace(phrase, " ")).strip(" :?.!")
    found: tuple[str, str] | None = None
    for alias, operator in _WRITTEN_OPERATOR_ALIASES:
        index = value.find(alias)
        if index < 0:
            continue
        if value.find(alias, index + len(alias)) >= 0:
            return None
        if found is not None:
            return None
        found = (alias, operator)
    if found is None:
        return None
    alias, operator = found
    left_raw, right_raw = value.split(alias, 1)
    left, right = _school_number(left_raw), _school_number(right_raw)
    if left is None or right is None:
        return None
    compact = f"{left}{operator}{right}"
    school_op = _WRITTEN_SCHOOL_OP[operator]
    if compatible_methods is not None and school_op not in compatible_methods:
        return None
    if alias == "/" and not (
        had_cue or had_long_division_cue or _unambiguous_single_slash(compact)
    ):
        return None
    if alias == "-" and not had_cue and _looks_like_date_or_phone(compact):
        return None
    return left, right, operator, school_op


def geometry_dim_context(lower: str) -> bool:
    """Shape / diagonal words that geometry extractors actually require.

    ``first_dim_pair`` alone matches ``8*2`` inside ``8-8*2``. The gate must
    not treat that as verified geometry.
    """
    padded = f" {lower} "
    if " rect " in padded:
        return True
    return any(word_index(lower, cue) != -1 for cue in _GEOMETRY_DIM_WORDS)


def has_draw_shape(lower: str, shape: str) -> bool:
    if shape not in lower:
        return False
    return any(v in lower for v in ("draw ", "show ", "sketch ", "visualize ", "visualise "))


def has_math_keyword(lower: str) -> bool:
    compact = lower.replace(" ", "")
    # Bare ``y=x^2`` is a math ask. ``tell me about y=x^2`` is prose that
    # happens to mention a formula — do not pull it into SymPy as a solve.
    if "y=" in compact and not has_unknown_english_run(lower):
        return True
    # ``graph``/``plot`` are whole tokens (or glued onto a variable), not
    # substrings — ``paragraph`` must not look like a graph ask. ``show`` /
    # ``draw`` stay out of this gate so "show me the weather" is not math.
    if _text_has_command(lower, _GLUEABLE_VIZ, _GLUEABLE_VIZ):
        return True
    for phrase in (
        "solve",
        "simplify",
        "factor",
        "expand",
        "differentiate",
        "derivative",
        "integrate",
        "integral",
        "equation",
        "algebra",
        "quadratic",
        "polynomial",
        "find the angle",
        "diagonal",
        "rectangle",
        "triangle",
        "circle",
        "geometry",
        "radius",
        "diameter",
        "circumference",
        "function",
        "sqrt",
        "square root",
        "pythagor",
    ):
        if phrase in lower:
            return True
    return False


# A standalone single-letter variable (not part of a longer word) is a strong
# algebraic signal. "2x+3=7" → 'x' qualifies; "the meeting = 3pm" has no such
# letter (every letter sits inside a multi-letter word), so prose with an '='
# is not pulled into SymPy.
_STANDALONE_VAR_RE = re.compile(r"(?<![a-zA-Z])[a-zA-Z](?![a-zA-Z])")
_EQ_SIDE_LEADINS = (
    "let ",
    "set ",
    "given ",
    "if ",
    "when ",
    "where ",
    "and ",
    "so ",
    "then ",
)


def _math_equation_side(side: str) -> bool:
    """True when one side of ``=`` is an expression, not leftover English."""
    s = collapse_ws(side)
    if not s:
        return False
    prev = None
    while prev != s:
        prev = s
        lower = s.lower()
        for prefix in _EQ_SIDE_LEADINS:
            if lower.startswith(prefix):
                s = s[len(prefix) :].strip()
                break
        else:
            break
    return looks_like_math_expr(s)


def has_algebraic_equation(text: str) -> bool:
    """An equation that contains a standalone single-letter variable.

    Used to trigger SymPy for bare ``2x+3=7`` (no "solve"/"find" keyword)
    without dragging in prose that happens to contain an ``=``.
    """
    if not has_equation(text):
        return False
    if not _STANDALONE_VAR_RE.search(text):
        return False
    eq = text.find("=")
    return _math_equation_side(text[:eq]) and _math_equation_side(text[eq + 1 :])


def inequality_signal(cleaned: str) -> bool:
    """A clear algebraic inequality: a symbolic comparator (``<``, ``>``, ``≤``,
    ``≥``, ``<=``, ``>=``) with both a variable letter and a number nearby —
    ``"x > 4"``, ``"2x < 10"``, ``"1 < x < 5"``.

    Rejects prose (``"less than 5 minutes"`` — word, no symbol) and trivial
    comparisons (``"5 < 10"`` — no variable letter). The window is small (12
    chars each side) so a stray ``>`` in unrelated prose without a nearby digit
    + letter doesn't trip.
    """
    for m in re.finditer(r"<=|>=|≤|≥|<|>", cleaned):
        start = max(0, m.start() - 12)
        end = min(len(cleaned), m.end() + 12)
        window = cleaned[start:end]
        if any(c.isalpha() for c in window) and any(c.isdigit() for c in window):
            return True
    return False


def first_dim_pair(text: str) -> tuple[float, float, str] | None:
    # Collapse "8 x 5 cm" → "8x5cm" so separators are adjacent (no space pumps).
    compact = (
        text.replace(" \u00d7 ", "\u00d7")
        .replace(" x ", "x")
        .replace(" * ", "*")
        .replace(" by ", "by")
        .replace(" ", "")
    )
    lower = compact.lower()
    n = len(compact)
    i = 0
    while i < n:
        a_hit = _parse_unsigned_number(compact, i)
        if a_hit is None:
            i += 1
            continue
        a, j = a_hit
        sep_len = 0
        for sep in _DIM_SEPS:
            if lower.startswith(sep, j):
                sep_len = len(sep)
                break
        if not sep_len:
            i += 1
            continue
        b_hit = _parse_unsigned_number(compact, j + sep_len)
        if b_hit is None:
            i += 1
            continue
        b, k = b_hit
        unit = "cm"
        for cand in _DIM_UNITS:
            if lower.startswith(cand, k):
                unit = "units" if cand.startswith("unit") else cand
                break
        return a, b, unit
    return None


def first_dim_triple(text: str) -> tuple[float, float, float, str] | None:
    """Parse ``3 by 4 by 5 cm`` / ``3x4x5`` — a 2-value pair is not enough."""
    compact = (
        text.replace(" \u00d7 ", "\u00d7")
        .replace(" x ", "x")
        .replace(" * ", "*")
        .replace(" by ", "by")
        .replace(" ", "")
    )
    lower = compact.lower()
    n = len(compact)
    i = 0
    while i < n:
        a_hit = _parse_unsigned_number(compact, i)
        if a_hit is None:
            i += 1
            continue
        a, j = a_hit
        sep1 = 0
        for sep in _DIM_SEPS:
            if lower.startswith(sep, j):
                sep1 = len(sep)
                break
        if not sep1:
            i += 1
            continue
        b_hit = _parse_unsigned_number(compact, j + sep1)
        if b_hit is None:
            i += 1
            continue
        b, k = b_hit
        sep2 = 0
        for sep in _DIM_SEPS:
            if lower.startswith(sep, k):
                sep2 = len(sep)
                break
        if not sep2:
            i += 1
            continue
        c_hit = _parse_unsigned_number(compact, k + sep2)
        if c_hit is None:
            i += 1
            continue
        c, m = c_hit
        unit = "cm"
        for cand in _DIM_UNITS:
            if lower.startswith(cand, m):
                unit = "units" if cand.startswith("unit") else cand
                break
        return a, b, c, unit
    return None


def number_after(text: str, label: str) -> float | None:
    lower = text.lower()
    idx = lower.find(label)
    if idx == -1:
        return None
    m = _NUM.search(text, idx + len(label))
    return float(m.group(0)) if m else None


def two_numbers_after(text: str, label: str) -> tuple[float, float] | None:
    """``legs 3 and 4`` / ``legs 3, 4`` → (3, 4). Linear ``find`` + digit scan."""
    lower = text.lower()
    idx = lower.find(label)
    if idx == -1:
        return None
    found: list[float] = []
    pos = idx + len(label)
    while True:
        m = _NUM.search(text, pos)
        if m is None:
            break
        try:
            found.append(float(m.group(0)))
        except ValueError:
            pos = m.end()
            continue
        if len(found) >= 2:
            return found[0], found[1]
        pos = m.end()
    return None
