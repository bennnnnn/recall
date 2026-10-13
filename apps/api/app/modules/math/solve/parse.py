"""Parse/normalize expressions for SymPy (server-side only)."""

from __future__ import annotations

import logging
import re
from typing import Any

from sympy import Abs, E, Eq, Mul, Pow, Symbol, log, parse_expr, pi
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    standard_transformations,
)

from app.core.config import get_settings
from app.core.sympy_notation import use_school_log_notation
from app.modules.math.function_names import (
    HYPERBOLIC,
    MATH_FUNCTION_NAMES,
    TRIG,
    function_name_alternation,
    names_longest_first,
)
from app.modules.math.schemas import EquationInput
from app.services.solving import MathServiceError

logger = logging.getLogger(__name__)

# A bare ``log`` is base 10 here, so a natural log has to print as ``\ln``.
use_school_log_notation()

_TRANSFORMATIONS = (
    *standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)


def _school_log(arg: Any, base: Any = 10, evaluate: bool = True) -> Any:
    """``log(x)`` is base 10, as on a school calculator; ``ln(x)`` is natural.

    ``log(x, b)`` keeps its written base. Unevaluated, SymPy's two-argument
    ``log`` prints without its base, so the quotient is built by hand.
    """
    if evaluate:
        return log(arg, base)
    return Mul(
        log(arg, evaluate=False), Pow(log(base, evaluate=False), -1, evaluate=False), evaluate=False
    )


_LOCALS: dict[str, Any] = {
    "pi": pi,
    "e": E,
    "E": E,
    "Abs": Abs,
    "log": _school_log,
    "lg": _school_log,
}

_EXACT_LATEX_DECIMAL_THRESHOLD = 40


def derivative_latex(expr: Any) -> str:
    """A derivative as a textbook writes it.

    A quotient keeps one fraction bar: the denominator factored, the numerator
    expanded unless factoring shows a repeated factor:
    ``\\frac{x^{2} - 2 x - 1}{\\left(x - 1\\right)^{2}}``, not SymPy's
    ``\\frac{- x^{2} + 2 x \\left(x - 1\\right) - 1}{...}``. Anything else is
    left to ``format_verified_latex``.
    """
    from sympy import cancel, expand, factor, fraction, latex, together

    symbols: set[Any] = set(getattr(expr, "free_symbols", set()))
    if len(symbols) != 1 or not expr.is_rational_function(*symbols):
        return format_verified_latex(expr)
    numerator, denominator = fraction(cancel(together(expr)))
    if not denominator.free_symbols:
        return format_verified_latex(expr)
    factored = factor(numerator)
    repeated = factored.is_Pow or (
        factored.is_Mul and any(part.is_Pow and part.free_symbols for part in factored.args)
    )
    top = factored if repeated else expand(numerator)
    bottom = factor(denominator)
    if top.could_extract_minus_sign() and not top.is_Add:
        return rf"- \frac{{{latex(-top)}}}{{{latex(bottom)}}}"
    return rf"\frac{{{latex(top)}}}{{{latex(bottom)}}}"


def format_verified_latex(expr: Any) -> str:
    """Exact latex when short; decimal via evalf when the exact form is a wall."""
    from sympy import latex, simplify

    val = simplify(expr)
    tex = str(latex(val))
    # A derivative or antiderivative stays exact: ``0.434294 x`` is not ``x / ln 10``.
    if len(tex) <= _EXACT_LATEX_DECIMAL_THRESHOLD or getattr(val, "free_symbols", None):
        return tex
    approximate = str(latex(val.evalf(6)))
    # ``evalf`` also converts harmless exact integer coefficients inside a
    # symbolic expression (``3`` -> ``3.0``).  Only use the approximation when
    # it actually makes a long exact result easier to read.
    return approximate if len(approximate) < len(tex) else tex


