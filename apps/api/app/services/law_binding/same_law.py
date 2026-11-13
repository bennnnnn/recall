# ruff: noqa: RUF002, RUF003 -- a form is written as a reader sees it (× 100%).
"""How a form of a law stands to the law: the same, a percent of it, or it at a value.

A reply prints a law, then the form its solver worked with. When the two share a left
side, the reader has to see why both hold, or one of them goes:

- the same function written differently (``½gt²`` and ``gt²/2``, ``× 100\\%`` and ``100``):
  one form is enough;
- a hundred times the law (``N/N₀ = 100(½)ⁿ`` under ``N/N₀ = (½)ⁿ``): the law as a percent;
- the law with one of its symbols at 0 (``h_max = v₀²/2g`` under ``h_max = h₀ + v₀²/2g``):
  it holds for that value;
- a different number for the question's own givens: the law does not hold as written
  there (a train that stops before the time asked), and only the form worked with does.

Each side is read in its symbols (``reduction.law_tree``) and evaluated, never solved: a
few fixed sets of values for the symbols, and the givens themselves. A side outside the
reader's grammar answers nothing, and the caller leaves the rows as they are.
"""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable, Mapping

from app.services.law_binding.expression import Notation, tree_value
from app.services.law_binding.leaf_units import SYMBOL
from app.services.law_binding.reduction import law_tree
from app.services.law_binding.symbols import plain_symbol

# Spellings the reader does not take that change no value: ``× 100\%`` is the number times
# 100, read as a percent; a unit after a thin space; ``⇒ ω_f``, naming what is worked out
# next; log₁₀ is ln over ln 10; bars round a size are \lvert and \rvert, which the reader
# takes as a factor after a number (``2|a|``); a slash over letters written together divides
# by all of them, as a formula means it (``t/RC`` is t/(RC), where the reader takes t/R × C).
_SPELLINGS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\\%"), ""),
    (re.compile(r"\\,\s*\\mathrm\{[^{}]*\}"), ""),
    (re.compile(r"\s*\\Rightarrow.*$"), ""),
    (re.compile(r"\\log_\{?10\}?"), r"\\frac{1}{\\ln(10)}\\ln"),
    (re.compile(r"\|([^|]+)\|"), r"\\lvert \1 \\rvert "),
    (re.compile(r"/((?:[A-Za-z](?:_\{[^{}]*\}|_[A-Za-z0-9])?){2,})"), r"/(\1)"),
)
# Values a symbol takes when the forms are compared: not round, not 0, and in a range where
# a root, a logarithm and an inverse sine of the usual school laws stay real.
_SAMPLES = ((0.731, 0.413, 0.917), (0.523, 0.871, 0.389), (0.649, 0.287, 0.958))
_PERCENT = 100.0
_NOTATION = Notation(constants={}, number=str)


def _tree(side: str) -> ast.expr | None:
    for pattern, spelling in _SPELLINGS:
        side = pattern.sub(spelling, side)
    return law_tree(side.strip())


def _symbols(tree: ast.expr) -> list[str]:
    """The tree's symbols, each once."""
    seen: dict[str, None] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id.startswith(SYMBOL):
            seen.setdefault(node.id, None)
    return list(seen)


def _value(tree: ast.expr, values: Mapping[str, float]) -> float | None:
    try:
        value = tree_value(tree, values, _NOTATION)
    except (ValueError, KeyError, TypeError, ZeroDivisionError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _samples(names: list[str]) -> list[dict[str, float]]:
    """Fixed values for ``names``, a set per sample, each symbol its own value."""
    return [
        {name: row[at % len(row)] * (1 + at) for at, name in enumerate(names)} for row in _SAMPLES
    ]


def _always(
    form: ast.expr, law: ast.expr, holds: Callable[[float, float], bool], fixed: dict[str, float]
) -> bool:
    """``holds(form, law)`` at every sample of their symbols that both evaluate at, and at
    two of them at least."""
    names = list(dict.fromkeys([*_symbols(form), *_symbols(law)]))
    compared = 0
    for sample in _samples(names):
        values = {**sample, **fixed}
        left, right = _value(form, values), _value(law, values)
        if left is None or right is None:
            continue
        if not holds(left, right):
            return False
        compared += 1
    return compared >= 2


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)


def same_function(form: str, law: str) -> bool:
    """``form`` is ``law`` written another way: equal for every value of their symbols."""
    form_tree, law_side = _tree(form), _tree(law)
    if form_tree is None or law_side is None:
        return False
    return _always(form_tree, law_side, _close, {})


def as_percent(form: str, law: str) -> bool:
    """``form`` is ``law`` times 100: the same quantity as a percent."""
    form_tree, law_side = _tree(form), _tree(law)
    if form_tree is None or law_side is None:
        return False
    return _always(form_tree, law_side, lambda left, right: _close(left, _PERCENT * right), {})


def zeroed_symbol(form: str, law: str) -> str | None:
    """The symbol of ``law`` that ``form`` is the law at 0 of (h₀ in h₀ + v₀²/2g), if one."""
    form_tree, law_side = _tree(form), _tree(law)
    if form_tree is None or law_side is None:
        return None
    for name in _symbols(law_side):
        if name not in _symbols(form_tree) and _always(form_tree, law_side, _close, {name: 0.0}):
            return name.removeprefix(SYMBOL)
    return None


def differs_at(form: str, law: str, givens: Mapping[str, float]) -> bool:
    """Whether ``form`` and ``law`` give different numbers for these ``givens`` (by symbol,
    as the formulas write it), when both can be worked out from them."""
    form_tree, law_side = _tree(form), _tree(law)
    if form_tree is None or law_side is None:
        return False
    values = {f"{SYMBOL}{plain_symbol(symbol)}": value for symbol, value in givens.items()}
    left, right = _value(form_tree, values), _value(law_side, values)
    return left is not None and right is not None and not math.isclose(left, right, rel_tol=1e-6)
