"""Closed number facts asked in words.

Roots (``cube root of 27``), a fraction or decimal as a percentage, standard
form, and the sum of the first n natural, odd or even numbers. Each writes one
working line and leaves the result to the answer.
"""

from __future__ import annotations

import re
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from app.modules.math.schemas import MathIntent
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.services.workout import math_line

NUMBER_FACT_OPS = frozenset({"root_words", "to_percent", "standard_form", "first_n_sum"})

_ASK = r"(?:(?:what\s+is|what's|whats|find|calculate|work\s+out|evaluate|give)\s+)?(?:the\s+)?"
_ROOT_NAMES = {"square": 2, "cube": 3, "fourth": 4, "fifth": 5, "sixth": 6}
_ROOT = re.compile(
    rf"{_ASK}(square|cube|fourth|fifth|sixth)\s+root\s+of\s+(\d+(?:\.\d+)?)", re.IGNORECASE
)
_PERCENT = re.compile(
    rf"(?:convert\s+|write\s+|express\s+|{_ASK})(\d+\s*/\s*\d+|\d*\.\d+|\d+)\s+"
    r"(?:to|into|as)\s+(?:a\s+)?percent(?:age)?",
    re.IGNORECASE,
)
_STANDARD_FORM = re.compile(
    r"(?:write|convert|express|put)\s+(-?\d[\d,]*(?:\.\d+)?|-?\.\d+)\s+(?:in|into|as|to)\s+"
    r"(?:standard\s+form|scientific\s+notation)",
    re.IGNORECASE,
)
_FIRST_N = re.compile(
    r"(?:(?:what\s+is|find|calculate|work\s+out)\s+)?(?:the\s+)?sum\s+of\s+(?:the\s+)?first\s+"
    r"(\d{1,6})\s+(natural|counting|positive|whole|odd|even)\s+(?:numbers|integers)",
    re.IGNORECASE,
)


def _body(text: str) -> str:
    return " ".join(text.split()).strip().rstrip("?.!").strip()


def extract_number_fact_intent(cleaned: str) -> MathIntent | None:
    body = _body(cleaned)
    if not body or len(body) > 200:
        return None
    root = _ROOT.fullmatch(body)
    if root is not None:
        return MathIntent(
            kind="arithmetic",
            school_op="root_words",
            combo_n=_ROOT_NAMES[root.group(1).lower()],
            expr=root.group(2),
            operation="solve",
        )
    percent = _PERCENT.fullmatch(body)
    if percent is not None:
        return MathIntent(
            kind="arithmetic",
            school_op="to_percent",
            expr=percent.group(1).replace(" ", ""),
            operation="solve",
        )
    standard = _STANDARD_FORM.fullmatch(body)
    if standard is not None:
        return MathIntent(
            kind="arithmetic",
            school_op="standard_form",
            expr=standard.group(1).replace(",", ""),
            operation="solve",
        )
    first = _FIRST_N.fullmatch(body)
    if first is not None:
        kind = first.group(2).lower()
        return MathIntent(
            kind="arithmetic",
            school_op="first_n_sum",
            combo_n=int(first.group(1)),
            trial_outcome=kind if kind in {"odd", "even"} else "natural",
            operation="solve",
        )
    return None


def _number(value: float) -> str:
    return f"{value:g}"


def _root_parts(value: int, index: int) -> tuple[int, int]:
    """``50`` under a square root -> ``(5, 2)``: 5 sqrt(2). The outside and inside factors."""
    outside, inside = 1, value
    factor = 2
    while factor**index <= inside:
        while inside % factor**index == 0:
            inside //= factor**index
            outside *= factor
        factor += 1
    return outside, inside