# Shallow LaTeX → SymPy-ish text. Nested \frac needs repeated passes (capped).
_LATEX_FRAC_RE = re.compile(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_LATEX_ABS_LEFT_RIGHT_RE = re.compile(
    r"\\(?:left|lvert)\s*\|\s*(.*?)\s*\\(?:right|rvert)\s*\|",
    re.DOTALL,
)
_LATEX_ABS_VERT_RE = re.compile(r"\\(?:lvert|rvert)\b")
_LATEX_SYMBOL_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\\infty"), "oo"),
    (re.compile(r"\\pi\b"), "pi"),
    (re.compile(r"\\cdot"), "*"),
    (re.compile(r"\\times"), "*"),
    (re.compile(r"\\div"), "/"),
    # Before \\left/\\right: \\le must not steal the prefix of \\left.
    (re.compile(r"\\leq"), "<="),
    (re.compile(r"\\geq"), ">="),
    (re.compile(r"\\le(?![a-zA-Z])"), "<="),
    (re.compile(r"\\ge(?![a-zA-Z])"), ">="),
    (re.compile(r"\\left"), ""),
    (re.compile(r"\\right"), ""),
]
_LATEX_FUNCTION_RE = re.compile(
    r"\\(sinh|cosh|tanh|coth|sech|csch|sin|cos|tan|sec|csc|cot|log|ln|sqrt|exp|min|max|Abs|abs)\b",
    re.IGNORECASE,
)
_TRIG_NAMES = f"({function_name_alternation(TRIG + HYPERBOLIC)})"
# ``\cot^{-1}(x)``, ``sinh^(-1) x`` and ``tan⁻¹ x`` name the inverse function,
# as on a school calculator. Read as a power they became ``1/cot(x)``, and the
# derivative of cot⁻¹(x) was certified as 1/cos²(x).
_INVERSE_POWER_RE = re.compile(
    rf"(?:\\|(?<![A-Za-z])){_TRIG_NAMES}\s*"
    r"(?:\^\s*\{\s*-\s*1\s*\}|\^\s*\(\s*-\s*1\s*\)|\^\s*-\s*1(?!\d)|\u207b\u00b9|\*\*\s*\(\s*-\s*1\s*\))"
)
# ``\arcsin`` … ``\arccsch`` are SymPy's ``asin`` … ``acsch``.
_ARC_NAME_RE = re.compile(rf"(?:\\|(?<![A-Za-z]))arc{_TRIG_NAMES}(?![A-Za-z])")


def _rewrite_inverse_functions(s: str) -> str:
    """``\\cot^{-1}`` / ``\\arccot`` → ``acot``; ``\\sinh^{-1}`` → ``asinh``."""
    # The trailing space keeps a glued argument apart: ``\\sin^{-1}x`` → ``asin x``.
    s = _ARC_NAME_RE.sub(lambda m: f"a{m.group(1).lower()} ", s)
    return _INVERSE_POWER_RE.sub(lambda m: f"a{m.group(1).lower()} ", s)


def _rewrite_bare_abs_bars(expr: str) -> str:
    """Rewrite paired ``|inner|`` → ``Abs(inner)``.

    Bare pipes are rejected by the expression allowlist; converting first lets
    homework like ``|x-2|<5`` reach SymPy without loosening ``_SAFE_EXPR_CHARS``.
    Unbalanced ``|`` is left as-is (still rejected later).
    """
    out: list[str] = []
    i = 0
    n = len(expr)
    while i < n:
        if expr[i] != "|":
            out.append(expr[i])
            i += 1
            continue
        depth = 0
        j = i + 1
        found = -1
        while j < n:
            ch = expr[j]
            if ch == "|" and depth == 0:
                found = j
                break
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
            j += 1
        if found == -1:
            out.append("|")
            i += 1
            continue
        inner = expr[i + 1 : found]
        if not inner.strip():
            out.append("|")
            i += 1
            continue
        out.append(f"Abs({inner})")
        i = found + 1
    return "".join(out)


# OCR / homework unicode operators → ASCII before the allowlist runs.
# Do NOT widen `_SAFE_EXPR_CHARS`; map glyphs here instead.
# Escapes (not literals) keep RUF001 from flagging lookalike punctuation.
_UNICODE_OP_SUBS: tuple[tuple[str, str], ...] = (
    ("\u00d7", "*"),  # U+00D7 multiplication sign
    ("\u22c5", "*"),  # U+22C5 dot operator
    ("\u00b7", "*"),  # U+00B7 middle dot
    ("\u2217", "*"),  # U+2217 asterisk operator
    ("\u00f7", "/"),  # U+00F7 division sign
    ("\u2215", "/"),  # U+2215 division slash
    ("\u2044", "/"),  # U+2044 fraction slash
    ("\u2212", "-"),  # U+2212 minus sign
    ("\u2013", "-"),  # U+2013 en dash
    ("\u2014", "-"),  # U+2014 em dash
    ("\u03c0", "pi"),  # π
    ("\u221e", "oo"),  # ∞
)

