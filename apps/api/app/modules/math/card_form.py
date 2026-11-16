"""A verified card in the form the reply's own working reaches.

SymPy writes its result in its own form. A reply that worked ∫ sec(2x - π/4) tan(2x - π/4) dx
to ½ sec(2x - π/4) + C carried a checked card of csc(2x + π/4)/2 + C, a form the working
never reaches; ln|1 - cos 2t|/2 + C stood over ln|2 cos 2t - 2|/2 + C, the same
antiderivative shifted by a constant (live round, Grade 12 unit 5, 2026-11-16). Both are
right, and a student reading the card cannot tell.

One rule: the card shows the value the reply states (its Answer, or the last line of its
working) when SymPy finds it the same value as the server's: equal everywhere both are
defined, or, for an antiderivative (a card ending ``+ C``), equal up to a constant. Any other
reply, a wrong one or one that never reaches a value, keeps the server's form, and the
correction line the fence pass writes for a different value stays as it is.
"""

from __future__ import annotations

import cmath
import logging
import math
import re
from typing import Any

from app.modules.math.fence_answer import same_spelling
from app.modules.math.solve.latex_normalize import rewrite_abs_bars
from app.modules.math.tool_check import parse_latex_formula
from app.services.answer_fence import answer_fence_value, stated_answers
from app.services.card_text import card_maths
from app.services.latex_groups import map_groups

logger = logging.getLogger(__name__)

# A card of one expression: no relation, list, words or several branches.
_NOT_ONE_EXPRESSION = re.compile(r"=|,|;|\\(?:text|mathrm|quad|pm|mp|approx|begin|cup)\b|\n|≈")
_CONSTANT = re.compile(r"\s*\+\s*C\s*$")
_DECIMAL = re.compile(r"\d\.\d")
_WHOLE_MATH = re.compile(r"\$\$?([^$]+)\$\$?")
# A script TeX reads as one character, written as more: "x^12" is x^1 times 2, "x^-1".
_LOOSE_SCRIPT = re.compile(r"[\^_](?:-|\d{2})")
_STYLE = re.compile(r"\\(?:displaystyle|textstyle)\s*")
# Commands that only size or space what they stand by.
_SIZING = re.compile(r"\\(?:left|right|[bB]igg?[lr]?|displaystyle|textstyle)(?![A-Za-z])")
_SPACING = re.compile(r"\\[,;:! ]|\\q?quad(?![A-Za-z])")
_FRACTION = re.compile(r"\\[dt]frac(?![A-Za-z])")
# A function's argument in braces, SymPy's own spelling: \csc{\left(2 x\right)}, \cos^{3}{(x)}.
_BRACED_ARGUMENT = re.compile(
    r"\\(sinh|cosh|tanh|sin|cos|tan|sec|csc|cot|ln|log|exp)(\^\{?-?\d+\}?)?\s*\{"
)
_SAMPLES = (0.37, 0.71, 1.29, 1.83, 2.57, 3.41, -0.43, -1.27, -2.11, 4.73)
_MIN_SAMPLES = 4


def read_tex(tex: str) -> Any | None:
    """``tex`` as one SymPy expression, read the way the solver reads typed LaTeX, with the
    spellings SymPy itself writes (a function's braced argument, |…| after ln); None when
    it does not read."""
    text = _FRACTION.sub(r"\\frac", _SPACING.sub(" ", _SIZING.sub("", tex.replace("$", ""))))
    for _ in range(4):
        unbraced = map_groups(
            text,
            _BRACED_ARGUMENT,
            lambda outside: outside,
            lambda opened, inside: f"\\{opened.group(1)}{opened.group(2) or ''}({inside})",
        )
        if unbraced == text:
            break
        text = unbraced
    return parse_latex_formula(rewrite_abs_bars(text, apart=True))


def _value(expr: Any, point: dict[Any, float]) -> complex | None:
    try:
        value = complex(expr.evalf(subs=point))
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    return value if cmath.isfinite(value) else None


