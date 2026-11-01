"""Whether a rewrite's card only restates the expression it was asked to rewrite.

"Find the cube root of 27a^3 + 54a^2b + 36ab^2 + 8b^3." was read by a model as a
simplification of (27a^3 + …)^(1/3); SymPy left it as it was, and the checked card was
\\sqrt[3]{27 a^{3} + …}: the question (2026-11-01). "simplify (x+1)/(x-1)" got
\\frac{x + 1}{x - 1}. A simplification, factorisation or expansion whose card is the
expression it was given, or a root of it, answers nothing.

The card and the expression are compared as SymPy trees parsed as written, never as text:
1/x^2 is a rewrite of x^-2, x of -(-x), and 1/(x - 1) of (x+1)/(x-1) - x/(x-1). A number,
one letter or an equation is never a restatement.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from sympy import Rational

from app.modules.math.solve.declines import sympy_decline
from app.modules.math.solve.latex_normalize import normalize_latex_to_sympy
from app.modules.math.solve.parse import parse_expression

# The operations that rewrite one value: their card should differ from what they were given.
REWRITES = frozenset({"simplify", "factor", "expand"})
_CARD_PIECES = re.compile(r",|;|\\quad")


def card_restates(card: str, expressions: Sequence[str | None]) -> bool:
    """Every piece of ``card`` is one of ``expressions`` as written, or a root of one."""
    given = [_as_written(text) for text in expressions if text]
    given = [expr for expr in given if expr is not None]
    pieces = [piece for piece in _CARD_PIECES.split(card) if piece.strip()]
    return bool(given and pieces) and all(_restates(piece, given) for piece in pieces)


def _as_written(text: str) -> Any | None:
    with sympy_decline():
        return parse_expression(normalize_latex_to_sympy(text.replace("$", " ")), evaluate=False)
    return None


def _restates(piece: str, given: list[Any]) -> bool:
    if "=" in piece:
        return False
    card = _as_written(piece)
    if card is None or not getattr(card, "free_symbols", None) or card.is_Symbol:
        return False
    shapes = [card]
    if card.is_Pow:
        with sympy_decline():
            power = card.exp.doit()
            if isinstance(power, Rational) and power.p == 1 and power.q > 1:
                shapes.append(card.base)
    return any(shape == written for shape in shapes for written in given)