_UNICODE_VULGAR: tuple[tuple[str, str], ...] = (
    ("\u00bd", "(1)/(2)"),
    ("\u2153", "(1)/(3)"),
    ("\u2154", "(2)/(3)"),
    ("\u00bc", "(1)/(4)"),
    ("\u00be", "(3)/(4)"),
    ("\u2155", "(1)/(5)"),
    ("\u2156", "(2)/(5)"),
    ("\u2157", "(3)/(5)"),
    ("\u2158", "(4)/(5)"),
    ("\u2159", "(1)/(6)"),
    ("\u215a", "(5)/(6)"),
    ("\u215b", "(1)/(8)"),
    ("\u215c", "(3)/(8)"),
    ("\u215d", "(5)/(8)"),
    ("\u215e", "(7)/(8)"),
)

_SUP_GLYPHS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_SUP_ASCII = "0123456789"
_SUB_GLYPHS = "₀₁₂₃₄₅₆₇₈₉"
_SUB_ASCII = "0123456789"
_SUP_TABLE = str.maketrans(_SUP_GLYPHS, _SUP_ASCII)
_SUB_TABLE = str.maketrans(_SUB_GLYPHS, _SUB_ASCII)


def _rewrite_unicode_script_runs(s: str) -> str:
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch in _SUP_GLYPHS:
            j = i + 1
            while j < n and s[j] in _SUP_GLYPHS:
                j += 1
            digits = s[i:j].translate(_SUP_TABLE)
            out.append(f"**{digits}" if len(digits) == 1 else f"**({digits})")
            i = j
            continue
        if ch in _SUB_GLYPHS:
            j = i + 1
            while j < n and s[j] in _SUB_GLYPHS:
                j += 1
            digits = s[i:j].translate(_SUB_TABLE)
            out.append(f"_{digits}")
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _read_brace_group(s: str, i: int) -> tuple[str, int] | None:
    if i >= len(s) or s[i] != "{":
        return None
    depth = 0
    j = i
    while j < len(s):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
        j += 1
    return None


def _rewrite_latex_sqrts(s: str) -> str:
    """`\\sqrt{x}` → sqrt(x); `\\sqrt[n]{x}` → (x)**(1/(n)). Linear scan."""
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        root_start = i + 1 if s[i] == "\\" else i
        if (
            s.startswith("sqrt", root_start)
            and (i == 0 or not s[i - 1].isalpha())
            and (root_start + 4 >= n or not s[root_start + 4].isalpha())
            and (s[i] == "\\" or s[root_start + 4 : root_start + 5] in {"[", "{"})
        ):
            j = root_start + 4
            degree: str | None = None
            if j < n and s[j] == "[":
                close = s.find("]", j + 1)
                if close == -1:
                    out.append(s[i])
                    i += 1
                    continue
                degree = s[j + 1 : close]
                j = close + 1
            while j < n and s[j] == " ":
                j += 1
            grp = _read_brace_group(s, j)
            if grp is not None:
                body, j = grp
            else:
                k = j
                while k < n and (s[k].isalnum() or s[k] == "."):
                    k += 1
                if k == j:
                    out.append(s[i])
                    i += 1
                    continue
                body = s[j:k]
                j = k
            if degree is not None and degree.strip():
                out.append(f"({body})**(1/({degree}))")
            else:
                out.append(f"sqrt({body})")
            i = j
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _implicit_mul_before_sqrt(s: str) -> str:
    """`6sqrt(4)` → `6*sqrt(4)` so juxtaposition is multiplication, not a 6th root."""
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if s.startswith("sqrt(", i):
            prev = ""
            for ch in reversed(out):
                if not ch.isspace():
                    prev = ch
                    break
            if prev and (prev.isdigit() or prev in ")."):
                out.append("*")
        out.append(s[i])
        i += 1
    return "".join(out)


