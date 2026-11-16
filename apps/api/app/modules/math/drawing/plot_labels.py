"""A graph's labels, written by the server from the values it worked out.

A value is written exactly when it is short that way (-7, 1/2, √5, π/4, e, 1/e) and as a
figure writes a decimal otherwise (1.165); a formula as a reader writes it (y = x² - 5x + 1, |ln x|,
xeˣ - 4). Every label is the server's: none is copied from the reply.
"""

from __future__ import annotations

import re
from typing import Any

from sympy import Expr, Float, Integer, Rational, exp, sympify
from sympy.printing.str import StrPrinter

from app.modules.math.drawing.real_curve import X
from app.modules.math.figure.drawing import number_text as decimal_text
from app.modules.math.tangent_line import slope_intercept
from app.services.glyphs import TO_SUPERSCRIPT

_MINUS = "\u2212"
_COMMON_LOG = re.compile(r"\bln( ?)(\([^()]*\)|\w+)/ln ?\(?10\)?")
_LABEL_CHARS = 48
# A value written exactly when that is this short (√5, π/4, 9/4, 28√2), else as a decimal.
_EXACT_CHARS = 5


def _closing(text: str, start: int) -> int:
    """The index of the bracket that closes the one opened just before ``start``."""
    depth = 1
    for i in range(start, len(text)):
        depth += {"(": 1, ")": -1}.get(text[i], 0)
        if depth == 0:
            return i
    return len(text)


def _calls(text: str) -> str:
    """Abs(u) as |u|, sqrt(u) as √u, exp(u) as e^u, log(u) as ln(u)."""
    for name in ("Abs(", "sqrt(", "exp(", "log("):
        while name in text:
            at = text.index(name)
            end = _closing(text, at + len(name))
            inner = _calls(text[at + len(name) : end])
            simple = inner.replace(".", "").isalnum()
            if name == "Abs(":
                shown = f"|{inner}|"
            elif name == "sqrt(":
                shown = f"√{inner}" if simple else f"√({inner})"
            elif name == "exp(":
                shown = "e\u02e3" if inner == "x" else f"e^({inner})"
            else:
                shown = f"ln {inner}" if simple else f"ln({inner})"
            text = text[:at] + shown + text[end + 1 :]
    return text


def _powers(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("**", i):
            j = i + 2
            digits = ""
            while j < len(text) and (text[j].isdigit() or (text[j] == "-" and j == i + 2)):
                digits += text[j]
                j += 1
            if digits and digits != "-":
                out.append(digits.translate(TO_SUPERSCRIPT))
                i = j
                continue
            out.append("^")
            i += 2
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _reading() -> Any:
    """SymPy's printing, a sum that would begin with a negative term written the other way
    round, as a question writes it: 9 - x², 3 - x, 5 - 2x² + 4x³ - x⁵."""
    printer = StrPrinter()
    ordered = printer._as_ordered_terms

    def terms_of(expr: Any, order: Any = None) -> list[Any]:
        terms = list(ordered(expr, order="lex"))
        if terms[0].could_extract_minus_sign() and not terms[-1].could_extract_minus_sign():
            return terms[::-1]
        return terms

    printer._as_ordered_terms = terms_of
    return printer


def formula_text(expr: Any) -> str:
    """``expr`` as a reader writes it: x² - 5x + 1, x/(x + 1)², |x² - 1|, 9 - x²."""
    text = _reading().doprint(expr).replace("exp(-1)", "(1/e)")
    text = _powers(_calls(text)).replace("*", "")
    words = {"pi": "π", "E": "e"}
    for word, shown in words.items():
        text = _whole_word(text, word, shown)
    if text == "(1/e)":
        text = "1/e"
    # SymPy holds log x as ln x/ln 10: written as the question writes it (i01).
    text = _COMMON_LOG.sub(r"log\1\2", text)
    return text.replace(" - ", f" {_MINUS} ").replace("-", _MINUS)


def _whole_word(text: str, word: str, shown: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        before = text[i - 1] if i else " "
        after = text[i + len(word)] if i + len(word) < len(text) else " "
        if text.startswith(word, i) and not before.isalpha() and not after.isalpha():
            out.append(shown)
            i += len(word)
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def number_text(value: Any) -> str:
    """A value the server worked out, exact when that is short, else as a figure prints a
    decimal (``figure.drawing.number_text``)."""
    number = sympify(value)
    if isinstance(number, Integer):
        return str(number).replace("-", _MINUS)
    if isinstance(number, Rational) and len(str(abs(number))) <= _EXACT_CHARS - 1:
        return str(number).replace("-", _MINUS)
    if isinstance(number, Expr) and not number.atoms(Float):
        if number == exp(-1):
            return "1/e"
        shown = formula_text(number)
        if len(shown.lstrip(_MINUS)) <= _EXACT_CHARS - 1:
            return shown
    text = decimal_text(float(number))
    return ("0" if text == "-0" else text).replace("-", _MINUS)


def point_text(x: Any, y: Any) -> str:
    return f"({number_text(x)}, {number_text(y)})"


def equation_text(name: str, expr: Any) -> str:
    """ "y = …" or "x = …", cut to nothing when too long to sit on a graph."""
    text = f"{name} = {formula_text(expr)}"
    return text if len(text) <= _LABEL_CHARS else ""


def line_text(slope: Any, offset: Any) -> str:
    """ "y = -x/2 + 3/2", the x term first (``tangent_line.slope_intercept``), cut to
    nothing when too long to sit on a graph."""
    text = slope_intercept(
        sympify(slope),
        sympify(offset),
        lambda m: formula_text(m * X),
        formula_text,
        minus=_MINUS,
    )
    return text if len(text) <= _LABEL_CHARS else ""
