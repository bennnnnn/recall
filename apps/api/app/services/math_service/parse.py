"""Parse/normalize expressions for SymPy (server-side only)."""

from __future__ import annotations

import logging
import math
import re
from typing import Any

from sympy import Abs, Eq, Symbol, parse_expr
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    standard_transformations,
)

from app.core.config import get_settings
from app.models.math_schemas import EquationInput

logger = logging.getLogger(__name__)

_TRANSFORMATIONS = (
    *standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)
_LOCALS: dict[str, Any] = {
    "pi": math.pi,
    "e": math.e,
    "Abs": Abs,
}


class MathServiceError(ValueError):
    """Invalid or unsupported math input."""


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
    r"\\(sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan|sinh|cosh|tanh|log|ln|sqrt|exp|min|max|Abs|abs)\b",
    re.IGNORECASE,
)


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
        if s.startswith("\\sqrt", i) and (i + 5 >= n or not s[i + 5].isalpha()):
            j = i + 5
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


def _normalize_latex_to_sympy(expr: str) -> str:
    """Expand common LaTeX so pasted/OCR homework can pass the safe-char gate."""
    s = expr
    for glyph, repl in _UNICODE_OP_SUBS:
        s = s.replace(glyph, repl)
    for glyph, repl in _UNICODE_VULGAR:
        s = s.replace(glyph, repl)
    s = re.sub("\u221a\\s*\\(([^()]*)\\)", r"sqrt(\1)", s)
    s = s.replace("\u221a", "sqrt")
    s = _rewrite_unicode_script_runs(s)
    s = _rewrite_latex_sqrts(s)
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
        nxt = _LATEX_FRAC_RE.sub(r"(\1)/(\2)", s)
        if nxt == s:
            break
        s = nxt
    s = _rewrite_bare_abs_bars(s)
    return s


def _normalize_expr(text: str) -> str:
    s = text.strip()
    s = _normalize_latex_to_sympy(s)
    s = s.replace("^", "**")
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
    reachable from a plain chat message (math_tools.py's keyword-triggered
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


def _parse_expression(
    expr: str,
    variable_names: list[str] | None = None,
    *,
    real: bool = False,
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
        return parse_expr(
            normalized,
            local_dict=local_dict,
            transformations=_TRANSFORMATIONS,
            evaluate=True,
        )
    except Exception as exc:
        raise MathServiceError(f"Could not parse expression: {expr}") from exc


def _expr_needs_real_domain(*parts: str) -> bool:
    """Abs-value homework needs a real domain; SymPy rejects Abs(complex) solve."""
    return any("Abs(" in p or "abs(" in p for p in parts)


def parse_equation(data: EquationInput) -> tuple[Any, Any, list[Any]]:
    real = _expr_needs_real_domain(data.lhs, data.rhs)
    lhs = _parse_expression(data.lhs, data.variables, real=real)
    rhs = _parse_expression(data.rhs, data.variables, real=real)
    return Eq(lhs, rhs), lhs, rhs