_UNICODE_HIGHER_ROOTS = {"\u221b": "3", "\u221c": "4"}  # cube and fourth root signs


def _rewrite_unicode_higher_roots(s: str) -> str:
    """``∛(x)`` / ``∛8`` → ``((x))**(1/3)``; a sign with nothing after it is left alone."""
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        index = _UNICODE_HIGHER_ROOTS.get(s[i])
        if index is None:
            out.append(s[i])
            i += 1
            continue
        j = i + 1
        while j < n and s[j] in " \t":
            j += 1
        if j < n and s[j] == "(":
            depth = 1
            k = j + 1
            while k < n and depth:
                depth += {"(": 1, ")": -1}.get(s[k], 0)
                k += 1
            if depth:
                out.append(s[i])
                i += 1
                continue
            body = s[j + 1 : k - 1]
        else:
            k = j
            while k < n and (s[k].isalnum() or s[k] == "."):
                k += 1
            body = s[j:k]
        if not body.strip():
            out.append(s[i])
            i += 1
            continue
        out.append(f"(({body})**(1/{index}))")
        i = k
    return "".join(out)


def _rewrite_unicode_sqrts(s: str) -> str:
    """``√9`` / ``√x`` / ``√(x+1)`` → ``sqrt(...)``. Linear scan, leftover ``√`` → ``sqrt``."""
    out: list[str] = []
    i = 0
    n = len(s)
    root = "\u221a"
    while i < n:
        if s[i] != root:
            out.append(s[i])
            i += 1
            continue
        i += 1
        while i < n and s[i] in " \t":
            i += 1
        if i >= n:
            out.append("sqrt")
            break
        if s[i] == "(":
            depth = 1
            j = i + 1
            while j < n and depth:
                if s[j] == "(":
                    depth += 1
                elif s[j] == ")":
                    depth -= 1
                j += 1
            if depth == 0:
                out.append("sqrt(")
                out.append(s[i + 1 : j - 1])
                out.append(")")
                i = j
                continue
            out.append("sqrt")
            continue
        if s[i].isdigit():
            j = i
            while j < n and s[j].isdigit():
                j += 1
            if j < n and s[j] == "." and j + 1 < n and s[j + 1].isdigit():
                j += 1
                while j < n and s[j].isdigit():
                    j += 1
            out.append("sqrt(")
            out.append(s[i:j])
            out.append(")")
            i = j
            continue
        if s[i].isalpha():
            out.append("sqrt(")
            out.append(s[i])
            out.append(")")
            i += 1
            continue
        out.append("sqrt")
    return "".join(out)


def _strip_math_dollar_delims(s: str) -> str:
    """Composer/math keyboard wraps expressions in ``$...$`` / ``\\(...\\)``.

    ``$`` / ``{}`` are not equation-side characters, so ``$x^{6}=1$`` used to
    extract an empty LHS and skip SymPy — then the tool loop blocked on R1.
    """
    return (
        s.replace("$$", "")
        .replace("$", "")
        .replace("\\(", "")
        .replace("\\)", "")
        .replace("\\[", "")
        .replace("\\]", "")
    )


def _rewrite_latex_braced_scripts_once(s: str) -> str:
    """One pass: ``x^{6}`` → ``x^6``; ``^{x}^{2}`` → ``x^{2}``."""
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if s.startswith("^{", i):
            grp = _read_brace_group(s, i + 1)
            if grp is None:
                out.append(s[i])
                i += 1
                continue
            body, j = grp
            if s.startswith("^{", j):
                nxt = _read_brace_group(s, j + 1)
                if nxt is not None:
                    # ^{a}^{b} → a^{b} (math-keyboard x² chain).
                    out.append(body)
                    out.append("^{")
                    out.append(nxt[0])
                    out.append("}")
                    i = nxt[1]
                    continue
            if body and all(ch.isalnum() or ch in ".-" for ch in body):
                out.append("^")
                out.append(body)
            else:
                out.append("^(")
                out.append(body)
                out.append(")")
            i = j
            continue
        if s.startswith("_{", i):
            grp = _read_brace_group(s, i + 1)
            if grp is None:
                out.append(s[i])
                i += 1
                continue
            body, j = grp
            if body and all(ch.isalnum() or ch in ".-" for ch in body):
                out.append("_")
                out.append(body)
            else:
                out.append("_(")
                out.append(body)
                out.append(")")
            i = j
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _rewrite_latex_braced_scripts(s: str) -> str:
    """``x^{6}`` → ``x^6``; ``^{x}^{2}`` → ``x^2``. Linear scan, no regex."""
    for _ in range(8):
        nxt = _rewrite_latex_braced_scripts_once(s)
        if nxt == s:
            return s
        s = nxt
    return s


