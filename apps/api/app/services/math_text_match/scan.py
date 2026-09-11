"""Number / dimension scans (CodeQL-safe, mostly linear)."""

from __future__ import annotations

import re

from app.services.text_normalize import collapse_ws

_MAX = 1000
_NUM = re.compile(r"-?\d+(?:\.\d+)?")
# Math keyboard / Unicode units: m/s² and m/s^{2} must match m/s^2.
_SUP_GLYPHS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_SUP_ASCII = "0123456789"
_SUP_TABLE = str.maketrans(_SUP_GLYPHS, _SUP_ASCII)
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
    return (
        text.replace("$$", "")
        .replace("$", "")
        .replace("\\(", "")
        .replace("\\)", "")
        .replace("\\[", "")
        .replace("\\]", "")
    )


def word_index(lower: str, phrase: str) -> int:
    """First index of ``phrase`` not glued inside a longer letter-run."""
    start = 0
    n = len(phrase)
    while True:
        idx = lower.find(phrase, start)
        if idx == -1:
            return -1
        before_ok = idx == 0 or not lower[idx - 1].isalpha()
        after = idx + n
        after_ok = after >= len(lower) or not lower[after].isalpha()
        if before_ok and after_ok:
            return idx
        start = idx + 1


def fold_match_superscripts(s: str) -> str:
    """Turn ``m/s²`` / ``m/s^{2}`` into ``m/s^2`` so unit scanners can bind.

    Linear scan — math-keyboard superscripts used to miss F=ma extract, then
    the reply still said *Couldn't verify this with SymPy.*
    """
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch in _SUP_GLYPHS:
            j = i + 1
            while j < n and s[j] in _SUP_GLYPHS:
                j += 1
            out.append("^" + s[i:j].translate(_SUP_TABLE))
            i = j
            continue
        if ch == "^" and i + 1 < n and s[i + 1] == "{":
            close = s.find("}", i + 2)
            if close != -1:
                inner = s[i + 2 : close]
                # Leave ^{x}^{2} keyboard chains for the graph peeler.
                if inner.isdigit() and (not out or out[-1] != "}"):
                    out.append("^" + inner)
                    i = close + 1
                    continue
        out.append(ch)
        i += 1
    return "".join(out)


def collapse_repeated_si_unit_powers(s: str) -> str:
    """Stacked math-keyboard ``$^2$`` inserts: ``m/s^2^2.^2`` → ``m/s^2``.

    ``2 m/s$^2$$^2.$^2`` never bound acceleration, so F=ma shipped the
    *Couldn't verify this with SymPy.* footer under a correct 10 N.
    """
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if i + 4 <= n and s[i : i + 4] == "m/s^":
            j = i + 4
            if j < n and s[j].isdigit():
                k = j + 1
                while k < n and s[k].isdigit():
                    k += 1
                out.append(s[i:k])
                i = k
                while i < n:
                    p = i
                    if p < n and s[p] == ".":
                        p += 1
                    if p < n and s[p] == "^" and p + 1 < n and s[p + 1].isdigit():
                        p += 1
                        while p < n and s[p].isdigit():
                            p += 1
                        i = p
                        continue
                    break
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def prepare(text: str) -> str | None:
    cleaned = collapse_ws(strip_inline_math_delims(text))
    if len(cleaned) > _MAX:
        return None
    return collapse_repeated_si_unit_powers(fold_match_superscripts(cleaned))


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
    for ch in compact:
        if ch in "+*^":
            return False
    return True


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

    Conservative on a single ``-`` / ``/`` (dates, phone numbers, scores).
    Auto-accept only with ``*``, ``^``, times/divide glyphs, two or
    more operators, or a cue word (``what is``, ``calculate``, ...).
    """
    if not text or len(text) > _MAX:
        return None
    stripped, had_cue = _strip_arith_cues(text.lower())
    if not stripped or not any(ch.isdigit() for ch in stripped):
        return None
    if any(ch not in _ARITH_ALLOWED for ch in stripped):
        return None
    compact = _to_ascii_arith(stripped).replace(" ", "")
    if not compact or not _arith_parens_ok(compact):
        return None
    if compact[-1] not in "0123456789)":
        return None
    if compact[0] not in "0123456789.(+-":
        return None
    ops = _count_binary_arith_ops(compact)
    if ops < 1:
        return None
    unambiguous = any(ch in stripped for ch in _UNAMBIGUOUS_ARITH)
    if not (unambiguous or ops >= 2 or had_cue):
        return None
    # Dates / phones: every binary op is ``-`` or ``/`` and there is no
    # times/power cue. Keep ``8-8*2``, ``1+2+3``, and cued ``what is 9/9``.
    if not had_cue and not unambiguous and _binary_ops_only_minus_or_slash(compact):
        return None
    return collapse_ws(_to_ascii_arith(stripped))


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


def has_equation(text: str) -> bool:
    eq = text.find("=")
    if eq <= 0 or eq >= len(text) - 1:
        return False
    if text[eq + 1 : eq + 2] == "=":
        return False
    lhs, rhs = text[:eq].strip(), text[eq + 1 :].strip()
    return bool(lhs and rhs and any(c.isalnum() for c in lhs) and any(c.isalnum() for c in rhs))


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