def _real(value: complex | None) -> float | None:
    if value is None or abs(value.imag) > 1e-9 * max(1.0, abs(value.real)):
        return None
    return value.real


def same_value(server: Any, stated: Any, *, up_to_constant: bool) -> bool:
    """``stated`` is ``server``: equal where both are real, or with ``up_to_constant`` apart
    by one constant; real at the same sample points, and at enough of them."""
    symbols = sorted(server.free_symbols, key=str)
    if set(symbols) != stated.free_symbols:
        return False
    gaps: list[float] = []
    sizes: list[float] = []
    for sample in _SAMPLES if symbols else _SAMPLES[:1]:
        point = {symbol: sample + 0.13 * number for number, symbol in enumerate(symbols)}
        mine, theirs = _real(_value(server, point)), _real(_value(stated, point))
        if (mine is None) != (theirs is None):
            return False
        if mine is None or theirs is None:
            continue
        gaps.append(mine - theirs)
        sizes.append(max(1.0, abs(mine)))
    if not gaps or (symbols and len(gaps) < _MIN_SAMPLES):
        return False
    base = gaps[0] if up_to_constant else 0.0
    pairs = zip(gaps, sizes, strict=True)
    return all(math.isclose(gap, base, abs_tol=1e-9 * size) for gap, size in pairs)


def _right_side(value: str) -> str | None:
    """What a stated line of maths gives: after its last ``=`` ("∫ … dx = ½ sec(…) + C").
    None for a sentence ("At $x = 1$: $…$"): only a line that is all maths states a value."""
    plain = value.strip().rstrip(".").strip()
    whole = _WHOLE_MATH.fullmatch(plain)
    if whole is not None:
        plain = whole.group(1)
    elif "$" in plain:
        return None
    side = plain.rsplit("=", 1)[-1]
    return _STYLE.sub("", side).strip().rstrip(".").strip()


def in_working_form(reply: str, answer_body: str) -> str:
    """``answer_body``, or the value ``reply`` states in its place when it is the same
    value (the module's rule): its working's last line, else its Answer's; an
    antiderivative's line gains the card's + C. Runs in the SymPy pool, as the fence pass
    does."""
    value = answer_fence_value(answer_body)
    if not value or _NOT_ONE_EXPRESSION.search(_SPACING.sub(" ", value)) is not None:
        return answer_body
    antiderivative = _CONSTANT.search(value) is not None
    for stated in stated_answers(reply):
        shown = _right_side(stated) or ""
        if antiderivative and shown and not _CONSTANT.search(shown):
            shown += " + C"  # the working's last line before its constant is written
        if shown and _same_form_as_working(shown, value):
            return card_maths(shown)
    return answer_body


def _same_form_as_working(shown: str, value: str) -> bool:
    """``shown``, a line the reply states, is ``value`` in another form the card may show."""
    antiderivative = _CONSTANT.search(value) is not None
    if antiderivative != (_CONSTANT.search(shown) is not None):
        return False  # an antiderivative keeps its + C; a value gains none
    if _NOT_ONE_EXPRESSION.search(_SPACING.sub(" ", shown)) or "\\int" in shown:
        return False
    if _DECIMAL.search(shown) and not _DECIMAL.search(value):
        return False  # an exact value is never shown rounded
    if _LOOSE_SCRIPT.search(shown + value) or same_spelling(shown, value):
        return False  # a malformed script, or the server's own form spaced otherwise
    server = read_tex(_CONSTANT.sub("", value))
    mine = read_tex(_CONSTANT.sub("", shown))
    if server is None or mine is None or server.is_Number:
        return False  # a number is written one way ("27/3 - 0" is 9, "0.15 * 85" is 12.75)
    try:
        return same_value(server, mine, up_to_constant=antiderivative)
    except Exception:
        logger.info("the working's form was not compared; the card keeps SymPy's", exc_info=True)
        return False