def _rewrite_log_bases_once(s: str) -> str:
    """``log_2(x)`` -> ``ln(x)/ln(2)`` without dropping the logarithm.

    The equation scanner intentionally rejects underscores. Previously it
    resumed at the base digit, turning ``log_2(x-1)`` into ``2(x-1)`` and
    certifying an entirely different equation. Numeric bases cover ordinary
    school notation while keeping the safe-expression grammar narrow.
    """
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if not s.startswith("log_", i) or (i > 0 and s[i - 1].isalpha()):
            out.append(s[i])
            i += 1
            continue
        base_start = i + 4
        base_end = base_start
        while base_end < n and (s[base_end].isdigit() or s[base_end] == "."):
            base_end += 1
        if base_end == base_start:
            out.append(s[i])
            i += 1
            continue
        paren = base_end
        while paren < n and s[paren].isspace():
            paren += 1
        if paren >= n or s[paren] != "(":
            out.append(s[i])
            i += 1
            continue
        depth = 1
        close = paren + 1
        while close < n and depth:
            if s[close] == "(":
                depth += 1
            elif s[close] == ")":
                depth -= 1
            close += 1
        if depth:
            out.append(s[i])
            i += 1
            continue
        base = s[base_start:base_end]
        body = s[paren + 1 : close - 1]
        out.append(f"(ln({body})/ln({base}))")
        i = close
    return "".join(out)


# ``log2(x)`` and ``log10(x)`` are written bases. Without this the digits end a
# letter run and implicit multiplication reads ``l*o*g*2*x``.
_GLUED_LOG_BASE_RE = re.compile(r"(?<![A-Za-z_\\])log(\d+)(?=\s*\()")

# ``sinx`` / ``sin2x`` / ``lnx`` are sin(x), sin(2x), ln(x). The argument is
# digits and one letter; anything longer (``sinx^2``, ``sinxy``) is left alone so
# the written-letter guard declines it instead of guessing.
_GLUED_FUNCTION_ARG_RE = re.compile(
    r"(?<![A-Za-z_\\])(sin|cos|tan|sec|csc|cot|ln)(\d*[a-z])(?![A-Za-z(_^\d])"
)


def _rewrite_glued_function_args(s: str) -> str:
    # ``\log_2`` keeps its backslash: ``_`` is a word character, so the LaTeX
    # function pattern's ``\b`` never matched it.
    s = s.replace("\\log_", "log_")
    s = _GLUED_LOG_BASE_RE.sub(r"log_\1", s)
    return _GLUED_FUNCTION_ARG_RE.sub(r"\1(\2)", s)


def _rewrite_log_bases(s: str) -> str:
    s = _rewrite_glued_function_args(s)
    for _ in range(8):
        nxt = _rewrite_log_bases_once(s)
        if nxt == s:
            return s
        s = nxt
    return s