def _root(intent: MathIntent) -> tuple[str, str] | None:
    index, text = intent.combo_n or 2, intent.expr or ""
    symbol = r"\sqrt" if index == 2 else rf"\sqrt[{index}]"
    if "." in text:
        value = float(text)
        result = value ** (1 / index)
        return f"{symbol}{{{text}}}", f"{result:.4g}"
    number = int(text)
    whole = round(number ** (1 / index))
    for candidate in (whole - 1, whole, whole + 1):
        if candidate >= 0 and candidate**index == number:
            return f"{symbol}{{{number}}} = {symbol}{{{candidate}^{{{index}}}}}", str(candidate)
    outside, inside = _root_parts(number, index)
    approx = f"{number ** (1 / index):.4g}"
    if outside == 1:
        return f"{symbol}{{{number}}}", rf"{symbol}{{{number}}} \approx {approx}"
    return (
        f"{symbol}{{{number}}} = {symbol}{{{outside}^{{{index}}} \\times {inside}}}",
        rf"{outside}{symbol}{{{inside}}} \approx {approx}",
    )


def _to_percent(intent: MathIntent) -> tuple[str, str] | None:
    text = intent.expr or ""
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None
    percent = value * 100
    exact = _terminates(percent)
    if percent.denominator == 1:
        shown = f"{percent.numerator}\\%"
    elif exact:
        shown = f"{_decimal_text(percent)}\\%"
    else:
        # 2/3 is 200/3 % exactly, about 66.67%.
        fraction = rf"\frac{{{percent.numerator}}}{{{percent.denominator}}}"
        shown = rf"{fraction}\% \approx {float(percent):.2f}\%"
    if "/" in text:
        top, bottom = text.split("/")
        working = rf"\frac{{{top}}}{{{bottom}}} \times 100\%"
        if exact:
            working += rf" = \frac{{{int(top) * 100}}}{{{bottom}}}\%"
    else:
        working = rf"{text} \times 100\%"
    return working, shown


def _terminates(value: Fraction) -> bool:
    denominator = value.denominator
    for prime in (2, 5):
        while denominator % prime == 0:
            denominator //= prime
    return denominator == 1


def _decimal_text(value: Fraction) -> str:
    """A terminating decimal, written exactly: 37.5, not 37.50000."""
    return f"{Decimal(value.numerator) / Decimal(value.denominator):f}".rstrip("0").rstrip(".")


def _standard_form(intent: MathIntent) -> tuple[str, str] | None:
    try:
        value = Decimal(intent.expr or "")
    except InvalidOperation:
        return None
    if value == 0:
        return None
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    exponent = magnitude.adjusted()
    mantissa = (magnitude / Decimal(10) ** exponent).normalize()
    shown = f"{sign}{mantissa:f} \\times 10^{{{exponent}}}"
    places = abs(exponent)
    direction = "left" if exponent > 0 else "right"
    note = (
        f"move the decimal point {places} place{'s' if places != 1 else ''} {direction}"
        if exponent
        else "already between 1 and 10"
    )
    return rf"{sign}{magnitude.normalize():f} = {shown}|{note}", shown


def _first_n(intent: MathIntent) -> tuple[str, str] | None:
    n = intent.combo_n
    if n is None or n < 1:
        return None
    kind = intent.trial_outcome
    if kind == "odd":
        return rf"1 + 3 + \cdots + {2 * n - 1} = {n}^{{2}}", str(n * n)
    if kind == "even":
        return rf"2 + 4 + \cdots + {2 * n} = {n}({n} + 1)", str(n * (n + 1))
    return (
        rf"1 + 2 + \cdots + {n} = \frac{{{n}({n} + 1)}}{{2}} = \frac{{{n} \times {n + 1}}}{{2}}",
        str(n * (n + 1) // 2),
    )


def number_fact_block(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    solved = {
        "root_words": _root,
        "to_percent": _to_percent,
        "standard_form": _standard_form,
        "first_n_sum": _first_n,
    }[intent.school_op or ""](intent)
    if solved is None:
        return None
    working, answer = solved
    working, _, note = working.partition("|")
    lines.append(f"Working: ${working}$")
    block = _finish_with_answer(lines, answer)
    shown = math_line(working, note or None)
    return replace(block, worked_reply=f"{shown}\n\n```answer\n{answer}\n```\n")