def _normalize_latex_to_sympy(expr: str) -> str:
    """Expand common LaTeX so pasted/OCR homework can pass the safe-char gate."""
    s = _strip_math_dollar_delims(expr)
    s = _rewrite_inverse_functions(s)
    for glyph, repl in _UNICODE_OP_SUBS:
        s = s.replace(glyph, repl)
    for glyph, repl in _UNICODE_VULGAR:
        s = s.replace(glyph, repl)
    s = _rewrite_unicode_higher_roots(s)
    s = _rewrite_unicode_sqrts(s)
    s = _rewrite_unicode_script_runs(s)
    for _ in range(8):
        nxt = _rewrite_latex_sqrts(s)
        if nxt == s:
            break
        s = nxt
    s = _implicit_mul_before_sqrt(s)
    s = _LATEX_ABS_LEFT_RIGHT_RE.sub(r"Abs(\1)", s)
    s = _LATEX_ABS_VERT_RE.sub("", s)
    for pattern, replacement in _LATEX_SYMBOL_SUBS:
        s = pattern.sub(replacement, s)

    def _func_repl(match: re.Match[str]) -> str:
        name = match.group(1).lower()
        return "Abs" if name == "abs" else name

    s = _LATEX_FUNCTION_RE.sub(_func_repl, s)
    for _ in range(8):
        nxt = _LATEX_FRAC_RE.sub(r"((\1)/(\2))", s)
        if nxt == s:
            break
        s = nxt
    s = _rewrite_bare_abs_bars(s)
    s = _rewrite_latex_braced_scripts(s)
    s = _rewrite_log_bases(s)
    return s


# A glued exponent ends the token. `^` is absent so `x2^3` is left for
# implicit multiplication (`x*2**3`), and `(` is absent so `log2(8)` stays a name.
_GLUED_EXPONENT_END = frozenset("+-*/=<>),] \t\n")


def _lift_glued_exponents(text: str) -> str:
    """`3x2+4` is `3x**2+4`, not `3*x*2`.

    Homework and OCR write `x2` for `x^2`. Implicit multiplication would
    otherwise split that into `x*2` and solve a different equation (`6x`).
    `x0` / `x1` stay names, and a digit run after another letter (`sin2`,
    `log2`) is not an exponent.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        prev = text[i - 1] if i else ""
        if ch.isalpha() and not prev.isalpha() and prev != "\\":
            j = i + 1
            if j < n and text[j].isdigit():
                k = j + 1
                while k < n and text[k].isdigit():
                    k += 1
                digits = text[j:k]
                nxt = text[k] if k < n else ""
                if digits not in {"0", "1"} and (k == n or nxt in _GLUED_EXPONENT_END):
                    out.append(ch)
                    out.append("**")
                    out.append(digits)
                    i = k
                    continue
        out.append(ch)
        i += 1
    return "".join(out)


def _normalize_expr(text: str) -> str:
    s = text.strip()
    s = _normalize_latex_to_sympy(s)
    # Lift `x2` before `^` becomes `**`, so a real caret (`x2^3`) is not
    # reread as a glued exponent.
    s = _lift_glued_exponents(s)
    s = s.replace("^", "**")
    # Python tokenizes 0x as the start of a hexadecimal literal before
    # SymPy's implicit-multiplication transform can see it. Explicitly mark
    # every number-letter boundary (2x, 0x, 3pi) as multiplication.
    s = re.sub(r"(?<=\d)(?=[A-Za-z])", "*", s)
    s = re.sub(r"\s+", " ", s)
    return s


# Only characters a real math expression ever needs. Rejects backslashes,
# quotes, braces, semicolons, and every other punctuation a Python-eval
# gadget would need to reach beyond a plain arithmetic/algebraic expression.
_SAFE_EXPR_CHARS = re.compile(r"^[\w\s+\-*/().,=<>!]*$")
_DECIMAL_NUMBER = re.compile(r"\d+\.\d+|\.\d+|\d+\.")


def _reject_unsafe_expr(normalized: str) -> None:
    """BUG FIX (was a live RCE): parse_expr/sympify evaluate the input via
    Python's eval() internally. Restricting local_dict to declared variable
    names (as this module already did) only stops BARE names from resolving
    to something dangerous via auto_symbol — it does nothing to stop
    ATTRIBUTE ACCESS on an already-resolved object. A Symbol instance is a
    real Python object, so "x.__class__.__mro__[1].__subclasses__()[N](...)"
    is valid Python syntax that walks the class hierarchy to reach e.g.
    subprocess.Popen and executes arbitrary shell commands — entirely inside
    SymPy's parse-time eval(), no further .doit()/evaluation needed. This is
    reachable from a plain chat message (math/tools keyword-triggered
    intent extraction has no sanitization) and from the sympy MCP tool the
    model can call directly. SymPy's own docs are explicit that
    sympify/parse_expr must never see untrusted input un-validated.

    Reject anything that isn't plainly arithmetic/algebraic before it ever
    reaches parse_expr: no "__" (blocks every dunder-attribute gadget chain),
    no "." outside a decimal number (blocks attribute access while still
    allowing "3.14"), no "[" or "]" (blocks subscripting), and a strict
    character allowlist as a second, independent layer against whatever this
    doesn't anticipate. Do not loosen this without a real threat-model
    review — this is the only thing standing between a chat message and
    eval() in the API process.
    """
    if "__" in normalized:
        raise MathServiceError("Invalid expression")
    if "[" in normalized or "]" in normalized:
        raise MathServiceError("Invalid expression")
    if "." in _DECIMAL_NUMBER.sub("", normalized):
        raise MathServiceError("Invalid expression")
    if not _SAFE_EXPR_CHARS.match(normalized):
        raise MathServiceError("Invalid expression")


# Longest first, so ``sinh`` is not read as ``sin`` + ``h``.
_FUNCTION_WORDS = names_longest_first(MATH_FUNCTION_NAMES)
# A unit after a number is not a product of variables: ``5 kg`` is not 5*k*g.
_UNIT_AFTER_NUMBER_RE = re.compile(
    r"(?<=\d)\s*(?:kg|km|cm|mm|mg|mL|ml|ms|mol|kJ|kN|kW|kPa|hPa|Pa|Hz|hrs?|min|mph)\b"
)
_LETTER_RUN_RE = re.compile(r"[^\W\d_]+")


def _written_letters(text: str) -> set[str]:
    """Single letters the writer used as names, not inside a function or unit word."""
    letters: set[str] = set()
    for run in _LETTER_RUN_RE.findall(_UNIT_AFTER_NUMBER_RE.sub(" ", text)):
        lowered = run.lower()
        for word in _FUNCTION_WORDS:
            if lowered.startswith(word):
                run = run[len(word) :]
                break
        letters.update(run)
    return letters


def _reject_unwritten_symbols(expr: str, parsed: Any) -> None:
    """Every one-letter symbol must be a letter the writer wrote as a name.

    Implicit multiplication splits any letter run it cannot resolve, so
    ``log2(x)`` became ``2*g*l*o*x``, ``cos2x`` became ``2*c*o*s*x`` and
    ``5 kg`` became ``5*g*k``; each then solved as ordinary algebra and was
    certified. A symbol that only exists inside such a word means the parse
    is not what was written.
    """
    names = {symbol.name for symbol in getattr(parsed, "free_symbols", ()) if len(symbol.name) == 1}
    if names and not names <= _written_letters(expr):
        raise MathServiceError(f"Could not parse expression: {expr}")


def _parse_expression(
    expr: str,
    variable_names: list[str] | None = None,
    *,
    real: bool = False,
    evaluate: bool = True,
):
    normalized = _normalize_expr(expr)
    if len(normalized) > get_settings().math_max_expr_length:
        raise MathServiceError("Expression too long")
    _reject_unsafe_expr(normalized)
    local_dict = dict(_LOCALS)
    if variable_names:
        for name in variable_names:
            local_dict[name] = Symbol(name, real=True) if real else Symbol(name)
    try:
        parsed = parse_expr(
            normalized,
            local_dict=local_dict,
            transformations=_TRANSFORMATIONS,
            evaluate=evaluate,
        )
    except Exception as exc:
        raise MathServiceError(f"Could not parse expression: {expr}") from exc
    _reject_unwritten_symbols(expr, parsed)
    return parsed


def _expr_needs_real_domain(*parts: str) -> bool:
    """Abs-value homework needs a real domain; SymPy rejects Abs(complex) solve."""
    return any("Abs(" in p or "abs(" in p for p in parts)


def parse_equation(data: EquationInput) -> tuple[Any, Any, list[Any]]:
    real = _expr_needs_real_domain(data.lhs, data.rhs)
    lhs = _parse_expression(data.lhs, data.variables, real=real)
    rhs = _parse_expression(data.rhs, data.variables, real=real)
    return Eq(lhs, rhs), lhs, rhs
